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
from django.core.cache import cache
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
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
import os
from django.db import close_old_connections, transaction, connection
from django.db.utils import OperationalError
# Tareas Celery
from .tasks import (
    process_save_task,
    update_consecutive_task,
    scrape_and_save_phone_task,
    update_consecutive_progress_task
)

logger = logging.getLogger(__name__)

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
        borrar_movil_por_lotes(u, batch_size=1000)

        for c in Consecutive.objects.filter(user=u).iterator():
            c.delete()

        for p in Proxy.objects.filter(user=u).iterator():
            p.delete()

        for b in BlockIp.objects.filter(user=u).iterator():
            b.delete()

        if not u.is_superuser:
            u.delete()

def guardar_movil_json():
    carpeta = "backup"
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)

    contador = 0
    archivo_actual = os.path.join(carpeta, f"moviles_{contador}.json")
    tamaño_maximo = 100000

    with open(archivo_actual, "w", encoding="utf-8") as f:
        f.write("[")
        for i, movil in enumerate(Movil.objects.all().iterator()):
            data = {
                "id": movil.id,
                "file": movil.file,
                "number": movil.number,
                "operator": movil.operator,
                "user": movil.user.username,
                "ip": movil.ip,
                "fecha_hora": timezone.localtime(movil.fecha_hora).isoformat(),
            }

            json.dump(data, f, ensure_ascii=False)
            if (i + 1) % tamaño_maximo == 0:
                f.write("]")
                f.close()
                contador += 1
                archivo_actual = os.path.join(carpeta, f"moviles_{contador}.json")
                f = open(archivo_actual, "w", encoding="utf-8")
                f.write("[")
            else:
                f.write(",\n")

        f.write("]")
        f.close()

    return f"Se guardaron los archivos en '{carpeta}/moviles_X.json'"

_logging = logging.basicConfig(filename="logger.log", level=logging.INFO)


def check_scraping_in_cache_and_db(number):
    """
    🚀 OPTIMIZADO: Busca un número en caché Redis primero, luego en BD.
    
    Returns:
        tuple: (operator, source) donde source es 'cache', 'database' o None
        
    Ejemplos:
        ('Movistar', 'cache')     - Encontrado en caché Redis
        ('Vodafone', 'database')  - Encontrado en BD PostgreSQL
        (None, None)              - No encontrado, requiere scraping
    """
    # 1. BUSCAR EN CACHÉ REDIS (super rápido: ~1ms) ⚡
    try:
        operator = cache.get(f"phone:{number}")
        if operator is not None:
            logger.info(f"[CACHE HIT] ✓ {number} → {operator} (Redis)")
            return (operator, 'cache')
    except Exception as e:
        logger.warning(f"[CACHE ERROR] Error accediendo caché para {number}: {e}")

    # 2. BUSCAR EN BASE DE DATOS (si no está en caché) 🗄️
    logger.debug(f"[CACHE MISS] {number} no en caché, buscando en BD...")
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    max_retries = 3
    base_delay = 0.05
    
    for attempt in range(max_retries):
        try:
            close_old_connections()
            result = Movil.objects.filter(
                number=number,
                fecha_hora__gte=thirty_days_ago
            ).exclude(
                operator__in=['ERROR_SCRAPING', 'No existe', 'Desconocido']
            ).order_by('-fecha_hora').first()
            
            if result:
                logger.info(f"[DB HIT] ✓ {number} → {result.operator} (PostgreSQL)")
                
                # IMPORTANTE: Agregar al caché para próxima vez
                from .signals import add_to_phone_cache
                add_to_phone_cache(number, result.operator, result.file)
                
                return (result.operator, 'database')
            else:
                logger.debug(f"[DB MISS] {number} no encontrado en BD")
                return (None, None)
                
        except OperationalError as e:
            error_str = str(e)
            if "database is locked" in error_str.lower() or "locked" in error_str.lower():
                delay = base_delay * (2 ** attempt)
                logger.debug(f"[check_scraping_in_cache_and_db] ⚠ DB locked para {number} (intento {attempt + 1}/{max_retries}) - Esperando {delay:.2f}s")
                sleep(delay)
            else:
                logger.warning(f"[check_scraping_in_cache_and_db] ✗ OperationalError para {number}: {error_str}")
                return (None, None)
        except Exception as e:
            logger.warning(f"[check_scraping_in_cache_and_db] ✗ Error DB para {number}: {str(e)}")
            if attempt >= max_retries - 1:
                return (None, None)
    
    return (None, None)


