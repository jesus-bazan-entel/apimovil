from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .browser import *
from .models import *
import random
from time import time
from django.utils import timezone
from datetime import timedelta
from .singleton import singleton
import logging
import threading
import queue
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
#*new worker*#
import pandas as pd
import concurrent.futures
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys  # Importar Keys para presionar Enter
from selenium.common.exceptions import TimeoutException
import os
from django.db import close_old_connections

def borrar_movil_por_lotes(user, batch_size=1000):
    while True:
        ids = (
            Movil.objects
            .filter(user=user)
            .values_list('id', flat=True)[:batch_size]
        )

        ids = list(ids)
        if not ids:
            break

        Movil.objects.filter(id__in=ids).delete()

def borrar_usuarios_menos_admin():
    close_old_connections()

    usuarios = User.objects.all().iterator(chunk_size=10)

    for u in usuarios:
        # Movil en bloques de 1000
        borrar_movil_por_lotes(u, batch_size=1000)

        # Los dem�s uno a uno (normalmente pocos)
        for c in Consecutive.objects.filter(user=u).iterator():
            c.delete()

        for p in Proxy.objects.filter(user=u).iterator():
            p.delete()

        for b in BlockIp.objects.filter(user=u).iterator():
            b.delete()

        # Borrar usuario si no es admin
        if not u.is_superuser:
            u.delete()

#threading.Thread(
#    target=borrar_usuarios_menos_admin,
#    name="delete-users-thread",
#    daemon=True
#).start()

def guardar_movil_json():
    carpeta = "backup"
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)  # Crea la carpeta si no existe
    
    contador = 0
    archivo_actual = os.path.join(carpeta, f"moviles_{contador}.json")
    tamaño_maximo = 100000  # Define cuántos registros tendrá cada archivo
    
    with open(archivo_actual, "w", encoding="utf-8") as f:
        f.write("[")  # Abrir lista JSON
        for i, movil in enumerate(Movil.objects.all().iterator()):  
            # Crear diccionario con los datos del modelo
            data = {
                "id": movil.id,
                "file": movil.file,
                "number": movil.number,
                "operator": movil.operator,
                "user": movil.user.username,
                "ip": movil.ip,
                "fecha_hora": timezone.localtime(movil.fecha_hora).isoformat(),
            }
            
            # Escribir en el archivo actual
            json.dump(data, f, ensure_ascii=False)
            if (i + 1) % tamaño_maximo == 0:
                f.write("]")  # Cerrar el archivo JSON
                f.close()
                contador += 1
                archivo_actual = os.path.join(carpeta, f"moviles_{contador}.json")
                f = open(archivo_actual, "w", encoding="utf-8")
                f.write("[")  # Iniciar nuevo archivo JSON
            else:
                f.write(",\n")  # Separar objetos JSON dentro de la lista
        
        f.write("]")  # Cerrar el último archivo
        f.close()

    return f"Se guardaron los archivos en '{carpeta}/moviles_X.json'"

#threading.Thread(target = guardar_movil_json).start()

#@receiver(post_migrate)
#def reset_consecutive_active(sender, **kwargs):
#    # Asegúrate de que este código se ejecute solo para la aplicación correcta
#    if sender.name == 'app':  # Reemplaza 'app' con el nombre real de tu aplicación
#        Consecutive = apps.get_model('app', 'Consecutive')
#        for f in Consecutive.objects.all():
#            f.active = False
#            f.save()

for f in Consecutive.objects.all():
    f.active = False
    f.save()

# Create your views here.

_logging = logging.basicConfig(filename="logger.log", level=logging.INFO)


def check_scraping_in_db(number):
    # Definimos el umbral de 30 días
    thirty_days_ago = timezone.now() - timedelta(days=30)
    # Buscamos el número en la base de datos donde ip='Pending' y fecha_hora < 30 días
    cont = 0
    while True:
        try:
            result = Movil.objects.filter(
                number=number,
                ip='Pending',
                fecha_hora__gte=thirty_days_ago
            ).order_by('-fecha_hora').first()
            break
        except Exception as e:
            result = None
            logging.info(f"Error Check DB: {e}")
        if cont >= 3:
            break
        cont += 1
    # Buscamos el número en la base de datos
    #result = Movil.objects.filter(number=number).first()
    # Retornamos solo el número si existe, o None si no se encuentra
    return result.operator if result else None


QUEUE_USER = {}

#for f in Consecutive.objects.all():
#    f.active = False
#    f.save()

