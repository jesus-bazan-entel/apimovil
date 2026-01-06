"""
Configuración de Celery para apimovil.

SISTEMA DE COLAS POR USUARIO:
- Cada usuario tiene su propia cola: user_queue_<user_id>
- Los workers procesan todas las colas en round-robin
- Esto garantiza que archivos de diferentes usuarios se procesen en paralelo
"""
import os
from celery import Celery
from kombu import Queue

# Establecer el módulo de settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')

# Crear instancia de Celery
app = Celery('apimovil')

# Configuración desde settings.py con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en todas las apps instaladas
app.autodiscover_tasks()


def get_user_queue_name(user_id):
    """Genera el nombre de cola para un usuario específico."""
    return f'user_queue_{user_id}'


# Lista de colas de usuario activas (se actualizan dinámicamente)
# Incluimos colas para usuarios del 1 al 500 por defecto
USER_QUEUES = [Queue(f'user_queue_{i}') for i in range(1, 501)]

# Configuración básica
app.conf.update(
    # Broker y backend
    broker_url='redis://127.0.0.1:6379/0',
    result_backend='redis://127.0.0.1:6379/0',
    
    # Serialización
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Lima',  # Ajusta a tu zona horaria
    enable_utc=True,
    
    # Workers
    worker_prefetch_multiplier=1,  # Importante: 1 para round-robin justo
    worker_max_tasks_per_child=1000,
    
    # Timeouts
    task_time_limit=300,  # 5 minutos máximo por tarea
    task_soft_time_limit=240,  # 4 minutos soft limit
    
    # Retry
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Conexiones DB
    worker_pool_restarts=True,
    
    # COLAS: Cola por defecto + colas de usuario
    task_queues=[Queue('celery')] + USER_QUEUES,
    
    # Cola por defecto para tareas que no especifican cola
    task_default_queue='celery',
    
    # Rutas de tareas (las tareas de scraping van a colas de usuario)
    task_routes={
        'app.tasks.scrape_and_save_phone_task': {
            'queue': 'celery',  # Se sobreescribe dinámicamente
        },
        'app.tasks.process_file_in_batches': {
            'queue': 'celery',  # Se sobreescribe dinámicamente
        },
    },
    
    # Celery Beat - Tareas periódicas
    beat_schedule={
        'sync-progress-every-30-seconds': {
            'task': 'app.tasks.sync_progress_with_movil',
            'schedule': 30.0,  # Cada 30 segundos
        },
        'check-orphan-files-every-60-seconds': {
            'task': 'app.tasks.check_and_requeue_orphan_files',
            'schedule': 60.0,  # Cada 60 segundos
        },
    },
)

@app.task(bind=True)
def debug_task(self):
    """Tarea de prueba."""
    print(f'Request: {self.request!r}')