# Mantener función original para compatibilidad con código existente
def check_scraping_in_db(number):
    """
    DEPRECATED: Usa check_scraping_in_cache_and_db() para mejor rendimiento.
    Se mantiene para compatibilidad con código existente.
    """
    operator, _ = check_scraping_in_cache_and_db(number)
    return operator


QUEUE_USER = {}
QUEUE_USER_LOCK = threading.Lock()

def worker(q, events, _thread, user, reprocess):
    digiPhone = DigiPhone(user, reprocess)
    if digiPhone._len_proxy > 0:
        close_old_connections()

        try:
            logger.info(f"[worker] Thread {_thread} - Obteniendo acceso inicial (cookies)...")
            access_ok = digiPhone.get_access("", get_cart=False)
            if access_ok:
                logger.info(f"[worker] Thread {_thread} - Acceso obtenido correctamente")
            else:
                logger.warning(f"[worker] Thread {_thread} - No se pudo obtener acceso inicial (se intentará en cada tarea)")
        except Exception as e_init:
            logger.warning(f"[worker] Thread {_thread} - Error obteniendo acceso inicial: {e_init} (se intentará obtener en cada tarea)")

        cont = 0
        while True:
            task = q.get()
            if task is None:
                break

            task_start_time = time()
            logger.info(f"[worker] Thread {_thread} - Iniciando tarea: {task['phone']} | Usuario: {task['user'].username} | Archivo: {task['data']['file']}")

            acum = 0
            ssl_error_count = 0
            max_task_time = 180
            max_ssl_errors = 3

            while True:
                elapsed_time = time() - task_start_time
                if elapsed_time > max_task_time:
                    logger.warning(f"[worker] Thread {_thread} - ⚠ TIMEOUT: Tarea {task['phone']} excedió {max_task_time}s (tiempo: {elapsed_time:.2f}s)")
                    task['_state'] = False
                    data_phone = (500, {"message": f"Task timeout after {max_task_time}s"})
                    break

                try:
                    logger.info(f"[worker] Thread {_thread} - Intento {acum + 1} para teléfono: {task['phone']}")
                    data_phone = digiPhone.get_phone_number(phone=task["phone"])
                    ssl_error_count = 0
                except Exception as e1:
                    error_str = str(e1)
                    ip = "Pending"

                    is_ssl_error = any(ssl_keyword in error_str for ssl_keyword in [
                        "SSLZeroReturnError", "SSLError", "TLS/SSL connection has been closed",
                        "Max retries exceeded", "Connection closed", "EOF"
                    ])

                    error_type = type(e1).__name__
                    is_connection_error = any(conn_keyword in error_str or conn_keyword in error_type for conn_keyword in [
                        "RemoteDisconnected", "Connection aborted", "ConnectionError",
                        "ProtocolError", "Remote end closed connection", "Connection reset",
                        "Broken pipe", "Connection refused"
                    ])

                    if is_ssl_error:
                        ssl_error_count += 1
                        logger.warning(f"[worker] Thread {_thread} - ⚠ Error SSL #{ssl_error_count} para {task['phone']}: {error_str[:200]}")

                        if ssl_error_count >= max_ssl_errors:
                            logger.warning(f"[worker] Thread {_thread} - 🔄 Cambiando proxy después de {ssl_error_count} errores SSL consecutivos")
                            digiPhone.change_position()
                            ssl_error_count = 0
                            sleep(0.5)
                    elif is_connection_error:
                        ssl_error_count += 1
                        logger.warning(f"[worker] Thread {_thread} - ⚠ Error de conexión #{ssl_error_count} para {task['phone']}: {error_type} - {error_str[:200]}")

                        if ssl_error_count >= max_ssl_errors:
                            logger.warning(f"[worker] Thread {_thread} - 🔄 Cambiando proxy después de {ssl_error_count} errores de conexión consecutivos")
                            digiPhone.change_position()
                            ssl_error_count = 0
                            sleep(0.5)
                    else:
                        logger.info(f"[worker] Thread {_thread} - Error desconocido: {error_type} - {error_str[:200]}")

                    logger.info(f"[worker] Thread {_thread} - IP: {ip} | Proxy: {digiPhone._proxy.password if digiPhone._proxy else 'N/A'} | Usuario: {task['user'].username} | Error: {error_str[:150]}")
                    data_phone = (401, {"message": f"Error connect {error_str[:100]}"})

                if data_phone[0] in [401, 498]:
                    logger.info(f"[worker] Thread {_thread} - Reautenticando (401/498) | Usuario: {task['user']} | Archivo: {task['data']['file']}")
                    reauth_success = False

                    try:
                        reauth_success = digiPhone.get_access("", get_cart=False)
                        if not reauth_success:
                            logger.warning(f"[worker] Thread {_thread} - Primera reautenticación falló, cambiando proxy...")
                            digiPhone.change_position()
                            reauth_success = digiPhone.get_access("", get_cart=False)
                    except Exception as e2:
                        ip = "Pending"
                        logger.warning(f"[worker] Thread {_thread} - Error en reautenticación: {e2}")
                        register_block(ip.strip(), task["user"], digiPhone._proxy)
                        digiPhone.change_position()

                        try:
                            reauth_success = digiPhone.get_access("", get_cart=False)
                            if not reauth_success:
                                data_phone = (500, {"message": f"Reauth failed: {str(e2)[:100]}"})
                        except Exception as e3:
                            ip = "Pending"
                            logger.error(f"[worker] Thread {_thread} - Error crítico en reautenticación: {e3}")
                            register_block(ip.strip(), task["user"], digiPhone._proxy)
                            data_phone = (500, {"message": f"Critical reauth error: {str(e3)[:100]}"})
                            digiPhone.change_position()

                    if not reauth_success:
                        logger.error(f"[worker] Thread {_thread} - ✗ Reautenticación falló completamente")
                        data_phone = (500, {"message": "Failed to reauth after multiple attempts"})

                if acum >= 20 or data_phone[0] in [200, 404]:
                    if acum >= 20 and data_phone[0] not in [200, 404]:
                        task['_state'] = False
                        logger.warning(f"[worker] Thread {_thread} - ⚠ Máximo de reintentos alcanzado para {task['phone']} (20 intentos)")
                    break

                if acum >= 2:
                    logger.info(f"[worker] Thread {_thread} - 🔄 Cambiando proxy después de {acum} reintentos fallidos")
                    digiPhone.change_position()
                    sleep(0.3)

                acum += 1

            task_elapsed = time() - task_start_time

            if task['_state']:
                operator = None
                if data_phone[0] == 200:
                    if len(data_phone) >= 2 and isinstance(data_phone[1], dict) and "name" in data_phone[1]:
                        operator = data_phone[1]["name"]
                    else:
                        operator = "No existe"
                        logger.warning(f"[worker] Thread {_thread} - Formato inesperado en respuesta 200: {data_phone}")
                elif data_phone[0] == 404:
                    result = data_phone[1] if len(data_phone) >= 2 else ""
                    if isinstance(result, dict) and result.get("message") == "Operator not found":
                        operator = "DIGI SPAIN TELECOM, S.L."
                    elif isinstance(result, str) and "Operator not found" in result:
                        operator = "DIGI SPAIN TELECOM, S.L."

                ip = "Pending"
                logger.info(f"[worker] Thread {_thread} - ✓ ÉXITO: Teléfono {task['phone']} | Operador: {operator} | Tiempo: {task_elapsed:.2f}s | Usuario: {task['user']} | Archivo: {task['data']['file']}")
                
                process_save_task.delay(
                   phone=task["phone"],
                   operator=operator if operator != None else "No existe",
                   user_id=task["user"].id,
                   file=task["data"]["file"],
                   ip=ip
                )

                task["conse"].progres += 1
                _save_consecutive_with_retry(task["conse"], _thread, max_retries=3)

                digiPhone.change_position()
            else:
                logger.warning(f"[worker] Thread {_thread} - ✗ FALLO: Teléfono {task['phone']} | Tiempo: {task_elapsed:.2f}s | Usuario: {task['user']} | Archivo: {task['data']['file']}")

            q.task_done()
            if task["name_task"] in events:
                events[task["name_task"]].set()
                logger.debug(f"[worker] Thread {_thread} - Evento señalizado para tarea: {task['phone']}")
            else:
                logger.warning(f"[worker] Thread {_thread} - ⚠ Evento no encontrado para tarea: {task['phone']} (name_task: {task.get('name_task', 'N/A')})")

            cont += 1
            if cont % 5 == 0:
                close_old_connections()
                logger.debug(f"[worker] Thread {_thread} - Conexiones DB cerradas después de {cont} tareas")

    else:
        with QUEUE_USER_LOCK:
            QUEUE_USER.pop(user.username, None)
        logger.info(f"[-] Porfavor asigne proxys - User: {user.username} - Cantidad de proxys actual: {digiPhone._len_proxy}")

