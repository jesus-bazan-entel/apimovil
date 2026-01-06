from django.apps import AppConfig
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def load_phone_cache_on_startup():
    """
    Carga el caché de números de teléfono al iniciar Django.
    Se ejecuta desde AppConfig.ready()
    """
    from .models import Movil
    
    try:
        # Verificar si el caché ya está cargado
        if cache.get('global_phone_cache') is not None:
            count = cache.get('global_phone_cache_count', 0)
            logger.info(f"[CACHE INIT] Caché ya existe con {count:,} números. Saltando inicialización.")
            return
    except Exception as e:
        logger.warning(f"[CACHE INIT] No se pudo verificar caché existente: {e}. Continuando con carga...")

    logger.info("=" * 80)
    logger.info("🔄 [CACHE INIT] Iniciando carga de caché de números (30 días)...")
    logger.info("=" * 80)

    try:
        cache_threshold = timezone.now() - timedelta(days=30)

        # Obtener números de los últimos 30 días usando fecha_hora
        phone_cache = {}

        logger.info(f"[CACHE INIT] Consultando base de datos desde {cache_threshold}...")

        cached_numbers = Movil.objects.filter(
            fecha_hora__gte=cache_threshold
        ).exclude(
            operator__in=['ERROR_SCRAPING', 'No existe', 'Desconocido']
        ).values('number', 'operator', 'file', 'fecha_hora').order_by('number', '-fecha_hora')

        total_records = cached_numbers.count()
        logger.info(f"[CACHE INIT] Registros encontrados en BD: {total_records:,}")

        # Construir diccionario (solo el más reciente por número)
        for item in cached_numbers:
            if item['number'] not in phone_cache:
                phone_cache[item['number']] = {
                    'operator': item['operator'],
                    'source_file': item['file'],
                    'fecha_hora': item['fecha_hora'].isoformat()
                }

        logger.info(f"[CACHE INIT] Números únicos procesados: {len(phone_cache):,}")

        # Guardar en Redis (sin timeout, persistente)
        cache.set('global_phone_cache', phone_cache, timeout=None)
        cache.set('global_phone_cache_updated', timezone.now().isoformat(), timeout=None)
        cache.set('global_phone_cache_count', len(phone_cache), timeout=None)

        logger.info("=" * 80)
        logger.info(f"✅ [CACHE INIT] Caché global CARGADO en Redis: {len(phone_cache):,} números")
        logger.info(f"✅ [CACHE INIT] Última actualización: {timezone.now()}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ [CACHE INIT] Error cargando caché: {e}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())


def refresh_phone_cache():
    """
    Función para refrescar manualmente el caché.
    Puede ser llamada desde una tarea Celery programada.
    """
    from .models import Movil

    logger.info("🔄 [CACHE REFRESH] Refrescando caché global de números...")

    try:
        cache_threshold = timezone.now() - timedelta(days=30)

        phone_cache = {}
        cached_numbers = Movil.objects.filter(
            fecha_hora__gte=cache_threshold
        ).exclude(
            operator__in=['ERROR_SCRAPING', 'No existe', 'Desconocido']
        ).values('number', 'operator', 'file', 'fecha_hora').order_by('number', '-fecha_hora')

        for item in cached_numbers:
            if item['number'] not in phone_cache:
                phone_cache[item['number']] = {
                    'operator': item['operator'],
                    'source_file': item['file'],
                    'fecha_hora': item['fecha_hora'].isoformat()
                }

        cache.set('global_phone_cache', phone_cache, timeout=None)
        cache.set('global_phone_cache_updated', timezone.now().isoformat(), timeout=None)
        cache.set('global_phone_cache_count', len(phone_cache), timeout=None)

        logger.info(f"✅ [CACHE REFRESH] Caché refrescado: {len(phone_cache):,} números")
        return len(phone_cache)

    except Exception as e:
        logger.error(f"❌ [CACHE REFRESH] Error refrescando caché: {e}")
        return 0


def add_to_phone_cache(number, operator, file_name):
    """
    Agrega un número al caché después de scraping exitoso.
    """
    try:
        cache.set(f"phone:{number}", operator, timeout=60*60*24*30)  # 30 días
        logger.debug(f"[CACHE] Número agregado: {number} → {operator}")
    except Exception as e:
        logger.error(f"[CACHE] Error agregando al caché: {e}")
