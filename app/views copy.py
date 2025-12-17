from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .browser import *
from .models import *
import random
from time import time
from .singleton import singleton
import logging
import threading
import queue
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps

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
                    data_phone = digiPhone.get_phone_by_request(phone=task["phone"])
                except Exception as e1:
                    logging.info(f"Exception in get_phone_by_request: {e1}")
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
                    data_phone = {"_info": {"status": 401}}
                    #sleep(2)

                if data_phone["_info"]["status"] in [401, 498]:
                    logging.info(f"[-] Check token <-> Usuario: {task['user']} <-> File: {task['data']['file']} <-> Thread: {_thread}")
                    #logging.info(data_phone)
                    try:
                        digiPhone.get_access(digiPhone._token if digiPhone._token else "")
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
                            data_phone = {"_info": {"status": 500}}
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
                            data_phone = {"_info": {"status": 500}}
                            digiPhone.change_position()
                        #sleep(2)

                #SAM 02-09-24: se quita restriccion de acum = 20
                if acum >= 20 or data_phone["_info"]["status"] in [201, 400]:
                    if acum >= 20 and data_phone["_info"]["status"] not in [201, 400]:
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
                if data_phone["_info"]["status"] == 201:
                    operator = data_phone["_result"]["operatorSOAPDesc"] if data_phone["_result"]["operatorSOAPDesc"] != None else "No existe"
                elif data_phone["_info"]["status"] == 400:
                    if data_phone["_error"] != []:
                        if data_phone["_error"]["message"] == "Number is Digi":
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
        for i in range(1):
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
    try:
        Movil.objects.create(
            file = file,
            number = phone,
            operator = oper,
            user = user,
            ip = ip
        )
    except Exception as e:
        logging.info("Error DB: "+str(e))

def register_block(ip, user, proxy):
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

# def process_in_worker(phone, user, conse, data, _name_task):
#     task_queue.put({
#         "phone": phone,
#         "user": user,
#         "conse": conse,
#         "data": data,
#         "_state": True,
#         "name_task": _name_task
#     })
#     # add event
#     task_events[_name_task] = threading.Event()
#     # Wait event
#     task_events[_name_task].wait()

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
        for phone in data["number"]:
            segment = seg.getter(data)
            if segment["state"]:
                if not Movil.objects.filter(file=data["file"], user=user, number=phone).first():
                    _name_task = str(phone)+str(data["file"])
                    QUEUE_USER[user.username]["task_queue"].put({
                        "phone": phone,
                        "user": user,
                        "conse": conse,
                        "data": data,
                        "_state": True,
                        "name_task": _name_task
                    })
                    # add event
                    QUEUE_USER[user.username]["task_events"][_name_task] = threading.Event()
                    # Wait event
                    QUEUE_USER[user.username]["task_events"][_name_task].wait()
                    # _thread = threading.Thread(target=process_in_worker, args=(phone, user, conse, data, _name_task))
                    # _thread.start()
                    # theads_process.append(_thread)
                    # if len(positions) == len(theads_process):
                    #     for t in theads_process:
                    #         t.join()
                    #     theads_process = []
            else:
                break
    
    if segment["state"]:
        seg.change(data, False)
    conse.active = False
    conse.save()
    logging.info("Proceso finalizado: "+str(data["file"]))

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
        #SAM 14-09-2024
        state = True
        #SAM 01-09-2024
        for conse in c:
            if conse.active:
                state = False
                break 
        #SAM 01-09-2024
        logging.info("Log - process - " + str(user))

        if state:
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
    if seg.check_in_pause(data):
        seg.change(data, False)
        result["code"] = 200
        result["status"] = "OK"
        result["message"] = "Proceso pausado"
        logging.info("Proceso pausado: "+str(data["file"]))

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