def addUserWithQueue(user, reprocess):
    """
    NOTA: Función mantenida por compatibilidad pero YA NO USA THREADS.
    Ahora todo se procesa via Celery.
    """
    with QUEUE_USER_LOCK:
        if user.username not in QUEUE_USER:
            QUEUE_USER[user.username] = {
                "task_queue": None,
                "threads": [],
                "task_events": {}
            }
            logger.info(f"[addUserWithQueue] Usuario {user.username} registrado (procesamiento via Celery)")

#@singleton
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
        # Inicializar estructura si no existe
        if data["user"] not in cls.USERDATA:
            cls.USERDATA[data["user"]] = {}
        if data["file"] not in cls.USERDATA[data["user"]]:
            cls.USERDATA[data["user"]][data["file"]] = {
                "state": False,
                "file": data["file"]
            }
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

def _save_consecutive_with_retry(conse, thread_id, max_retries=3):
    """
    Guarda el objeto Consecutive con retry para manejar errores de DB bloqueada.
    """
    base_delay = 0.05

    for attempt in range(max_retries):
        try:
            close_old_connections()
            conse.save()
            return
        except OperationalError as e:
            error_str = str(e)
            if "database is locked" in error_str.lower() or "locked" in error_str.lower():
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[worker] Thread {thread_id} - ⚠ DB locked al guardar progreso (intento {attempt + 1}/{max_retries}) - Esperando {delay:.2f}s")
                sleep(delay)
            else:
                logger.error(f"[worker] Thread {thread_id} - ✗ OperationalError al guardar progreso: {error_str}")
                break
        except Exception as e:
            logger.error(f"[worker] Thread {thread_id} - ✗ Error al guardar progreso: {str(e)}")
            break

    logger.warning(f"[worker] Thread {thread_id} - ⚠ No se pudo guardar progreso después de {max_retries} intentos")


