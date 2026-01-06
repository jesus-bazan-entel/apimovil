#!/usr/bin/env python
# validar_flujo_celery.py
"""
Script para validar el flujo completo de procesamiento con Celery
y detectar cuellos de botella o errores.
"""
import django
import os
import sys
import time
from datetime import datetime, timedelta

# Setup Django
sys.path.append('/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Consecutive, Movil, Proxy
from app.tasks import scrape_and_save_phone_task, update_consecutive_progress_task
from django.utils import timezone
from celery import current_app
import redis


class Colors:
    """Colores para terminal"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def verificar_redis():
    """Verifica conexión y estado de Redis"""
    print_header("1. VERIFICACIÓN DE REDIS")
    
    try:
        r = redis.Redis(host='127.0.0.1', port=6379, db=0)
        r.ping()
        print_success("Redis está corriendo")
        
        # Ver tareas en cola
        queue_length = r.llen('celery')
        if queue_length == 0:
            print_success(f"Cola de tareas: {queue_length} (limpia)")
        elif queue_length < 100:
            print_info(f"Cola de tareas: {queue_length} (normal)")
        elif queue_length < 1000:
            print_warning(f"Cola de tareas: {queue_length} (acumulándose)")
        else:
            print_error(f"Cola de tareas: {queue_length} (CRÍTICO - cuello de botella)")
        
        return True, queue_length
    except Exception as e:
        print_error(f"Redis no disponible: {e}")
        return False, 0


def verificar_celery_workers():
    """Verifica estado de workers de Celery"""
    print_header("2. VERIFICACIÓN DE CELERY WORKERS")
    
    try:
        # Obtener workers activos
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            print_error("No hay workers activos")
            return False, 0
        
        total_workers = len(stats)
        print_success(f"Workers activos: {total_workers}")
        
        for worker_name, worker_stats in stats.items():
            print_info(f"  └─ {worker_name}")
            print(f"     Pool: {worker_stats.get('pool', {}).get('implementation', 'N/A')}")
            print(f"     Concurrency: {worker_stats.get('pool', {}).get('max-concurrency', 'N/A')}")
        
        # Ver tareas activas
        active = inspect.active()
        if active:
            total_active = sum(len(tasks) for tasks in active.values())
            print_info(f"Tareas ejecutándose: {total_active}")
        else:
            print_info("Tareas ejecutándose: 0")
        
        # Ver tareas reservadas
        reserved = inspect.reserved()
        if reserved:
            total_reserved = sum(len(tasks) for tasks in reserved.values())
            print_info(f"Tareas reservadas: {total_reserved}")
        
        return True, total_workers
    except Exception as e:
        print_error(f"Error verificando Celery: {e}")
        return False, 0


def verificar_postgresql():
    """Verifica estado de PostgreSQL"""
    print_header("3. VERIFICACIÓN DE POSTGRESQL")
    
    try:
        from django.db import connection
        
        # Conexiones activas
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    state,
                    COUNT(*) as cantidad
                FROM pg_stat_activity 
                WHERE datname = 'db_apimovil'
                GROUP BY state
                ORDER BY cantidad DESC;
            """)
            
            results = cursor.fetchall()
            print_info("Conexiones por estado:")
            for state, count in results:
                if state == 'idle' and count > 30:
                    print_warning(f"  └─ {state}: {count} (muchas idle)")
                elif state == 'active' and count > 50:
                    print_warning(f"  └─ {state}: {count} (alta actividad)")
                else:
                    print(f"  └─ {state}: {count}")
            
            # Queries lentas
            cursor.execute("""
                SELECT 
                    COUNT(*) as slow_queries
                FROM pg_stat_activity 
                WHERE datname = 'db_apimovil'
                  AND state = 'active'
                  AND now() - query_start > interval '5 seconds';
            """)
            
            slow_queries = cursor.fetchone()[0]
            if slow_queries > 0:
                print_warning(f"Queries lentas (>5s): {slow_queries}")
            else:
                print_success("No hay queries lentas")
        
        return True
    except Exception as e:
        print_error(f"Error verificando PostgreSQL: {e}")
        return False


