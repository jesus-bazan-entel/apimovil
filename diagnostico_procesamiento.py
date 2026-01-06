# diagnostico_procesamiento.py
import django
import os
import sys

# Setup Django
sys.path.append('/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Consecutive, Movil, Proxy, BlockIp
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.utils import timezone

def diagnosticar_archivo(consecutive_id):
    """
    Diagnóstica el estado de un archivo que se detuvo
    """
    try:
        # Obtener información del archivo
        consecutive = Consecutive.objects.get(id=consecutive_id)
        
        print(f"{'='*80}")
        print(f"DIAGNÓSTICO DEL ARCHIVO: {consecutive.file}")
        print(f"{'='*80}\n")
        
        # 1. Información básica
        print(f"📋 INFORMACIÓN BÁSICA:")
        print(f"   ID: {consecutive.id}")
        print(f"   Usuario: {consecutive.user}")
        print(f"   Número consecutivo: {consecutive.num}")
        print(f"   Archivo: {consecutive.file}")
        print(f"   Fecha creación: {consecutive.created}")
        print(f"   Estado: {consecutive.status_display} ({consecutive.status})")
        print(f"   Activo: {'Sí' if consecutive.active else 'No'}")
        print(f"   Registros totales: {consecutive.total}")
        print(f"   Registros procesados: {consecutive.progres}")
        print(f"   Progreso: {consecutive.progress_percentage:.2f}%")
        
        # 2. Tiempo de procesamiento
        now = timezone.now()
        if consecutive.finish:
            print(f"\n⏱️  TIEMPO:")
            print(f"   Fecha finalización: {consecutive.finish}")
            print(f"   Tiempo total: {consecutive.finish - consecutive.created}")
        else:
            tiempo_transcurrido = now - consecutive.created
            print(f"\n⏱️  TIEMPO:")
            print(f"   Tiempo transcurrido: {tiempo_transcurrido}")
            
            if consecutive.active:
                print(f"   Estado: En progreso")
            else:
                print(f"   Estado: Detenido/Pausado")
        
        # 3. Análisis de registros procesados
        moviles = Movil.objects.filter(file=consecutive.file, user=consecutive.user)
        total_moviles = moviles.count()
        
        print(f"\n📊 ANÁLISIS DE REGISTROS:")
        print(f"   Registros en BD (Movil): {total_moviles}")
        print(f"   Procesados exitosos: {moviles.exclude(operator__isnull=True).exclude(operator='').count()}")
        print(f"   Con error/sin operador: {moviles.filter(operator__isnull=True).count() + moviles.filter(operator='').count()}")
        print(f"   Pendientes: {consecutive.total - consecutive.progres}")
        print(f"   Diferencia (progres vs BD): {consecutive.progres - total_moviles}")
        
        # 4. Últimos registros procesados
        last_processed = moviles.order_by('-id')[:10]
        print(f"\n📱 ÚLTIMOS 10 REGISTROS PROCESADOS:")
        for i, record in enumerate(last_processed, 1):
            status = "✓" if record.operator else "✗"
            operator = record.operator if record.operator else "SIN OPERADOR"
            print(f"   {i:2d}. {status} {record.number} -> {operator} | {record.fecha_hora}")
        
        # 5. Estadísticas por operador
        from django.db.models import Count
        operators_stats = moviles.exclude(operator__isnull=True).exclude(operator='').values('operator').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        print(f"\n📈 TOP 10 OPERADORES ENCONTRADOS:")
        for i, stat in enumerate(operators_stats, 1):
            print(f"   {i:2d}. {stat['operator']}: {stat['count']} números ({stat['count']/total_moviles*100:.1f}%)")
        
        # 6. Verificar proxies del usuario
        proxies = Proxy.objects.filter(user=consecutive.user)
        print(f"\n🌐 PROXIES CONFIGURADOS PARA {consecutive.user}:")
        print(f"   Total proxies: {proxies.count()}")
        for proxy in proxies:
            usernames_count = len([u.strip() for u in proxy.username.splitlines() if u.strip()])
            print(f"   - {proxy.ip}:{proxy.port_min} ({usernames_count} sesiones)")
        
        # 7. IPs bloqueadas
        blocked_ips = BlockIp.objects.filter(user=consecutive.user)
        if blocked_ips.exists():
            print(f"\n🚫 IPs BLOQUEADAS:")
            print(f"   Total: {blocked_ips.count()}")
            for block in blocked_ips[:5]:
                print(f"   - {block.ip_block} (Proxy: {block.proxy_ip.ip if block.proxy_ip else 'N/A'}, Reintentos: {block.reintent})")
        
        # 8. Verificar workers activos
        import subprocess
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
            workers = [line for line in result.stdout.split('\n') 
                      if 'daphne' in line and 'apimovil' in line]
            print(f"\n🔧 WORKERS ACTIVOS:")
            if workers:
                for worker in workers:
                    parts = worker.split()
                    if len(parts) >= 11:
                        print(f"   PID: {parts[1]} | CPU: {parts[2]}% | MEM: {parts[3]}%")
            else:
                print(f"   ⚠️  NO SE ENCONTRARON WORKERS ACTIVOS")
        except:
            print(f"\n🔧 WORKERS: No se pudo verificar")
        
        # 9. Última actividad en logs
        try:
            with open('/opt/apimovil/logger.log', 'r') as f:
                lines = f.readlines()
                # Buscar líneas relacionadas con este archivo
                related_lines = [l for l in lines if consecutive.file in l]
                if related_lines:
                    print(f"\n📝 ÚLTIMA ACTIVIDAD EN LOGS:")
                    for line in related_lines[-5:]:
                        print(f"   {line.rstrip()}")
        except:
            pass
        
        # 10. Recomendaciones
        print(f"\n💡 RECOMENDACIONES:")
        
        if consecutive.status == 'paused':
            print(f"   ⚠️  El archivo está PAUSADO (active=False)")
            print(f"   → Ejecutar: UPDATE app_consecutive SET active=true WHERE id={consecutive_id};")
            print(f"   → O usar el botón de reanudar en el frontend")
        
        if consecutive.status == 'processing' and consecutive.active:
            # Verificar si realmente está procesando
            if total_moviles > 0:
                ultimo_registro = moviles.order_by('-fecha_hora').first()
                tiempo_sin_actividad = now - ultimo_registro.fecha_hora
                
                if tiempo_sin_actividad > timedelta(minutes=5):
                    print(f"   ⚠️  El archivo está marcado como 'procesando' pero sin actividad hace {tiempo_sin_actividad}")
                    print(f"   → Último registro: {ultimo_registro.fecha_hora}")
                    print(f"   → Verificar si los workers están corriendo")
                    print(f"   → Revisar logs: tail -f /opt/apimovil/daphne.log")
                else:
                    print(f"   ✓ El archivo está procesando activamente")
                    print(f"   → Último registro hace: {tiempo_sin_actividad}")
        
        if consecutive.progres >= consecutive.total:
            print(f"   ✓ El archivo está COMPLETADO")
            if not consecutive.finish:
                print(f"   → Actualizar fecha de finalización manualmente si es necesario")
        
        if proxies.count() == 0:
            print(f"   ⚠️  No hay proxies configurados para el usuario {consecutive.user}")
        
        pendientes = consecutive.total - consecutive.progres
        if pendientes > 0 and not consecutive.active:
            print(f"   📋 Hay {pendientes} registros pendientes")
            print(f"   → Para continuar procesamiento, activar el archivo")
        
        print(f"\n{'='*80}\n")
        
        return consecutive
        
    except Consecutive.DoesNotExist:
        print(f"❌ ERROR: No se encontró el archivo con ID {consecutive_id}")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def listar_archivos_activos():
    """
    Lista todos los archivos que están en procesamiento o pausados
    """
    # Archivos en procesamiento
    processing = Consecutive.objects.filter(active=True, progres__lt=models.F('total')).order_by('-created')
    
    # Archivos pausados
    paused = Consecutive.objects.filter(active=False, progres__lt=models.F('total'), progres__gt=0).order_by('-created')
    
    print(f"{'='*80}")
    print(f"ARCHIVOS EN PROCESAMIENTO")
    print(f"{'='*80}\n")
    
    if processing.exists():
        for f in processing:
            progreso = f.progress_percentage
            tiempo_transcurrido = timezone.now() - f.created
            
            # Verificar última actividad
            ultimo_movil = Movil.objects.filter(file=f.file, user=f.user).order_by('-fecha_hora').first()
            if ultimo_movil:
                tiempo_sin_actividad = timezone.now() - ultimo_movil.fecha_hora
                status_symbol = "⏸️" if tiempo_sin_actividad > timedelta(minutes=5) else "▶️"
            else:
                status_symbol = "⏸️"
            
            print(f"{status_symbol} ID: {f.id} | {f.file}")
            print(f"   Usuario: {f.user}")
            print(f"   Progreso: {f.progres}/{f.total} ({progreso:.1f}%)")
            print(f"   Creado: {f.created} (hace {tiempo_transcurrido})")
            if ultimo_movil:
                print(f"   Última actividad: hace {tiempo_sin_actividad}")
            print()
    else:
        print("No hay archivos procesando")
    
    print(f"\n{'='*80}")
    print(f"ARCHIVOS PAUSADOS")
    print(f"{'='*80}\n")
    
    if paused.exists():
        for f in paused:
            progreso = f.progress_percentage
            print(f"⏸️  ID: {f.id} | {f.file}")
            print(f"   Usuario: {f.user}")
            print(f"   Progreso: {f.progres}/{f.total} ({progreso:.1f}%)")
            print(f"   Creado: {f.created}")
            print()
    else:
        print("No hay archivos pausados")


def estadisticas_generales():
    """
    Muestra estadísticas generales del sistema
    """
    print(f"\n{'='*80}")
    print(f"ESTADÍSTICAS GENERALES DEL SISTEMA")
    print(f"{'='*80}\n")
    
    # Totales
    total_archivos = Consecutive.objects.count()
    total_numeros = Movil.objects.count()
    total_usuarios = User.objects.filter(consecutive__isnull=False).distinct().count()
    
    print(f"📊 TOTALES:")
    print(f"   Archivos procesados: {total_archivos}")
    print(f"   Números consultados: {total_numeros}")
    print(f"   Usuarios activos: {total_usuarios}")
    
    # Por estado
    completados = Consecutive.objects.filter(progres__gte=models.F('total')).count()
    procesando = Consecutive.objects.filter(active=True, progres__lt=models.F('total')).count()
    pausados = Consecutive.objects.filter(active=False, progres__lt=models.F('total'), progres__gt=0).count()
    
    print(f"\n📈 POR ESTADO:")
    print(f"   Completados: {completados}")
    print(f"   Procesando: {procesando}")
    print(f"   Pausados: {pausados}")
    
    # Últimos 7 días
    hace_7_dias = timezone.now() - timedelta(days=7)
    archivos_recientes = Consecutive.objects.filter(created__gte=hace_7_dias).count()
    numeros_recientes = Movil.objects.filter(fecha_hora__gte=hace_7_dias).count()
    
    print(f"\n📅 ÚLTIMOS 7 DÍAS:")
    print(f"   Archivos cargados: {archivos_recientes}")
    print(f"   Números procesados: {numeros_recientes}")
    
    # Top usuarios
    from django.db.models import Count
    top_usuarios = Consecutive.objects.values('user__username').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    print(f"\n👥 TOP 5 USUARIOS:")
    for i, user_stat in enumerate(top_usuarios, 1):
        print(f"   {i}. {user_stat['user__username']}: {user_stat['total']} archivos")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    from django.db.models import F
    from django.db import models
    
    if len(sys.argv) > 1:
        try:
            consecutive_id = int(sys.argv[1])
            diagnosticar_archivo(consecutive_id)
        except ValueError:
            print("Error: El ID debe ser un número")
            print("Uso: python diagnostico_procesamiento.py <consecutive_id>")
            print("Ejemplo: python diagnostico_procesamiento.py 1007")
    else:
        listar_archivos_activos()
        estadisticas_generales()
        print("\n💡 Para diagnóstico detallado de un archivo específico:")
        print("   python diagnostico_procesamiento.py <consecutive_id>")
        print("   Ejemplo: python diagnostico_procesamiento.py 1007")