def register_block(ip, user, proxy):
    """
    Registra un bloqueo de IP con manejo de errores de DB bloqueada.
    """
    max_retries = 3
    base_delay = 0.1

    for attempt in range(max_retries):
        try:
            close_old_connections()
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
            return
        except OperationalError as e:
            error_str = str(e)
            if "database is locked" in error_str.lower() or "locked" in error_str.lower():
                delay = base_delay * (2 ** attempt)
                logger.warning(f"[register_block] ⚠ DB locked (intento {attempt + 1}/{max_retries}) - Esperando {delay:.2f}s")
                sleep(delay)
            else:
                logger.error(f"[register_block] ✗ OperationalError: {error_str}")
                break
        except Exception as e:
            logger.error(f"[register_block] ✗ Error DB: {str(e)}")
            break


def active_process(data):
    from django.utils import timezone
    from datetime import timedelta

    user = User.objects.filter(username=data["user"]).first()
    if user is None:
        user = User.objects.create(username=data["user"])

    seg = Segment()
    seg.change(data, True)

    old_threshold = timezone.now() - timedelta(hours=12)
    old_processes = Consecutive.objects.filter(
        user=user,
        active=True,
        created__lt=old_threshold
    )
    if old_processes.exists():
        count = old_processes.count()
        logger.warning(f"Limpiando {count} procesos colgados para usuario {user.username}")
        for old in old_processes:
            logger.warning(f"  - Proceso colgado: {old.file} (ID: {old.id}, creado: {old.created})")
        old_processes.update(active=False)

    conse = Consecutive.objects.filter(
        file=data["file"],
        user=user
    ).order_by('-id').first()

    if conse and conse.progres < conse.total:
        logger.info(f"Reanudando proceso existente: {conse.file} (ID: {conse.id}) - Progreso: {conse.progres}/{conse.total}")
        conse.active = True
        conse.finish = None
        conse.save()

        if len(data["number"]) != conse.total:
            logger.warning(f"El archivo cambió de tamaño: {conse.total} → {len(data['number'])}")
            conse.total = len(data["number"])
            conse.save()
    else:
        logger.info(f"Creando nuevo proceso: {data['file']} - Total: {len(data['number'])} números")
        conse = Consecutive.objects.create(
            file=data["file"],
            total=len(data["number"]),
            user=user,
            active=True,
            finish=None
        )

    try:
        segment = seg.getter(data)
        addUserWithQueue(user, data["reprocess"])
        #sleep(10)

        logger.info(f"[DEBUG] Tipo de data['number']: {type(data['number'])}")
        if len(data["number"]) > 0:
            logger.info(f"[DEBUG] Tipo del primer elemento: {type(data['number'][0])}")
            logger.info(f"[DEBUG] Primeros 3 números del archivo: {data['number'][:3]}")

        bd_sample = list(Movil.objects.filter(
            file=data["file"],
            user=user
        ).values_list('number', flat=True)[:3])
        logger.info(f"[DEBUG] Primeros 3 números de BD: {bd_sample}")
        if bd_sample:
            logger.info(f"[DEBUG] Tipo del primer número de BD: {type(bd_sample[0])}")

        # Procesar siempre - ya no dependemos de QUEUE_USER
        processed_numbers = set(
            str(num) for num in Movil.objects.filter(
                file=data["file"],
                user=user
            ).values_list('number', flat=True)
        )
        file_numbers = [str(num) for num in data["number"]]
        pending_numbers = [num for num in file_numbers if num not in processed_numbers]

        logger.info(f"Total números: {len(file_numbers)} | Ya procesados: {len(processed_numbers)} | Pendientes: {len(pending_numbers)}")

        if pending_numbers:
            from app.tasks import process_file_in_batches, get_user_queue_name

            logger.info(f"[active_process] Iniciando procesamiento en lotes para {data['file']}")
            logger.info(f"[active_process] Números pendientes: {len(pending_numbers)}")

            # Enviar a la cola específica del usuario para round-robin entre usuarios
            user_queue = get_user_queue_name(user.id)
            process_file_in_batches.apply_async(
                kwargs={
                    'consecutive_id': conse.id,
                    'batch_size': 100
                },
                queue=user_queue
            )

            logger.info(f"[active_process] ✓ Procesamiento en lotes iniciado en cola: {user_queue}")
        else:
            logger.info(f"Todos los números ya fueron procesados para {data['file']}")

    except Exception as e:
        logger.error(f"Error en active_process para {data['file']}: {str(e)}")

    finally:
        if segment["state"]:
            seg.change(data, False)

        if conse.progres >= conse.total:
            conse.active = False
            conse.finish = timezone.now()
            logger.info(f"✅ Archivo COMPLETADO: {data['file']} ({conse.progres}/{conse.total})")
        else:
            logger.info(f"⏳ Procesamiento en curso: {data['file']} ({conse.progres}/{conse.total})")

        conse.save()