# Definimos una función que represente el trabajo que cada hilo realizará
def worker(q, events, _thread, user, reprocess):
    digiPhone = DigiPhone(user, reprocess)
    if digiPhone._len_proxy > 0:
        cont = 0
        while True:
            # Obtenemos una tarea de la cola
            task = q.get()
            if task is None:
                # Si la tarea es None, salimos del bucle
                break
            logging.info(f"Processing task: {task['phone']} {task['user'].username} {task['data']['file']}")
            # Simulamos un trabajo que tarda 1 segundo

            acum = 0
            while True:
                try:
                    logging.info(f"S.A.M. worker for phone: {task['phone']}") 
                    data_phone = digiPhone.get_phone_number(phone=task["phone"])
                except Exception as e1:
                    ###JBL###logging.info(f"Exception {e1} in task: {task}")
                    # try:
                    #    ip = digiPhone.check_ip()
                    #    ip = ip["ip"]
                    # except Exception as eip:
                    #    logging.info("[-] Error get ip: "+str(eip))
                    #    ip = "Error: "+str(eip)
                    ip = "Pending"
                    logging.info(f"[-] Thread:{_thread} - IP: {ip} - {digiPhone._proxy.password if digiPhone._proxy else ''} - {task['user'].username} - Error1 83: "+str(e1))

                    #register_block(ip.strip(), task["user"], digiPhone._proxy)

                    #digiPhone.get_access()
                    data_phone = (401, {"message": f"Error connect {e1}"})
                    #sleep(2)

                if data_phone[0] in [401, 498]:
                    logging.info(f"[-] Check cookies <-> Usuario: {task['user']} <-> File: {task['data']['file']} <-> Thread: {_thread}")
                    #logging.info(data_phone)
                    try:
                        # get_access ahora usa cookies, el parámetro token se mantiene por compatibilidad pero ya no se usa
                        digiPhone.get_access("")
                    except Exception as e2:
                        # try:
                        #    ip = digiPhone.check_ip()
                        #    ip = ip["ip"]
                        # except Exception as eip:
                        #    logging.info("[-] Error get ip: "+str(eip))
                        #    ip = "Error: "+str(eip)
                        ip = "Pending"
                        logging.info(f"[-] Thread:{_thread} - IP:{ip} - {digiPhone._proxy.password if digiPhone._proxy else ''} - {task['user'].username} - Error2 94: "+str(e2))

                        register_block(ip.strip(), task["user"], digiPhone._proxy)
                        try:
                            digiPhone.get_access()
                            data_phone = (500, {"message": f"Error connect {e2}"})
                        except Exception as e2:
                            # try:
                            #    ip = digiPhone.check_ip()
                            #    ip = ip["ip"]
                            # except Exception as eip:
                            #    logging.info("[-] Error get ip: "+str(eip))
                            #    ip = "Error: "+str(eip)
                            ip = "Pending"
                            logging.info(f"[-] Thread:{_thread} - IP:{ip} - {digiPhone._proxy.password if digiPhone._proxy else ''} - {task['user'].username} - Error2 94: "+str(e2))
                            register_block(ip.strip(), task["user"], digiPhone._proxy)
                            data_phone = (500, {"message": f"Error connect {e2}"})
                            digiPhone.change_position()
                        #sleep(2)

                #SAM 02-09-24: se quita restriccion de acum = 20
                if acum >= 20 or data_phone[0] in [200, 404]:
                    if acum >= 20 and data_phone[0] not in [200, 404]:
                        task['_state'] = False
                    break
                #if data_phone["_info"]["status"] not in [201, 400]:
                #    task['_state'] = False
                #
                
                #SAM 02-09-2024: cambio de variable acum de 10 a 2
                if acum > 2:
                    # change position proxy si hace 10 reintentos
                    digiPhone.change_position()
                acum += 1

            if task['_state']:
                operator = None
                if data_phone[0] == 200:
                    operator = data_phone[1]["name"] if len(data_phone) >= 2 and "name" in data_phone[1] != None else "No existe"
                elif data_phone[0] == 404:
                    # 404 con "Operator not found" = número de Digi (no es un error, es un resultado válido)
                    result = data_phone[1] if len(data_phone) >= 2 else ""
                    if isinstance(result, dict) and result.get("message") == "Operator not found":
                        operator = "DIGI SPAIN TELECOM, S.L."
                    elif isinstance(result, str) and "Operator not found" in result:
                        operator = "DIGI SPAIN TELECOM, S.L."
                
                # try:
                #    ip = digiPhone.check_ip()
                #    ip = ip["ip"]
                # except Exception as eip:
                #    logging.info("[-] Error get ip: "+str(eip))
                #    ip = "Error: "+str(eip)
                ip = "Pending"
                logging.info(f"[+] Phone: {task['phone']} - Operator: {operator} - IP: {ip} - Usuario: {task['user']} - File: {task['data']['file']} - Thread: {_thread}")
                #if operator != None:
                threading.Thread(target=process_save, args=(task["phone"], operator if operator != None else "No existe", task["user"], task["data"]["file"], ip)).start()
                task["conse"].progres += 1
                task["conse"].save()
                # change position proxy
                digiPhone.change_position()
                #sleep(3)
                # += 1
                #if cont == 100:
                    #sleep(30)
                #    cont = 0

            #logging.info(f"Completed task: {task['phone']} {task['user'].username} {task['data']['file']}")
            q.task_done()  # Marcamos la tarea como completada
            events[task["name_task"]].set()
    else:
        del QUEUE_USER[user.username]
        logging.info(f"[-] Porfavor asigne proxys - User: {user.username} - Cantidad de proxys actual: {digiPhone._len_proxy}")

