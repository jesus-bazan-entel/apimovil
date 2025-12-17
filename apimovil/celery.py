from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')

app = Celery('apimovil')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Refuerzo anti “storm”: si algo pisa settings, estos valores quedan
app.conf.update(
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=45,
    task_time_limit=60,
    broker_pool_limit=10,
    broker_connection_timeout=30,
    task_annotations={'*': {'max_retries': 3, 'rate_limit': '10/m'}},
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