def process_block(seg, phones, user, data, conse):
    """
    🚀 OPTIMIZADO: Procesa un bloque de números usando caché Redis primero.
    """
    # OPTIMIZACIÓN: Cargar todos los números ya procesados de este archivo UNA VEZ
    already_processed_numbers = set(
        Movil.objects.filter(
            file=data["file"],
            user=user
        ).values_list('number', flat=True)
    )
    logger.info(f"[OPTIMIZACIÓN] {len(already_processed_numbers)} números ya procesados en {data['file']}")

    for phone in phones:
        # 🚀 Consultar en caché + BD con una sola llamada
        operator, source = check_scraping_in_cache_and_db(phone)

        # Verificar si ya procesamos este número en ESTE archivo
        already_processed = phone in already_processed_numbers

        if operator:
            logger.info(f"[{source.upper()}] ✓ Número {phone} encontrado → {operator}")
            # Guardar desde caché/BD via Celery
            process_save_task.delay(
                phone=phone,
                operator=operator,
                user_id=user.id,
                file=data["file"],
                ip=source  # 'cache' o 'database'
            )
            conse.progres += 1
            _save_consecutive_with_retry(conse, "process_block", max_retries=3)

        elif already_processed:
            logger.info(f"Número {phone} ya procesado en {data['file']}, saltando...")
            conse.progres += 1
            _save_consecutive_with_retry(conse, "process_block", max_retries=3)

        else:
            logger.info(f"[SCRAPING] → Número {phone} NO en caché ni BD, enviando a Celery...")
            # Enviar a Celery para scraping
            segment = seg.getter(data)
            if segment["state"]:
                scrape_and_save_phone_task.delay(
                    phone_number=phone,
                    user_id=user.id,
                    file_name=data["file"],
                    max_attempts=3
                )

                update_consecutive_progress_task.delay(
                    consecutive_id=conse.id,
                    increment=1
                )

                logger.info(f"[CELERY] Tarea enviada: {phone}")
            else:
                break

    logger.info(f"[process_block] ✓ Bloque de {len(phones)} números procesado")