def test_tarea_celery():
    """Envía una tarea de prueba a Celery"""
    print_header("4. TEST DE TAREA CELERY")
    
    try:
        # Enviar tarea de prueba (número ficticio)
        test_phone = "999999999"
        
        print_info(f"Enviando tarea de prueba: {test_phone}")
        start_time = time.time()
        
        result = scrape_and_save_phone_task.delay(
            phone_number=test_phone,
            user_id=187,  # Ajustar según tu BD
            file_name="TEST_FLOW_VALIDATION.txt",
            max_attempts=1
        )
        
        print_info(f"Tarea encolada con ID: {result.id}")
        
        # Esperar resultado (timeout 30s)
        try:
            final_result = result.get(timeout=30)
            elapsed = time.time() - start_time
            
            print_success(f"Tarea completada en {elapsed:.2f}s")
            print_info(f"Resultado: {final_result}")
            
            # Verificar en BD
            from django.db import connection
            connection.close()  # Cerrar conexión anterior
            
            movil = Movil.objects.filter(
                number=test_phone,
                file="TEST_FLOW_VALIDATION.txt"
            ).first()
            
            if movil:
                print_success(f"Registro guardado en BD correctamente")
                print_info(f"  └─ Operador: {movil.operator}")
                # Limpiar registro de prueba
                movil.delete()
                print_info("Registro de prueba eliminado")
            else:
                print_warning("No se encontró registro en BD")
            
            return True, elapsed
        except Exception as timeout_err:
            print_error(f"Timeout esperando resultado: {timeout_err}")
            return False, 30
            
    except Exception as e:
        print_error(f"Error en test de tarea: {e}")
        return False, 0