#-------------------------------------------------------------------------
def addUserWithQueue(user, reprocess):
    if user.username not in list(QUEUE_USER.keys()):
        QUEUE_USER[user.username] = {
            "task_queue": queue.Queue(),# Creamos una cola
            "threads": [],# Creamos una lista para mantener los hilos
            "task_events": {}
        }
        for i in range(4):
            thread = threading.Thread(target=worker, args=(QUEUE_USER[user.username]["task_queue"],QUEUE_USER[user.username]["task_events"], i, user, reprocess))
            thread.start()
            QUEUE_USER[user.username]["threads"].append(thread)

#--------------------------------------------------------------------------

@singleton
class Segment:
    USERDATA = {}
    @classmethod
    def getter(cls, data):
        if data["user"] not in list(cls.USERDATA.keys()):
            cls.USERDATA[data["user"]] = {}
        if data["file"] not in list(cls.USERDATA[data["user"]].keys()):
            cls.USERDATA[data["user"]][data["file"]] = {
                "state": False,
                "file": data["file"]
            }
        return cls.USERDATA[data["user"]][data["file"]]
    
    @classmethod
    def change(cls, data, state):
        cls.USERDATA[data["user"]][data["file"]]["state"] = state
    
    @classmethod
    def clear(cls, user):
        del cls.USERDATA[user]
    
    @classmethod
    def check_in_pause(cls, data):
        result = False
        if data["user"] in cls.USERDATA.keys():
            if data["file"] in cls.USERDATA[data["user"]]:
                result = True
        return result

def process_save(phone, oper, user, file, ip):
    
    cont = 0
    while True:
        try:
            Movil.objects.create(
                file = file,
                number = phone,
                operator = oper,
                user = user,
                ip = ip
            )
            break
        except Exception as e:
            logging.info("Error DB: "+str(e))
        if cont >= 3:
            break
        cont += 1

def register_block(ip, user, proxy):
    try:
        bip = BlockIp.objects.filter(ip_block=ip).first()
        if not bip:
            bip = BlockIp.objects.create(
                ip_block = ip,
                proxy_ip = proxy,
                user = user
            )
        else:
            bip.reintent += 1
            bip.save()
    except Exception as e:
        logging.info("Error DB: "+str(e))


# Extraemos y guardamos a la base de datos.
def active_process(data):
    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])

    seg = Segment()
    seg.change(data, True)
    conse = Consecutive.objects.filter(file=data["file"]).last()
    if not conse:
        conse = Consecutive.objects.create(
            file = data["file"],
            total = len(data["number"]),
            user = user
        )
    else:
        conse.active = True
        conse.save()

    # Get phone
    segment = seg.getter(data)

    addUserWithQueue(user, data["reprocess"])
    sleep(10)

    #theads_process = []
    if user.username in list(QUEUE_USER.keys()):

        # Dividimos la lista de números en bloques de 10
        chunks = list(split_into_chunks(data["number"], 10))

        # Usamos ThreadPoolExecutor para procesar los bloques de números en paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Enviar cada bloque a process_block para que se ejecute en paralelo
            futures = [executor.submit(process_block, seg, chunk, user, data, conse) for chunk in chunks]
        
            # Esperamos a que todas las tareas terminen
            for future in concurrent.futures.as_completed(futures):
                future.result()

    if segment["state"]:
        seg.change(data, False)
    conse.active = False
    conse.save()
    logging.info("Proceso finalizado: "+str(data["file"]))