def split_into_chunks(data_list, chunk_size):
    """Divide una lista en bloques de tamaño chunk_size."""
    for i in range(0, len(data_list), chunk_size):
        yield data_list[i:i + chunk_size]


def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless")

    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options
    )
    return driver


def process_file_in_chunks(data, user, file):
    print("process_file_in_chunks")
    print(type(data))
    chunks = list(split_into_chunks(data, chunk_size=10))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_block, chunk, user, file) for chunk in chunks]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def process_row(row, user, file):
    driver = init_selenium()

    try:
        numero_telefonico = row['number']

        driver.get("https://www.digimobil.es/combina-telefonia-internet?movil=1498")
        link = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'config_loquiero'))
        )
        driver.execute_script("arguments[0].click();", link)
        WebDriverWait(driver, 5).until(lambda driver: driver.current_url != 'https://tienda.digimobil.es/')
        redirected_url = driver.current_url
        phone_input = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, 'phoneNumber-0'))
        )
        phone_input.clear()
        phone_input.send_keys(numero_telefonico)
        sleep(3)
        operator_value = driver.find_element(By.NAME, 'operator-0').get_attribute('value')
        logger.info(f"Número: {numero_telefonico}, Operador: {operator_value}")
        ip = "IP"
        
        process_save_task.delay(
            phone=numero_telefonico,
            operator=operator_value,
            user_id=user.id,
            file=file,
            ip=ip
        )

    except Exception as e:
        logger.info(f"Error al procesar {row['number']}: {str(e)}")
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
        logger.info("Log - process - " + str(user))

        if state:
            logger.info(f"El tipo de datos de 'data' antes de pasar a active_process es: {type(data)}")
            threading.Thread(target=active_process, args=(data,)).start()
            result["code"] = 200
            result["status"] = "OK"
            result["message"] = "Proceso activado."
            logger.info("Proceso activado: "+str(data["file"]))
        else:
            result["message"] = "Solo se permite 1 Proceso activado - File"
            logger.info("Solo se permite 1 Proceso activado - File "+str(data["file"]))
    else:
        result["message"] = "Proceso ya estaba activado."
        logger.info("Proceso ya estaba activado: "+str(data["file"]))

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
        logger.info("check_in_pause / Proceso pausado: "+str(data["file"]))

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
        logger.info("Base eliminada: "+str(c.file))
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
    response_data = []

    for i in c:
        if i.progres >= i.total:
            status = 'completed'
            status_display = 'Completado'
        elif i.active:
            status = 'processing'
            status_display = 'Procesando'
        elif i.progres > 0:
            status = 'paused'
            status_display = 'Pausado'
        else:
            status = 'pending'
            status_display = 'Pendiente'

        progress_percentage = round((i.progres / i.total * 100), 2) if i.total > 0 else 0

        response_data.append({
            "id": i.pk,
            "file": i.file,
            "total": i.total,
            "progres": i.progres,
            "conse": i.num,
            "created": i.created,
            "finish": i.finish,
            "active": i.active,
            "status": status,
            "status_display": status_display,
            "progress_percentage": progress_percentage
        })

    return Response({"data": response_data})


