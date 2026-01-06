import django
import os
import sys
import time

sys.path.append('/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Consecutive, Movil
from django.contrib.auth.models import User

def obtener_numeros_pendientes(consecutive_id):
    """
    Obtiene los números que faltan procesar
    """
    consecutive = Consecutive.objects.get(id=consecutive_id)
    
    # Obtener números ya procesados
    procesados = set(Movil.objects.filter(
        file=consecutive.file,
        user=consecutive.user
    ).values_list('number', flat=True))
    
    print(f"Números procesados: {len(procesados)}")
    print(f"Total esperado: {consecutive.total}")
    print(f"Diferencia: {consecutive.total - len(procesados)}")
    
    return consecutive, procesados


def reiniciar_worker_manualmente(consecutive_id):
    """
    Reinicia manualmente el procesamiento de los números pendientes
    """
    import openpyxl
    from app.browser import DigiPhone
    
    consecutive, procesados = obtener_numeros_pendientes(consecutive_id)
    
    # RUTA CORREGIDA: Buscar en masterfilter
    file_path = f"/opt/masterfilter/media/subido/{consecutive.file}"
    
    # Si no está ahí, intentar otras ubicaciones comunes
    if not os.path.exists(file_path):
        paths_to_try = [
            f"/opt/apimovil/media/{consecutive.file}",
            f"/opt/apimovil/media/subido/{consecutive.file}",
            f"/opt/masterfilter/media/{consecutive.file}",
        ]
        
        for path in paths_to_try:
            if os.path.exists(path):
                file_path = path
                break
    
    print(f"\n📂 Archivo: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: No se encontró el archivo")
        return
    
    try:
        workbook = openpyxl.load_workbook(file_path)
        sheet = workbook.active
        
        # Obtener todos los números del archivo
        todos_numeros = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row[0]:  # Primera columna
                numero = str(row[0]).strip()
                # Limpiar el número (quitar espacios, guiones, etc)
                numero = ''.join(filter(str.isdigit, numero))
                if numero and numero not in procesados and len(numero) == 9:
                    todos_numeros.append(numero)
        
        print(f"\n📋 Números pendientes encontrados: {len(todos_numeros)}")
        
        if not todos_numeros:
            print("✓ No hay números pendientes, el archivo está completo")
            # Actualizar como completado
            consecutive.progres = consecutive.total
            consecutive.active = False
            from django.utils import timezone
            consecutive.finish = timezone.now()
            consecutive.save()
            print("✓ Archivo marcado como completado")
            return
        
        print(f"\n📱 Números a procesar:")
        for num in todos_numeros:
            print(f"  - {num}")
        
        confirmar = input(f"\n¿Procesar estos {len(todos_numeros)} números? (s/n): ")
        
        if confirmar.lower() != 's':
            print("Operación cancelada")
            return
        
        # Inicializar DigiPhone con el ID del usuario (no el username)
        print(f"\n🔄 Inicializando sistema de procesamiento...")
        print(f"   Usuario: {consecutive.user.username} (ID: {consecutive.user.id})")
        
        # FIX: Pasar el ID del usuario, no el username
        phone = DigiPhone(user=consecutive.user.id, reprocess=False)
        
        # Verificar que tiene proxies disponibles
        if len(phone.proxies) == 0:
            print("❌ Error: No hay proxies configurados")
            return
        
        print(f"✓ Proxies disponibles: {len(phone.proxies)}")
        
        # Resetear manualmente los health checks de proxies
        print("🔧 Reseteando circuit breaker de proxies...")
        for proxy_id in phone._proxy_health.keys():
            phone._proxy_health[proxy_id] = {
                "ssl_errors": 0,
                "connection_errors": 0,
                "last_error_time": None,
                "disabled_until": None
            }
        print("✓ Circuit breaker reseteado")
        
        # Obtener acceso
        print("\n🔑 Obteniendo acceso...")
        if not phone.get_access(get_cart=False):
            print("❌ Error obteniendo acceso")
            return
        print("✓ Acceso obtenido")
        
        # Procesar números
        print(f"\n▶️  Procesando {len(todos_numeros)} números...\n")
        
        exitosos = 0
        fallidos = 0
        
        for i, numero in enumerate(todos_numeros, 1):
            print(f"[{i}/{len(todos_numeros)}] Procesando {numero}...", end=" ", flush=True)
            
            max_intentos = 3
            success = False
            
            for intento in range(1, max_intentos + 1):
                if intento > 1:
                    phone.change_position()
                    time.sleep(1)
                
                status, result = phone.get_phone_number(phone=numero)
                
                if status == 200:
                    operator_name = result.get('name', 'Desconocido')
                    print(f"✓ {operator_name}")
                    
                    # Guardar en BD
                    Movil.objects.create(
                        file=consecutive.file,
                        number=numero,
                        operator=operator_name,
                        user=consecutive.user
                    )
                    
                    # Actualizar progreso
                    consecutive.progres += 1
                    consecutive.save()
                    
                    exitosos += 1
                    success = True
                    break
                
                elif status == 404 and (isinstance(result, dict) and result.get("message") == "Operator not found"):
                    operator_name = "DIGI SPAIN TELECOM, S.L."
                    print(f"✓ {operator_name}")
                    
                    Movil.objects.create(
                        file=consecutive.file,
                        number=numero,
                        operator=operator_name,
                        user=consecutive.user
                    )
                    
                    consecutive.progres += 1
                    consecutive.save()
                    
                    exitosos += 1
                    success = True
                    break
                
                elif status in [401, 498]:
                    print(f"🔑 Renovando cookies...", end=" ", flush=True)
                    if phone.get_access(get_cart=False):
                        continue
                
                # Si llegamos aquí, hubo error
                if intento < max_intentos:
                    print(f"⚠️ Reintento {intento}...", end=" ", flush=True)
            
            if not success:
                print(f"✗ FALLO después de {max_intentos} intentos")
                fallidos += 1
            
            # Pequeña pausa entre números
            time.sleep(0.5)
        
        # Resumen final
        print(f"\n{'='*60}")
        print(f"RESUMEN FINAL")
        print(f"{'='*60}")
        print(f"Total procesados: {len(todos_numeros)}")
        print(f"Exitosos: {exitosos}")
        print(f"Fallidos: {fallidos}")
        print(f"Progreso final: {consecutive.progres}/{consecutive.total}")
        
        # Si completó todo, marcar como terminado
        if consecutive.progres >= consecutive.total:
            from django.utils import timezone
            consecutive.finish = timezone.now()
            consecutive.active = False
            consecutive.save()
            print(f"\n✓ ARCHIVO COMPLETADO")
        
        print(f"{'='*60}\n")
        
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {file_path}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python reactivar_procesamiento.py <consecutive_id>")
        print("Ejemplo: python reactivar_procesamiento.py 1007")
        sys.exit(1)
    
    consecutive_id = int(sys.argv[1])
    reiniciar_worker_manualmente(consecutive_id)