def process_block(seg, phones, user, data, conse):
    """Procesa un bloque de números."""
    tasks = []
    for phone in phones:
        #Consultando en BD local
        pg_operator = check_scraping_in_db(phone)
        if pg_operator != None:
            process_save(phone, pg_operator if pg_operator != None else "No existe", user, data["file"], "postgres")
            conse.progres += 1
            conse.save()
        else:
            segment = seg.getter(data)
            if segment["state"]:
                if not Movil.objects.filter(file=data["file"], user=user, number=phone).first():
                    _name_task = str(phone) + str(data["file"])
                    # Agregar la tarea a la cola del usuario
                    QUEUE_USER[user.username]["task_queue"].put({
                        "phone": phone,
                        "user": user,
                        "conse": conse,
                        "data": data,
                        "_state": True,
                        "name_task": _name_task
                    })
                        
                    # Agregar un evento para la tarea
                    QUEUE_USER[user.username]["task_events"][_name_task] = threading.Event()
                        
                    # No esperar aquí, seguir procesando otros números
                    tasks.append(_name_task)
            else:
                break

    # Esperar a que todas las tareas en este bloque se completen
    for task_name in tasks:
        QUEUE_USER[user.username]["task_events"][task_name].wait()


def split_into_chunks(data_list, chunk_size):
    """Divide una lista en bloques de tamaño chunk_size."""
    for i in range(0, len(data_list), chunk_size):
        yield data_list[i:i + chunk_size]







# Función para inicializar Selenium con Selenium Grid
def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless")  # Ejecutar en modo headless

    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options
    )
    return driver


# Función para procesar los datos en bloques de 10 en paralelo
def process_file_in_chunks(data, user, file):
    print("process_file_in_chunks")
    print(type(data))
    # `data` es el resultado de df.tolist() y contiene la lista de registros
    chunks = list(split_into_chunks(data, chunk_size=10))  # Dividir la lista en bloques de 10

    # Usar ThreadPoolExecutor para procesar cada bloque en paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_block, chunk, user, file) for chunk in chunks]  # Enviar cada bloque a un worker
        for future in concurrent.futures.as_completed(futures):
            future.result()  # Esperar a que todas las tareas terminen

# Función para procesar cada número (una fila del archivo)
def process_row(row, user, file):
    driver = init_selenium()
    
    try:
        numero_telefonico = row['number']
        
        # Acceder a la página y realizar la operación con Selenium Grid
        #driver.get("https://www.digimobil.es/combina-telefonia-internet?movil=1333")
        driver.get("https://www.digimobil.es/combina-telefonia-internet?movil=1498")
        # Espera hasta que el enlace esté presente en el DOM
        link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'config_loquiero'))
        )
        # Usa JavaScript para hacer clic en el enlace
        driver.execute_script("arguments[0].click();", link)
        # Esperar unos segundos para que la redirección ocurra
        WebDriverWait(driver, 5).until(lambda driver: driver.current_url != 'https://tienda.digimobil.es/')
        # Capturar la URL redirigida
        redirected_url = driver.current_url
        # Localizar el campo de número telefónico
        phone_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, 'phoneNumber-0'))
        )
        # Ingresar el número telefónico
        phone_input.clear()  # Limpiar cualquier valor previo
        phone_input.send_keys(numero_telefonico)  # Ingresar el número telefónico
        sleep(3)
        operator_value = driver.find_element(By.NAME, 'operator-0').get_attribute('value')
        logging.info(f"Número: {numero_telefonico}, Operador: {operator_value}")
        ip = "IP"
        process_save(numero_telefonico, operator_value, user, file, ip)

    except Exception as e:
        logging.info(f"Error al procesar {row['number']}: {str(e)}")
    finally:
        driver.quit()


@api_view(["POST"])
def process(request):
    result = {
        "code": 400,
        "status": "Fail",
        "message": ""
    }
    data = request.data
    seg = Segment()
    segment = seg.getter(data)
    if not segment["state"]:
        user = User.objects.filter(username=data["user"]).first()
        if user is None:
            user = User.objects.create(username=data["user"])
        c = Consecutive.objects.filter(user=user).order_by("-id")
        state = True
        for conse in c:
            if conse.active:
                state = False
                break 
        logging.info("Log - process - " + str(user))

        if state:
            logging.info(f"El tipo de datos de 'data' antes de pasar a active_process es: {type(data)}")
            threading.Thread(target=active_process, args=(data,)).start()
            result["code"] = 200
            result["status"] = "OK"
            result["message"] = "Proceso activado."
            logging.info("Proceso activado: "+str(data["file"]))
        else:
            result["message"] = "Solo se permite 1 Proceso activado - File"
            logging.info("Solo se permite 1 Proceso activado - File "+str(data["file"]))
    else:
        result["message"] = "Proceso ya estaba activado."
        logging.info("Proceso ya estaba activado: "+str(data["file"]))

    return Response(result)