@api_view(["POST"])
def phone_consult(request):
    """
    Endpoint para consultar un número telefónico individual.
    Retorna estructura compatible con el frontend: {"data": [status_code, data_or_error]}
    """
    result = {"data": [500, "Error interno"]}

    try:
        data = request.data
        logger.info(f"[phone_consult] Request data: {data}")

        if "user" not in data or "phone" not in data:
            result["data"] = [400, "Faltan parámetros: user y phone son requeridos"]
            logger.warning(f"[phone_consult] Faltan parámetros: {data}")
            return Response(result, status=400)

        user = User.objects.filter(username=data["user"]).first()
        if user is None:
            user = User.objects.create(username=data["user"])

        digiPhone = DigiPhone(user, None)

        if digiPhone._len_proxy == 0:
            result["data"] = [400, "No hay proxies disponibles para este usuario"]
            logger.warning(f"[phone_consult] No hay proxies para usuario: {data['user']}")
            return Response(result, status=400)

        logger.info(f"[phone_consult] Consultando teléfono: {data['phone']} para usuario: {data['user']}")

        access_success = digiPhone.get_access("", get_cart=False)
        if not access_success:
            result["data"] = [500, "Error obteniendo acceso (cookies)"]
            logger.error(f"[phone_consult] Error obteniendo acceso")
            return Response(result, status=500)

        data_phone = digiPhone.get_phone_number(phone=data["phone"])

        if isinstance(data_phone, tuple):
            status, result_data = data_phone
            if status == 200:
                if isinstance(result_data, dict):
                    result["data"] = [200, result_data]
                    logger.info(f"[phone_consult] Operador encontrado: {result_data.get('name', 'N/A')} (ID: {result_data.get('operatorId', 'N/A')})")
                else:
                    result["data"] = [200, {"name": "Desconocido", "tradeName": "Desconocido"}]
                    logger.warning(f"[phone_consult] Formato inesperado en respuesta 200: {result_data}")
            elif status == 404:
                if isinstance(result_data, dict) and result_data.get("message") == "Operator not found":
                    result["data"] = [200, {
                        "name": "DIGI SPAIN TELECOM, S.L.",
                        "tradeName": "DIGI SPAIN TELECOM, S.L.",
                        "operatorId": None
                    }]
                    logger.info(f"[phone_consult] Operador: DIGI SPAIN TELECOM, S.L. (Operator not found - Digi)")
                elif isinstance(result_data, str) and "Operator not found" in result_data:
                    result["data"] = [200, {
                        "name": "DIGI SPAIN TELECOM, S.L.",
                        "tradeName": "DIGI SPAIN TELECOM, S.L.",
                        "operatorId": None
                    }]
                    logger.info(f"[phone_consult] Operador: DIGI SPAIN TELECOM, S.L. (Operator not found - Digi)")
                else:
                    error_msg = result_data if isinstance(result_data, str) else str(result_data)
                    result["data"] = [404, error_msg]
                    logger.warning(f"[phone_consult] Error 404: {error_msg}")
            else:
                error_msg = result_data if isinstance(result_data, str) else str(result_data)
                result["data"] = [status, error_msg]
                logger.warning(f"[phone_consult] Error {status}: {error_msg}")
        else:
            result["data"] = [500, f"Formato de respuesta inesperado: {str(data_phone)}"]
            logger.error(f"[phone_consult] Formato inesperado: {type(data_phone)} - {data_phone}")

    except Exception as e:
        logger.exception(f"[phone_consult] Error inesperado: {e}")
        result["data"] = [500, str(e)]

    logger.info(f"[phone_consult] Respuesta final: data[0]={result['data'][0]}")
    return Response(result)