def analizar_archivo_en_proceso(consecutive_id=None):
    """Analiza un archivo que está siendo procesado"""
    print_header("5. ANÁLISIS DE ARCHIVO EN PROCESO")
    
    from django.db.models import F
    
    if consecutive_id:
        try:
            consecutive = Consecutive.objects.get(id=consecutive_id)
        except Consecutive.DoesNotExist:
            print_error(f"Archivo con ID {consecutive_id} no encontrado")
            return
    else:
        # Buscar archivo activo más reciente
        consecutive = Consecutive.objects.filter(
            active=True,
            progres__lt=F('total')
        ).order_by('-created').first()
        
        if not consecutive:
            print_info("No hay archivos en proceso")
            return
    
    print_info(f"Analizando: {consecutive.file} (ID: {consecutive.id})")
    
    # Información básica
    progreso_pct = (consecutive.progres / consecutive.total * 100) if consecutive.total > 0 else 0
    print(f"\n📊 Progreso: {consecutive.progres}/{consecutive.total} ({progreso_pct:.1f}%)")
    
    # Velocidad de procesamiento
    moviles = Movil.objects.filter(
        file=consecutive.file,
        user=consecutive.user
    ).order_by('-fecha_hora')[:50]
    
    moviles_list = list(moviles)
    
    if len(moviles_list) >= 2:
        primer_registro = moviles_list[-1]
        ultimo_registro = moviles_list[0]
        
        tiempo_transcurrido = ultimo_registro.fecha_hora - primer_registro.fecha_hora
        
        if tiempo_transcurrido.total_seconds() > 0:
            velocidad = len(moviles_list) / (tiempo_transcurrido.total_seconds() / 60)
            
            print(f"\n⏱️  Velocidad actual:")
            print(f"  └─ {velocidad:.1f} números/minuto")
            
            # Tiempo estimado
            pendientes = consecutive.total - consecutive.progres
            if velocidad > 0:
                tiempo_estimado_min = pendientes / velocidad
                horas = int(tiempo_estimado_min // 60)
                minutos = int(tiempo_estimado_min % 60)
                
                print(f"  └─ Tiempo estimado: {horas}h {minutos}m para completar")
                
                if velocidad < 10:
                    print_error("Velocidad CRÍTICA (<10 números/min)")
                elif velocidad < 30:
                    print_warning("Velocidad BAJA (<30 números/min)")
                else:
                    print_success(f"Velocidad BUENA (>30 números/min)")
    
    # Análisis de errores
    total_moviles = len(moviles_list)
    if total_moviles > 0:
        errores = sum(1 for m in moviles_list if m.operator in ['ERROR_SCRAPING', 'No existe', None, ''])
        tasa_error = (errores / total_moviles * 100)
        
        print(f"\n📈 Tasa de éxito:")
        print(f"  └─ Exitosos: {total_moviles - errores}/{total_moviles}")
        print(f"  └─ Errores: {errores}/{total_moviles} ({tasa_error:.1f}%)")
        
        if tasa_error > 50:
            print_error("Tasa de error CRÍTICA (>50%)")
        elif tasa_error > 20:
            print_warning("Tasa de error ALTA (>20%)")
        else:
            print_success("Tasa de error ACEPTABLE (<20%)")
    
    # Verificar última actividad
    ultimo_movil = Movil.objects.filter(
        file=consecutive.file,
        user=consecutive.user
    ).order_by('-fecha_hora').first()
    
    if ultimo_movil:
        tiempo_sin_actividad = timezone.now() - ultimo_movil.fecha_hora
        
        print(f"\n🕐 Última actividad: hace {tiempo_sin_actividad}")
        
        if tiempo_sin_actividad > timedelta(minutes=10):
            print_error("Sin actividad por >10 minutos - Posible problema")
        elif tiempo_sin_actividad > timedelta(minutes=5):
            print_warning("Sin actividad por >5 minutos")
        else:
            print_success("Actividad reciente")


def diagnostico_completo(consecutive_id=None):
    """Ejecuta diagnóstico completo del flujo"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     VALIDACIÓN COMPLETA DEL FLUJO CELERY                   ║")
    print("║     apimovil - Diagnóstico de Procesamiento                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    resultados = {}
    
    # 1. Redis
    redis_ok, queue_length = verificar_redis()
    resultados['redis'] = redis_ok
    resultados['queue_length'] = queue_length
    
    # 2. Celery Workers
    workers_ok, num_workers = verificar_celery_workers()
    resultados['celery'] = workers_ok
    resultados['num_workers'] = num_workers
    
    # 3. PostgreSQL
    pg_ok = verificar_postgresql()
    resultados['postgresql'] = pg_ok
    
    # 4. Test de tarea
    test_ok, test_time = test_tarea_celery()
    resultados['test_task'] = test_ok
    resultados['test_time'] = test_time
    
    # 5. Análisis de archivo
    analizar_archivo_en_proceso(consecutive_id)
    
    # Resumen final
    print_header("RESUMEN FINAL")
    
    all_ok = all([
        resultados['redis'],
        resultados['celery'],
        resultados['postgresql'],
        resultados['test_task']
    ])
    
    if all_ok:
        print_success("TODOS LOS COMPONENTES FUNCIONAN CORRECTAMENTE")
    else:
        print_error("SE DETECTARON PROBLEMAS EN EL SISTEMA")
    
    print("\n📊 Estado de componentes:")
    print(f"  Redis: {'✓' if resultados['redis'] else '✗'}")
    print(f"  Celery Workers: {'✓' if resultados['celery'] else '✗'} ({resultados['num_workers']} workers)")
    print(f"  PostgreSQL: {'✓' if resultados['postgresql'] else '✗'}")
    print(f"  Test de tarea: {'✓' if resultados['test_task'] else '✗'} ({resultados['test_time']:.2f}s)")
    
    # Cuellos de botella detectados
    print("\n🔍 Cuellos de botella detectados:")
    
    cuellos_botella = []
    
    if queue_length > 1000:
        cuellos_botella.append(f"Cola de Redis muy grande ({queue_length} tareas)")
    
    if num_workers < 1:
        cuellos_botella.append(f"Pocos workers ({num_workers} workers)")
    
    if test_time > 10:
        cuellos_botella.append(f"Tareas lentas (>{test_time:.2f}s por tarea)")
    
    if cuellos_botella:
        for cuello in cuellos_botella:
            print_warning(f"  └─ {cuello}")
    else:
        print_success("  └─ No se detectaron cuellos de botella")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    from django.db.models import F
    from django.db import models
    
    consecutive_id = None
    if len(sys.argv) > 1:
        try:
            consecutive_id = int(sys.argv[1])
        except ValueError:
            print("Uso: python validar_flujo_celery.py [consecutive_id]")
            print("Ejemplo: python validar_flujo_celery.py 1052")
            sys.exit(1)
    
    diagnostico_completo(consecutive_id)