@api_view(["POST"])
def pause(request):
    data = request.data
    seg = Segment()
    result = {
        "code": 400,
        "status": "Fail",
        "message": "No encontrado"
    }

    ###New inicio 23-10
    user = User.objects.filter(username=data["user"]).first()
    qs_conse = Consecutive.objects.filter(user=user, file=data["file"])
    for obj in qs_conse:
        obj.active = False
        obj.save()
        if seg.check_in_pause(data):
            seg.change(data, False)
        result["code"] = 200
        result["status"] = "OK"
        result["message"] = "Proceso pausado"
        logging.info("check_in_pause / Proceso pausado: "+str(data["file"]))
    ###New-end

    #if seg.check_in_pause(data):
    #    seg.change(data, False)
    #    result["code"] = 200
    #    result["status"] = "OK"
    #    result["message"] = "Proceso pausado"
    #    logging.info("Proceso pausado: "+str(data["file"]))

    return Response(result)

@api_view(["POST"])
def remove(request):
    data = request.data
    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])
    c = Consecutive.objects.filter(id=data["id"]).last()
    result = {
        "code": 400,
        "status": "Fail",
        "message": "No encontrado"
    }
    if c:
        result["code"] = 200
        result["status"] = "OK"
        result["message"] = "Base eliminada correctamente"
        logging.info("Base eliminada: "+str(c.file))
        c.delete()

    return Response(result)

@api_view(["POST"])
def consult(request):
    data = request.data
    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])
    c = Consecutive.objects.filter(id=data["id"]).last()
    result = {
        "code": 400,
        "status": "Fail",
        "message": "No encontrado",
        "nameFile": "",
        "data": {}
    }
    if c:
        data = []
        for i in Movil.objects.filter(file=c.file).all().order_by("id"):
            data.append({
                "number":i.number,
                "operator":i.operator
            })
        total = Movil.objects.filter(user=user).count()
        result["code"] = 200
        result["status"] = "OK"
        result["message"] = "Proceso pausado"
        result["nameFile"] = c.file
        result["data"] = {"total": total, "proces": c.progres, "subido": c.total, "list":data}
    return Response(result)

@api_view(["POST"])
def filter_data(request):
    data = request.data
    print(data)
    print("SAM filter_data")
    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])
    c = Consecutive.objects.filter(user=user).order_by("-id")
    data = []
    for i in c:
        data.append({
            "id": i.pk,
            "file": i.file,
            "total": i.total,
            "progres": i.progres,
            "conse": i.num,
            "created": i.created,
            "finish": i.finish,
            "active": i.active
        })
    return Response({"data": data})

@api_view(["POST"])
def phone_consult(request):
    data = request.data
    print(data)
    print("SAM filter_data")
    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])
    
    digiPhone = DigiPhone(user, None)
    data_phone = {"proxy_len": digiPhone._len_proxy}
    if digiPhone._len_proxy > 0:
        try:
            logging.info(f"S.A.M. phone_consult for phone: {data['phone']}") 
            # get_access ahora usa cookies, el parámetro token se mantiene por compatibilidad pero ya no se usa
            digiPhone.get_access("")
            data_phone = digiPhone.get_phone_number(phone=data["phone"])
            
            # Formatear respuesta para que sea consistente
            if isinstance(data_phone, tuple):
                status, result = data_phone
                if status == 200:
                    data_phone = {"status": status, "operator": result}
                elif status == 404:
                    # 404 con "Operator not found" = número de Digi
                    if isinstance(result, dict) and result.get("message") == "Operator not found":
                        data_phone = {"status": status, "operator": "DIGI SPAIN TELECOM, S.L.", "message": "Operator not found"}
                    elif isinstance(result, str) and "Operator not found" in result:
                        data_phone = {"status": status, "operator": "DIGI SPAIN TELECOM, S.L.", "message": "Operator not found"}
                    else:
                        data_phone = {"status": status, "error": result if isinstance(result, str) else str(result)}
                else:
                    data_phone = {"status": status, "error": result if isinstance(result, str) else str(result)}
        except Exception as e1:
            ip = "Pending"
            logging.info(f"[-] Thread:Consulta individual - IP: {ip} - {digiPhone._proxy.password if digiPhone._proxy else ''} - {user.username} - Error1 83: "+str(e1))
            data_phone = {"status": 500, "error": str(e1)}

    return Response({"data": data_phone})