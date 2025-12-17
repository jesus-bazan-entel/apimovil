from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import F
from app.models import Consecutive
import pandas as pd
import requests
from django.db.models import OuterRef, Subquery
import json

@shared_task
def simple_task():
    print("Tarea ejecutada exitosamente")
    return "Hecho"

@shared_task
def process_incomplete_files_task():
    three_days_ago = timezone.now() - timedelta(days=1)

    #incomplete_files = Consecutive.objects.filter(
    #    progres__lt=F('total'),
    #    active=False,
    #    created__gte=seven_days_ago
    #).order_by('-created')

    # Subquery para obtener el archivo más reciente de cada usuario en los últimos 3 días
    latest_file_subquery = Consecutive.objects.filter(
        user=OuterRef('user'),  # Filtrar por usuario
        progres__lt=F('total'),  # Progreso menor que el total (archivo incompleto)
        active=False,  # Solo archivos inactivos
        created__gte=three_days_ago  # Solo archivos creados en los últimos 3 días
    ).order_by('-created').values('id')[:1]  # Obtener el más reciente (orden descendente por fecha)

    # Filtrar los archivos incompletos más recientes por usuario
    incomplete_files = Consecutive.objects.filter(
        id=Subquery(latest_file_subquery)  # Emparejar los archivos más recientes
    )

    for doc in incomplete_files:
        print(f"tasks.py process_incomplete_files_task : {doc}")
        process_single_file(doc)

def process_single_file(doc):
    print(f"Procesando archivo {doc.file}")
    try:
        # Dividir el nombre del archivo por "/" y verificar si tiene más de un elemento
        file_parts = str(doc.file).split("/")
        print(f"Partes del archivo: {file_parts}")  # Agregar logging para verificar las partes

        # Asegurarse de que hay más de una parte antes de acceder al índice [1]
        if len(file_parts) > 1:
            name_file = file_parts[1]
        else:
            name_file = file_parts[0]  # Si no hay "/", tomar el nombre completo

        data = read_file(name_file)  # Asegúrate de que esta función existe
        doc.save()        
        send_data(doc.user.username, data, False, name_file)
    except Exception as e:
        print(f"Error al procesar el archivo {doc.file}: {e}")

def read_file(name_file):
	name_file = name_file.replace(" ", "_")
	file = "/opt/masterfilter/media/subido/" + name_file
	df = pd.read_excel(file, sheet_name='Hoja1')
	df.describe()
	documents = df['numeros'].tolist()
	return documents

def send_data(user, data, op, name_file):
    #url = "https://api.masterfilter.es/process/"
    url = "http://185.47.131.53:8800/process/"
    payload = json.dumps({
        "user": user,
        "number": data,
        "new": op,
        "reprocess": True,
        "file": name_file
    })
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)

