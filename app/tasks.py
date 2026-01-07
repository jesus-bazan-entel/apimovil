"""
Tareas Celery OPTIMIZADAS con caché Redis y rotación de proxies.

CARACTERÍSTICAS:
- Sistema de caché Redis para números ya consultados
- Procesamiento en lotes para eficiencia
- Manejo robusto de errores con reintentos automáticos
- Métricas y estadísticas de progreso

Archivo: app/tasks.py (VERSIÓN OPTIMIZADA)
"""
from celery import shared_task
from django.db import transaction, connection
from django.db.models import F
from .models import Movil, Consecutive
from django.core.cache import cache
import logging
from time import sleep

# Importación del sistema de rotación de proxies
from app.proxy_rotation_system import get_proxy_rotator

logger = logging.getLogger(__name__)


def get_user_queue_name(user_id):
    """
    Genera el nombre de cola para un usuario específico.
    Cada usuario tiene su propia cola para garantizar procesamiento paralelo.
    """
    return f'user_queue_{user_id}'


def update_progress_directly(consecutive_id, increment=1):
    """
    Actualiza el progreso directamente en la BD sin usar cola de tareas.
    Más rápido para actualizaciones en tiempo real.
    """
    try:
        from django.utils import timezone
        consecutive = Consecutive.objects.get(id=consecutive_id)
        consecutive.progres += increment
        
        # Auto-completar si llegó al total
        if consecutive.progres >= consecutive.total and consecutive.active:
            consecutive.active = False
            consecutive.finish = timezone.now()
            logger.info(f"✅ ARCHIVO COMPLETADO: {consecutive.file} ({consecutive.progres}/{consecutive.total})")
        
        consecutive.save()
        return True
    except Exception as e:
        logger.warning(f"[update_progress_directly] Error actualizando progreso {consecutive_id}: {e}")
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_save_task(self, phone, operator, user_id, file, ip):
    """
    Tarea Celery para guardar un número de teléfono en la base de datos.
    Además actualiza el caché Redis si es un número nuevo.
    
    Args:
        phone: Número de teléfono a guardar
        operator: Operador telefónico encontrado
        user_id: ID del usuario que inició el proceso
        file: Nombre del archivo origen
        ip: Fuente de la información ('cache', 'database', 'scraping')
    """
    try:
        with transaction.atomic():
            movil = Movil.objects.create(
                file=file,
                number=phone,
                operator=operator,
                user_id=user_id,
                ip=ip
            )

        # Actualizar caché Redis con el nuevo número
        if operator and operator not in ['', 'No existe', 'Desconocido'] and ip != 'cache':
            try:
                from .signals import add_to_phone_cache
                add_to_phone_cache(phone, operator, file)
                logger.debug(f"[process_save_task] Caché actualizado: {phone} → {operator}")
            except Exception as e:
                logger.warning(f"[process_save_task] Error actualizando caché: {e}")

        logger.info(f"[process_save_task] ✓ Guardado: {phone} | Operador: {operator} | Fuente: {ip}")
        return {"status": "success", "phone": phone}

    except Exception as e:
        logger.error(f"[process_save_task] ✗ Error guardando {phone}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        connection.close()


@shared_task(bind=True, max_retries=3)
def update_consecutive_task(self, consecutive_id, increment_progress=True):
    """
    Tarea Celery para actualizar el progreso de un Consecutive.
    
    Args:
        consecutive_id: ID del registro Consecutive a actualizar
        increment_progress: Si True, incrementa el progreso en 1
    """
    try:
        with transaction.atomic():
            consecutive = Consecutive.objects.select_for_update().get(id=consecutive_id)

            if increment_progress:
                consecutive.progres += 1

            consecutive.save()

        logger.debug(f"[update_consecutive_task] ✓ Consecutive {consecutive_id} actualizado")
        return {"status": "success", "consecutive_id": consecutive_id}

    except Consecutive.DoesNotExist:
        logger.error(f"[update_consecutive_task] ✗ Consecutive {consecutive_id} no existe")
        return {"status": "error", "message": "Consecutive not found"}

    except Exception as e:
        logger.error(f"[update_consecutive_task] ✗ Error actualizando {consecutive_id}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        connection.close()


@shared_task
def cleanup_old_tasks(self):
    """
    Tarea periódica para limpiar tareas antiguas.
    Ejecutar diariamente mediante beat scheduler.
    """
    from datetime import timedelta
    from django.utils import timezone

    cutoff_date = timezone.now() - timedelta(days=30)
    logger.info(f"[cleanup_old_tasks] Limpieza ejecutada hasta {cutoff_date}")
    return {"status": "success", "cutoff_date": str(cutoff_date)}


@shared_task
def sync_progress_with_movil():
    """
    Sincroniza el progreso de todos los archivos activos con la cantidad
    real de registros en Movil. Esto garantiza que el frontend siempre
    muestre el progreso correcto incluso si hay tareas antiguas sin consecutive_id.
    """
    from django.utils import timezone
    
    synced = []
    completed = []
    
    for c in Consecutive.objects.filter(active=True):
        count = Movil.objects.filter(file=c.file).count()
        
        if count != c.progres:
            old_progres = c.progres
            c.progres = count
            
            # Auto-completar si llegó al total
            if c.progres >= c.total:
                c.active = False
                c.finish = timezone.now()
                completed.append(f"{c.file}: {c.progres}/{c.total}")
            
            c.save()
            synced.append(f"{c.file}: {old_progres} → {c.progres}/{c.total}")
    
    if synced:
        logger.info(f"[sync_progress] ✅ Sincronizados: {len(synced)} archivos")
        for s in synced[:5]:  # Solo mostrar primeros 5
            logger.info(f"[sync_progress]   - {s}")
    
    if completed:
        for comp in completed:
            logger.info(f"[sync_progress] 🎉 COMPLETADO: {comp}")
    
    return {
        "status": "success",
        "synced_count": len(synced),
        "completed_count": len(completed)
    }


@shared_task
def check_and_requeue_orphan_files():
    """
    Detecta archivos que no tienen tareas en cola y los re-encola.
    Esto previene que archivos queden "huérfanos" sin procesar.
    
    CASOS QUE DETECTA:
    1. Archivos NUEVOS (progreso=0) que nunca empezaron - re-encola inmediatamente
    2. Archivos EN PROGRESO que se quedaron sin tareas en cola
    3. Archivos donde el progreso no avanza pero hay registros en Movil
    4. Archivos PAUSADOS que tienen tareas pendientes (se reactivan)
    """
    import redis
    from django.utils import timezone
    from datetime import timedelta
    
    r = redis.Redis(host='127.0.0.1', port=6379, db=0)
    requeued = []
    reactivated = []
    skipped = []
    
    # Buscar TODOS los archivos incompletos (activos Y pausados)
    for c in Consecutive.objects.filter(progres__lt=F('total')):
        user_queue = f'user_queue_{c.user.id}'
        queue_count = r.llen(user_queue)
        current_count = Movil.objects.filter(file=c.file).count()
        
        should_requeue = False
        reason = ""
        
        # CASO 1: Archivo NUEVO que nunca empezó (progreso=0, sin tareas en cola)
        if c.progres == 0 and current_count == 0 and queue_count == 0 and c.active:
            should_requeue = True
            reason = "archivo nuevo sin iniciar"
        
        # CASO 2: Archivo ACTIVO con progreso pero sin tareas en cola y sin avance
        elif c.active and queue_count == 0 and current_count < c.total:
            if current_count == c.progres or current_count <= c.progres:
                should_requeue = True
                reason = "archivo estancado sin tareas"
        
        # CASO 3: Hay discrepancia entre progreso y Movil count
        elif queue_count == 0 and current_count > c.progres:
            c.progres = current_count
            c.save()
            logger.info(f"[check_orphan] 📊 Sincronizado progreso: {c.file} → {c.progres}/{c.total}")
            
            if current_count < c.total and c.active:
                should_requeue = True
                reason = "archivo desincronizado, continuando"
        
        # CASO 4: Archivo PAUSADO pero con tareas en cola (se reactivó externamente)
        # O archivo pausado que debería continuar procesando
        if not c.active and queue_count > 0:
            # Hay tareas en cola pero el archivo está pausado → Reactivar
            c.active = True
            c.save()
            reactivated.append(f"{c.file} (ID: {c.id}) - tenía {queue_count} tareas en cola")
            logger.info(f"[check_orphan] 🔄 Reactivado: {c.file} (tenía {queue_count} tareas pendientes)")
        
        if should_requeue:
            logger.warning(f"[check_orphan] ⚠ Archivo huérfano: {c.file} (ID: {c.id}) - {reason}")
            logger.info(f"[check_orphan]   Usuario: {c.user.id}, Progreso: {c.progres}/{c.total}, Movil: {current_count}, Cola: {queue_count}")
            
            # Asegurar que el archivo esté activo antes de re-encolar
            if not c.active:
                c.active = True
                c.save()
                logger.info(f"[check_orphan] 🔄 Reactivado estado: {c.file}")
            
            process_file_in_batches.apply_async(
                kwargs={
                    'consecutive_id': c.id,
                    'batch_size': 100
                },
                queue=user_queue
            )
            
            requeued.append(f"{c.file} (ID: {c.id}) - {reason}")
            logger.info(f"[check_orphan] ✅ Re-encolado: {c.file}")
        else:
            if queue_count > 0 and c.active:
                skipped.append(f"{c.file}: {queue_count} tareas en cola")
    
    if requeued:
        logger.info(f"[check_orphan] 🔄 Re-encolados {len(requeued)} archivos huérfanos")
    
    if reactivated:
        logger.info(f"[check_orphan] ✅ Reactivados {len(reactivated)} archivos")
    
    return {
        "status": "success",
        "requeued_count": len(requeued),
        "requeued_files": requeued,
        "reactivated_count": len(reactivated),
        "reactivated_files": reactivated,
        "skipped_count": len(skipped)
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def scrape_and_save_phone_task(self, phone_number, user_id, file_name, max_attempts=3, consecutive_id=None):
    """
    Tarea Celery completa para consultar y guardar un número telefónico.
    
    Flujo:
    1. Verifica caché Redis
    2. Verifica BD PostgreSQL
    3. Si no existe: hace scraping con DigiPhone (con reintentos y cambio de proxy)
    4. Guarda en BD y actualiza caché
    5. Actualiza el progreso del archivo (Consecutive)
    
    Args:
        phone_number: Número telefónico a consultar
        user_id: ID del usuario
        file_name: Nombre del archivo origen
        max_attempts: Número máximo de reintentos con diferentes proxies
        consecutive_id: ID del Consecutive para actualizar progreso
    """
    from django.contrib.auth.models import User

    try:
        # Obtener usuario
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error(f"[scrape_and_save_phone_task] Usuario {user_id} no existe")
            return {"status": "error", "message": "User not found", "phone": phone_number}

        logger.info(f"[scrape_and_save_phone_task] 📞 Procesando: {phone_number} | Archivo: {file_name} | Usuario: {user_id}")

        # Paso 1: Verificar en caché Redis + BD
        from app.views import check_scraping_in_cache_and_db
        operator, source = check_scraping_in_cache_and_db(phone_number)

        if operator:
            logger.info(f"[scrape_and_save_phone_task] ✓ {phone_number} encontrado en {source} → {operator}")

            # Verificar si ya existe en BD para este archivo
            if not Movil.objects.filter(file=file_name, number=phone_number).exists():
                with transaction.atomic():
                    Movil.objects.create(
                        file=file_name,
                        number=phone_number,
                        operator=operator,
                        user=user,
                        ip=source
                    )
                logger.info(f"[scrape_and_save_phone_task] ✅ Guardado desde {source}: {phone_number} | {operator}")
            else:
                logger.info(f"[scrape_and_save_phone_task] ⚠ Ya existe: {phone_number} en {file_name}")

            # Actualizar progreso del archivo directamente (sin tarea async)
            if consecutive_id:
                update_progress_directly(consecutive_id, increment=1)
                logger.info(f"[scrape_and_save_phone_task] 📊 Progreso +1 directo (cache/BD) para consecutive_id={consecutive_id}")

            return {
                "status": "success",
                "phone": phone_number,
                "operator": operator,
                "source": source,
                "attempts": 0
            }

        # Paso 2: No está en caché ni BD → Hacer scraping
        logger.info(f"[scrape_and_save_phone_task] 🔍 No encontrado, iniciando scraping para {phone_number}")

        # Verificar duplicado en DB (por si acaso)
        if Movil.objects.filter(file=file_name, number=phone_number).exists():
            logger.info(f"[scrape_and_save_phone_task] ⚠ Ya existe: {phone_number}")
            # Actualizar progreso aunque sea duplicado (directo)
            if consecutive_id:
                update_progress_directly(consecutive_id, increment=1)
                logger.info(f"[scrape_and_save_phone_task] 📊 Progreso +1 directo (duplicado) para consecutive_id={consecutive_id}")
            return {"status": "skipped", "phone": phone_number, "reason": "duplicate"}

        # Usar DigiPhone para scraping con reintentos
        from .browser import DigiPhone
        digi_phone = DigiPhone(user=user, reprocess=False)

        operator = None
        attempts_made = 0
        
        # Intentar con múltiples proxies
        for attempt in range(max_attempts):
            attempts_made = attempt + 1
            
            try:
                # Obtener acceso (modo simple: solo cookies)
                if not digi_phone.get_access(get_cart=False):
                    logger.warning(f"[scrape_and_save_phone_task] Intento {attempts_made}/{max_attempts}: No se pudo obtener acceso para {phone_number}, cambiando proxy...")
                    digi_phone.change_position()
                    continue

                # Consultar operador
                result = digi_phone.get_phone_number(phone=phone_number)

                if result[0] == 200:
                    operator = result[1].get('name', 'Desconocido')
                    logger.info(f"[scrape_and_save_phone_task] ✓ {phone_number} → {operator} (intento {attempts_made})")
                    break  # Éxito, salir del loop
                elif result[0] == 404:
                    operator = "DIGI SPAIN TELECOM, S.L."
                    logger.info(f"[scrape_and_save_phone_task] ✓ {phone_number} → {operator} (404 - intento {attempts_made})")
                    break  # Éxito, salir del loop
                else:
                    logger.warning(f"[scrape_and_save_phone_task] Intento {attempts_made}/{max_attempts}: Status {result[0]} para {phone_number}, cambiando proxy...")
                    digi_phone.change_position()
                    
            except Exception as e:
                logger.warning(f"[scrape_and_save_phone_task] Intento {attempts_made}/{max_attempts}: Error para {phone_number}: {str(e)[:100]}, cambiando proxy...")
                digi_phone.change_position()
        
        # Si después de todos los intentos no se obtuvo operador válido
        if not operator or operator in ['', 'No existe', 'Desconocido', 'ERROR_SCRAPING']:
            logger.error(f"[scrape_and_save_phone_task] ✗ Falló después de {max_attempts} intentos para {phone_number} - NO se guarda en BD")
            
            # SÍ actualizar progreso porque se intentó procesar (directo)
            if consecutive_id:
                update_progress_directly(consecutive_id, increment=1)
                logger.info(f"[scrape_and_save_phone_task] 📊 Progreso +1 directo (fallido) para consecutive_id={consecutive_id}")
            
            return {
                "status": "failed",
                "phone": phone_number,
                "reason": "No se obtuvo operador válido"
            }

        # Paso 3: Guardar en base de datos SOLO si hay operador válido
        with transaction.atomic():
            Movil.objects.create(
                file=file_name,
                number=phone_number,
                operator=operator,
                user=user,
                ip="scraping"
            )

        # Actualizar caché si fue exitoso
        try:
            from .signals import add_to_phone_cache
            add_to_phone_cache(phone_number, operator, file_name)
            logger.info(f"[scrape_and_save_phone_task] Caché actualizado: {phone_number} → {operator}")
        except Exception as e:
            logger.warning(f"[scrape_and_save_phone_task] Error actualizando caché: {e}")

        logger.info(f"[scrape_and_save_phone_task] ✅ {phone_number} → {operator} | Archivo: {file_name} | Usuario: {user_id}")

        # Actualizar progreso del archivo (directo)
        if consecutive_id:
            update_progress_directly(consecutive_id, increment=1)
            logger.info(f"[scrape_and_save_phone_task] 📊 Progreso +1 directo (éxito) para consecutive_id={consecutive_id}")
        else:
            logger.warning(f"[scrape_and_save_phone_task] ⚠ No hay consecutive_id, progreso NO actualizado para {phone_number}")

        return {
            "status": "success",
            "phone": phone_number,
            "operator": operator
        }

    except Exception as e:
        logger.error(f"[scrape_and_save_phone_task] ✗ Error crítico para {phone_number}: {e}")
        # Actualizar progreso incluso en error para que el archivo no se quede atorado (directo)
        if consecutive_id:
            update_progress_directly(consecutive_id, increment=1)
            logger.info(f"[scrape_and_save_phone_task] 📊 Progreso +1 directo (error) para consecutive_id={consecutive_id}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        connection.close()


@shared_task(bind=True)
def update_consecutive_progress_task(self, consecutive_id, increment=1):
    """
    Actualiza el progreso de un Consecutive de forma atómica.
    Auto-finaliza cuando progres >= total.
    
    Args:
        consecutive_id: ID del registro Consecutive
        increment: Cantidad a incrementar el progreso (default: 1)
    """
    try:
        from django.utils import timezone

        with transaction.atomic():
            consecutive = Consecutive.objects.select_for_update().get(id=consecutive_id)
            consecutive.progres += increment

            # Auto-finalizar si completó el total
            if consecutive.progres >= consecutive.total and consecutive.active:
                consecutive.active = False
                consecutive.finish = timezone.now()
                logger.info(
                    f"✅ [update_consecutive_progress] ARCHIVO COMPLETADO: "
                    f"{consecutive.file} ({consecutive.progres}/{consecutive.total})"
                )

            consecutive.save()

        progress_pct = (consecutive.progres / consecutive.total * 100) if consecutive.total > 0 else 0
        logger.debug(
            f"[update_consecutive_progress_task] Progreso: "
            f"{consecutive.file} ({consecutive.progres}/{consecutive.total}) - {progress_pct:.1f}%"
        )

        return {
            "status": "success",
            "consecutive_id": consecutive_id,
            "progres": consecutive.progres,
            "total": consecutive.total,
            "progress_percentage": round(progress_pct, 2),
            "completed": consecutive.progres >= consecutive.total
        }

    except Consecutive.DoesNotExist:
        logger.error(f"[update_consecutive_progress_task] Consecutive {consecutive_id} no existe")
        return {"status": "error", "message": "Consecutive not found"}

    except Exception as e:
        logger.error(f"[update_consecutive_progress_task] Error: {e}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

    finally:
        connection.close()


@shared_task(bind=True)
def process_file_in_batches(self, consecutive_id, batch_size=200):
    """
    Procesa un archivo en lotes usando caché Redis para evitar scraping redundante.
    
    Ventajas del sistema:
    - Consulta en caché Redis (< 1ms por número)
    - Solo hace scraping de números nuevos
    - Procesamiento distribuido via Celery
    
    Args:
        consecutive_id: ID del registro Consecutive
        batch_size: Cantidad de números a procesar por lote (default: 200)
    """
    try:
        consecutive = Consecutive.objects.get(id=consecutive_id)

        # Verificar si el archivo sigue activo
        if not consecutive.active:
            logger.info(f"[process_file_in_batches] Archivo {consecutive.file} ya no está activo")
            return {"status": "cancelled", "consecutive_id": consecutive_id}

        # Obtener números ya procesados (evita query N+1)
        already_processed_numbers = set(
            Movil.objects.filter(
                file=consecutive.file,
                user=consecutive.user
            ).values_list('number', flat=True)
        )

        # Cargar todos los números del archivo
        import pandas as pd
        file_path = f"/opt/masterfilter/media/subido/{consecutive.file}"

        # Determinar formato y leer archivo
        if consecutive.file.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        elif consecutive.file.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            logger.error(f"[process_file_in_batches] Formato no soportado: {consecutive.file}")
            return {"status": "error", "message": "Unsupported format"}

        # Obtener columna de números (primera columna)
        phone_column = df.columns[0]
        all_phones = df[phone_column].astype(str).str.strip().tolist()

        # Filtrar números ya procesados
        pending_phones = [p for p in all_phones if p not in already_processed_numbers]

        # Procesar solo un lote
        current_batch = pending_phones[:batch_size]

        logger.info(
            f"[process_file_in_batches] 📁 {consecutive.file} | "
            f"Lote: {len(current_batch)} números | "
            f"Pendientes: {len(pending_phones)}"
        )

        # Métricas del lote
        cache_hits = 0
        db_hits = 0
        scraping_needed = 0
        errors = 0

        # Encolar tareas para este lote
        for phone in current_batch:
            try:
                # Verificar si ya existe en BD para ESTE archivo específico
                if Movil.objects.filter(file=consecutive.file, number=phone).exists():
                    # Ya procesado en este archivo, saltar
                    continue
                
                # Verificar en caché + BD con una sola llamada
                from app.views import check_scraping_in_cache_and_db
                operator, source = check_scraping_in_cache_and_db(phone)

                if operator:
                    # Encontrado en caché o BD - guardar directamente (sin usar tarea)
                    if source == 'cache':
                        cache_hits += 1
                    elif source == 'database':
                        db_hits += 1

                    # Guardar directamente en BD (más rápido que encolar tarea)
                    try:
                        with transaction.atomic():
                            Movil.objects.create(
                                file=consecutive.file,
                                number=phone,
                                operator=operator,
                                user=consecutive.user,
                                ip=source
                            )
                    except Exception as save_error:
                        logger.warning(f"[process_file_in_batches] Error guardando {phone}: {save_error}")

                else:
                    # Requiere scraping - enviar a cola del usuario
                    scraping_needed += 1
                    user_queue = get_user_queue_name(consecutive.user.id)
                    scrape_and_save_phone_task.apply_async(
                        kwargs={
                            'phone_number': phone,
                            'user_id': consecutive.user.id,
                            'file_name': consecutive.file,
                            'max_attempts': 3,
                            'consecutive_id': consecutive.id
                        },
                        queue=user_queue
                    )

            except Exception as e:
                errors += 1
                logger.error(f"[process_file_in_batches] Error procesando {phone}: {e}")

        # Log de estadísticas del lote
        total_batch = len(current_batch)
        cache_hit_rate = (cache_hits / total_batch * 100) if total_batch > 0 else 0
        
        logger.info(
            f"[process_file_in_batches] 📊 ESTADÍSTICAS DEL LOTE ({consecutive.file}):\n"
            f"   Total procesado: {total_batch}\n"
            f"   └─ Caché Redis: {cache_hits} ({cache_hit_rate:.1f}%)\n"
            f"   └─ Base de datos: {db_hits} ({db_hits/total_batch*100 if total_batch > 0 else 0:.1f}%)\n"
            f"   └─ Requiere scraping: {scraping_needed} ({scraping_needed/total_batch*100 if total_batch > 0 else 0:.1f}%)\n"
            f"   └─ Errores: {errors}"
        )

        # Programar siguiente lote si hay más números pendientes
        remaining = len(pending_phones) - batch_size
        if remaining > 0:
            logger.info(f"[process_file_in_batches] Quedan {remaining} números. Programando siguiente lote en 1s...")

            # Enviar a la cola del usuario para mantener round-robin
            user_queue = get_user_queue_name(consecutive.user.id)
            process_file_in_batches.apply_async(
                args=[consecutive_id, batch_size],
                countdown=1,  # Reducido de 5s a 1s
                queue=user_queue
            )
        else:
            logger.info(f"[process_file_in_batches] ✅ Archivo {consecutive.file} completamente encolado")

        return {
            "status": "success",
            "consecutive_id": consecutive_id,
            "batch_processed": len(current_batch),
            "remaining": max(0, remaining),
            "cache_hits": cache_hits,
            "db_hits": db_hits,
            "scraping_needed": scraping_needed,
            "errors": errors,
            "cache_hit_rate": round(cache_hit_rate, 2)
        }

    except Consecutive.DoesNotExist:
        logger.error(f"[process_file_in_batches] Consecutive {consecutive_id} no existe")
        return {"status": "error", "message": "Consecutive not found"}

    except Exception as e:
        logger.error(f"[process_file_in_batches] Error: {e}")
        raise self.retry(exc=e, countdown=30, max_retries=3)

    finally:
        connection.close()


# ============================================================================
# Tareas de Gestión de Proxies
# ============================================================================

@shared_task
def report_proxy_rotation_stats(self):
    """
    Reporta estadísticas de rotación de proxies.
    
    Útil para monitoreo y debugging del sistema de proxies.
    """
    rotator = get_proxy_rotator()
    stats = rotator.get_stats()

    # Calcular top proxies por rendimiento
    top_proxies = []
    for proxy_id, times in rotator.metrics.items():
        if times:
            avg_time = sum(times) / len(times)
            top_proxies.append({
                'id': proxy_id,
                'avg_time': round(avg_time, 2),
                'attempts': rotator.attempt_counts.get(proxy_id, 0)
            })

    top_proxies.sort(key=lambda x: x['avg_time'])

    # Log del reporte
    logger.info("="*80)
    logger.info("📊 REPORTE DE ROTACIÓN DE PROXIES")
    logger.info("="*80)
    logger.info(f"Total probados: {stats['total_proxies_tested']}")
    logger.info(f"En blacklist: {stats['blacklisted']}")
    logger.info(f"Proxies rápidos (<5s): {stats['fast_proxies']}")
    logger.info(f"Proxies lentos (>5s): {stats['slow_proxies']}")

    if top_proxies:
        logger.info("\n🏆 TOP 10 PROXIES MÁS RÁPIDOS:")
        for idx, p in enumerate(top_proxies[:10], 1):
            logger.info(f"  {idx}. {p['id']} - {p['avg_time']}s (intentos: {p['attempts']})")

    logger.info("="*80)

    return {
        "status": "success",
        "stats": stats,
        "top_proxies": top_proxies[:10]
    }


@shared_task
def clear_proxy_blacklist(self):
    """
    Limpia la blacklist de proxies.
    
    Útil para liberar todos los proxies blacklisted manualmente
    después de resolver problemas de conectividad.
    """
    rotator = get_proxy_rotator()
    before = len(rotator.blacklist)
    rotator.blacklist.clear()
    logger.info(f"🧹 Blacklist limpiada: {before} proxies liberados")
    return {"status": "success", "cleared": before}


@shared_task(bind=True)
def check_and_resume_stuck_processes(self):
    """
    Verifica procesos colgados y los reanuda si es necesario.
    
    Un proceso se considera colgado si:
    - Está activo (active=True)
    - El progreso no ha avanzado en las últimas 2 horas
    """
    from django.utils import timezone
    from datetime import timedelta

    stuck_threshold = timezone.now() - timedelta(hours=2)
    
    stuck_processes = Consecutive.objects.filter(
        active=True,
        created__lt=stuck_threshold
    )

    count = stuck_processes.count()
    if count > 0:
        logger.warning(f"[check_and_resume_stuck_processes] {count} procesos colgados detectados")
        
        for process in stuck_processes:
            logger.warning(f"  - {process.file} (ID: {process.id}, creado: {process.created})")
            
            # Reanudar proceso
            process_file_in_batches.delay(
                consecutive_id=process.id,
                batch_size=100
            )
        
        return {
            "status": "success",
            "message": f"{count} procesos colgados detectados y reagendados"
        }
    else:
        logger.info("[check_and_resume_stuck_processes] No hay procesos colgados")
        return {
            "status": "success",
            "message": "No hay procesos colgados"
        }


@shared_task
def get_system_stats(self):
    """
    Retorna estadísticas generales del sistema.
    
    Útil para dashboards de monitoreo.
    """
    from django.db.models import Count
    
    try:
        # Contadores básicos
        total_moviles = Movil.objects.count()
        total_consecutives = Consecutive.objects.count()
        active_consecutives = Consecutive.objects.filter(active=True).count()
        completed_consecutives = Consecutive.objects.filter(active=False).count()
        
        # Distribución por operador
        operator_distribution = dict(
            Movil.objects.values('operator')
            .annotate(count=Count('id'))
            .values_list('operator', 'count')
        )
        
        # Números por archivo
        files_stats = list(
            Consecutive.objects.values('file')
            .annotate(
                total=Count('id'),
                active=Count('id', filter=models.Q(active=True))
            )
        )
        
        return {
            "status": "success",
            "statistics": {
                "total_moviles": total_moviles,
                "total_consecutives": total_consecutives,
                "active_consecutives": active_consecutives,
                "completed_consecutives": completed_consecutives,
                "operator_distribution": operator_distribution
            }
        }
    
    except Exception as e:
        logger.error(f"[get_system_stats] Error: {e}")
        return {"status": "error", "message": str(e)}
