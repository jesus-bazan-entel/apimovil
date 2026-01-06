"""
Sistema automatizado de recuperación de archivos pendientes
Detecta archivos estancados y reprocesa números faltantes
"""

import django
import os
import sys
import time
import logging
from datetime import datetime, timedelta

sys.path.append('/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Consecutive, Movil
from django.utils import timezone
from django.db.models import Count

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/apimovil/auto_recuperacion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoRecuperacion:
    """
    Sistema de recuperación automática de archivos estancados
    """
    
    def __init__(self, inactividad_minutos=10, max_archivos_por_ciclo=5):
        """
        Args:
            inactividad_minutos: Minutos sin actividad para considerar estancado
            max_archivos_por_ciclo: Máximo de archivos a procesar por ciclo
        """
        self.inactividad_minutos = inactividad_minutos
        self.max_archivos_por_ciclo = max_archivos_por_ciclo
    
    def detectar_archivos_estancados(self):
        """
        Detecta archivos que están marcados como activos pero sin actividad reciente
        """
        logger.info("🔍 Buscando archivos estancados...")
        
        # Calcular el tiempo de corte
        tiempo_corte = timezone.now() - timedelta(minutes=self.inactividad_minutos)
        
        # Buscar archivos activos
        archivos_activos = Consecutive.objects.filter(
            active=True,
            progres__lt=models.F('total')  # No completados
        ).order_by('-created')
        
        archivos_estancados = []
        
        for archivo in archivos_activos:
            # Verificar última actividad en Movil
            ultimo_registro = Movil.objects.filter(
                file=archivo.file,
                user=archivo.user
            ).order_by('-fecha_hora').first()
            
            if ultimo_registro:
                if ultimo_registro.fecha_hora < tiempo_corte:
                    pendientes = archivo.total - archivo.progres
                    archivos_estancados.append({
                        'consecutive': archivo,
                        'pendientes': pendientes,
                        'ultima_actividad': ultimo_registro.fecha_hora,
                        'inactivo_minutos': int((timezone.now() - ultimo_registro.fecha_hora).total_seconds() / 60)
                    })
            else:
                # No tiene registros pero está activo
                archivos_estancados.append({
                    'consecutive': archivo,
                    'pendientes': archivo.total,
                    'ultima_actividad': None,
                    'inactivo_minutos': None
                })
        
        logger.info(f"✓ Encontrados {len(archivos_estancados)} archivos estancados")
        return archivos_estancados[:self.max_archivos_por_ciclo]
    
    def obtener_numeros_pendientes(self, consecutive):
        """
        Obtiene los números pendientes de un archivo
        """
        import openpyxl
        
        # Buscar el archivo Excel
        rutas_posibles = [
            f"/opt/masterfilter/media/subido/{consecutive.file}",
            f"/opt/apimovil/media/{consecutive.file}",
            f"/opt/apimovil/media/subido/{consecutive.file}",
            f"/opt/masterfilter/media/{consecutive.file}",
        ]
        
        file_path = None
        for ruta in rutas_posibles:
            if os.path.exists(ruta):
                file_path = ruta
                break
        
        if not file_path:
            logger.error(f"❌ No se encontró el archivo: {consecutive.file}")
            return None, []
        
        logger.info(f"📂 Archivo encontrado: {file_path}")
        
        try:
            # Obtener números ya procesados
            procesados = set(Movil.objects.filter(
                file=consecutive.file,
                user=consecutive.user
            ).values_list('number', flat=True))
            
            # Leer el archivo Excel
            workbook = openpyxl.load_workbook(file_path)
            sheet = workbook.active
            
            # Obtener números pendientes
            pendientes = []
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row[0]:
                    numero = str(row[0]).strip()
                    numero = ''.join(filter(str.isdigit, numero))
                    if numero and numero not in procesados and len(numero) == 9:
                        pendientes.append(numero)
            
            return file_path, pendientes
            
        except Exception as e:
            logger.error(f"❌ Error leyendo archivo: {e}")
            return file_path, []
    
    def procesar_numeros(self, consecutive, numeros):
        """
        Procesa una lista de números pendientes
        """
        from app.browser import DigiPhone
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 PROCESANDO ARCHIVO: {consecutive.file}")
        logger.info(f"   Usuario: {consecutive.user.username}")
        logger.info(f"   Números pendientes: {len(numeros)}")
        logger.info(f"{'='*60}\n")
        
        try:
            # Inicializar DigiPhone
            phone = DigiPhone(user=consecutive.user.id, reprocess=False)
            
            if len(phone.proxies) == 0:
                logger.error("❌ No hay proxies configurados")
                return False
            
            logger.info(f"✓ Proxies disponibles: {len(phone.proxies)}")
            
            # Resetear circuit breaker
            logger.info("🔧 Reseteando circuit breaker...")
            for proxy_id in phone._proxy_health.keys():
                phone._proxy_health[proxy_id] = {
                    "ssl_errors": 0,
                    "connection_errors": 0,
                    "last_error_time": None,
                    "disabled_until": None
                }
            
            # Obtener acceso
            logger.info("🔑 Obteniendo acceso...")
            if not phone.get_access(get_cart=False):
                logger.error("❌ Error obteniendo acceso")
                return False
            
            logger.info("✓ Acceso obtenido\n")
            
            # Procesar números
            exitosos = 0
            fallidos = 0
            
            for i, numero in enumerate(numeros, 1):
                logger.info(f"[{i}/{len(numeros)}] Procesando {numero}...")
                
                max_intentos = 3
                success = False
                
                for intento in range(1, max_intentos + 1):
                    if intento > 1:
                        phone.change_position()
                        time.sleep(1)
                    
                    status, result = phone.get_phone_number(phone=numero)
                    
                    if status == 200:
                        operator_name = result.get('name', 'Desconocido')
                        logger.info(f"  ✓ {operator_name}")
                        
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
                    
                    elif status == 404 and (isinstance(result, dict) and result.get("message") == "Operator not found"):
                        operator_name = "DIGI SPAIN TELECOM, S.L."
                        logger.info(f"  ✓ {operator_name}")
                        
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
                        logger.info("  🔑 Renovando cookies...")
                        if phone.get_access(get_cart=False):
                            continue
                    
                    if intento < max_intentos:
                        logger.info(f"  ⚠️ Reintento {intento}...")
                
                if not success:
                    logger.warning(f"  ✗ FALLO después de {max_intentos} intentos")
                    fallidos += 1
                
                time.sleep(0.5)
            
            # Resumen
            logger.info(f"\n{'='*60}")
            logger.info(f"RESUMEN DEL ARCHIVO: {consecutive.file}")
            logger.info(f"{'='*60}")
            logger.info(f"Exitosos: {exitosos}/{len(numeros)}")
            logger.info(f"Fallidos: {fallidos}/{len(numeros)}")
            logger.info(f"Progreso final: {consecutive.progres}/{consecutive.total}")
            
            # Marcar como completado si llegó al total
            if consecutive.progres >= consecutive.total:
                consecutive.finish = timezone.now()
                consecutive.active = False
                consecutive.save()
                logger.info("✓ ARCHIVO MARCADO COMO COMPLETADO")
            
            logger.info(f"{'='*60}\n")
            
            return exitosos > 0
            
        except Exception as e:
            logger.error(f"❌ Error procesando archivo: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def ejecutar_ciclo(self):
        """
        Ejecuta un ciclo completo de recuperación
        """
        logger.info(f"\n{'#'*60}")
        logger.info(f"# INICIANDO CICLO DE AUTO-RECUPERACIÓN")
        logger.info(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*60}\n")
        
        # Detectar archivos estancados
        archivos_estancados = self.detectar_archivos_estancados()
        
        if not archivos_estancados:
            logger.info("✓ No hay archivos estancados")
            return
        
        # Procesar cada archivo
        for info in archivos_estancados:
            consecutive = info['consecutive']
            pendientes_count = info['pendientes']
            
            logger.info(f"\n📋 Archivo detectado:")
            logger.info(f"   ID: {consecutive.id}")
            logger.info(f"   Nombre: {consecutive.file}")
            logger.info(f"   Usuario: {consecutive.user.username}")
            logger.info(f"   Progreso: {consecutive.progres}/{consecutive.total}")
            logger.info(f"   Pendientes: {pendientes_count}")
            logger.info(f"   Inactivo desde: {info['inactivo_minutos']} minutos")
            
            # Obtener números pendientes
            file_path, numeros_pendientes = self.obtener_numeros_pendientes(consecutive)
            
            if not numeros_pendientes:
                logger.warning(f"⚠️ No se encontraron números pendientes para {consecutive.file}")
                # Marcar como completado si no hay pendientes
                if consecutive.progres >= consecutive.total:
                    consecutive.active = False
                    consecutive.finish = timezone.now()
                    consecutive.save()
                    logger.info("✓ Archivo marcado como completado")
                continue
            
            # Procesar los números
            success = self.procesar_numeros(consecutive, numeros_pendientes)
            
            if success:
                logger.info(f"✓ Archivo {consecutive.file} procesado correctamente")
            else:
                logger.warning(f"⚠️ Hubo problemas procesando {consecutive.file}")
            
            # Pausa entre archivos
            time.sleep(2)
        
        logger.info(f"\n{'#'*60}")
        logger.info(f"# CICLO COMPLETADO")
        logger.info(f"{'#'*60}\n")


def main():
    """
    Función principal
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Sistema de auto-recuperación de archivos')
    parser.add_argument('--inactividad', type=int, default=10,
                       help='Minutos de inactividad para considerar estancado (default: 10)')
    parser.add_argument('--max-archivos', type=int, default=5,
                       help='Máximo de archivos a procesar por ciclo (default: 5)')
    parser.add_argument('--intervalo', type=int, default=15,
                       help='Intervalo en minutos entre ciclos (default: 15)')
    parser.add_argument('--once', action='store_true',
                       help='Ejecutar solo una vez y salir')
    
    args = parser.parse_args()
    
    recuperador = AutoRecuperacion(
        inactividad_minutos=args.inactividad,
        max_archivos_por_ciclo=args.max_archivos
    )
    
    if args.once:
        # Ejecutar solo una vez
        logger.info("Modo: Ejecución única")
        recuperador.ejecutar_ciclo()
    else:
        # Modo continuo
        logger.info(f"Modo: Continuo (intervalo: {args.intervalo} minutos)")
        logger.info(f"Inactividad considerada: {args.inactividad} minutos")
        logger.info(f"Máximo archivos por ciclo: {args.max_archivos}")
        
        while True:
            try:
                recuperador.ejecutar_ciclo()
                logger.info(f"⏰ Esperando {args.intervalo} minutos para el próximo ciclo...\n")
                time.sleep(args.intervalo * 60)
            except KeyboardInterrupt:
                logger.info("\n⏹️  Detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en el ciclo: {e}")
                import traceback
                logger.error(traceback.format_exc())
                logger.info(f"⏰ Esperando {args.intervalo} minutos antes de reintentar...\n")
                time.sleep(args.intervalo * 60)


if __name__ == "__main__":
    # Importar models aquí para evitar problemas de importación circular
    from django.db import models
    main()
