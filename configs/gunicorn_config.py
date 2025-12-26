"""
Configuración de Gunicorn para producción
Ubicación: /var/www/apimovil/gunicorn_config.py

Este archivo ya debería estar en el proyecto, pero aquí está una versión
optimizada para producción.
"""
import multiprocessing
import os

# Configuración de bind
bind = "127.0.0.1:8000"

# Número de workers
# Fórmula: (2 * número_de_cpus) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Clase de worker
# 'sync' es la más estable para la mayoría de aplicaciones
# Usa 'gevent' o 'eventlet' si necesitas manejar muchas conexiones concurrentes
worker_class = "sync"

# Conexiones por worker
worker_connections = 1000

# Reiniciar workers después de N requests (previene memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Timeouts (en segundos)
timeout = 60  # Tiempo máximo para procesar un request
graceful_timeout = 30  # Tiempo para terminar requests antes de matar el worker
keepalive = 5  # Tiempo de keep-alive para conexiones

# Logging
accesslog = "/var/www/apimovil/logs/gunicorn_access.log"
errorlog = "/var/www/apimovil/logs/gunicorn_error.log"
loglevel = "info"  # debug, info, warning, error, critical

# Formato de logs de acceso
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Nombre del proceso
proc_name = "apimovil_gunicorn"

# Mecánica de procesos
daemon = False  # Supervisor se encarga de esto
pidfile = "/var/www/apimovil/gunicorn.pid"
user = "apimovil"
group = "www-data"
umask = 0o007

# Directorio temporal
tmp_upload_dir = None

# Security
# Límite de tamaño de request line
limit_request_line = 4094

# Límite de número de headers
limit_request_fields = 100

# Límite de tamaño de headers
limit_request_field_size = 8190

# Configuración SSL (si usas Gunicorn directamente sin Nginx)
# keyfile = None
# certfile = None
# ssl_version = None
# cert_reqs = None
# ca_certs = None
# suppress_ragged_eofs = True
# do_handshake_on_connect = False
# ciphers = None

# Hooks de pre/post fork
def on_starting(server):
    """Se ejecuta antes de iniciar el master process"""
    pass

def on_reload(server):
    """Se ejecuta cuando se recarga la configuración"""
    pass

def when_ready(server):
    """Se ejecuta cuando Gunicorn está listo para recibir requests"""
    pass

def pre_fork(server, worker):
    """Se ejecuta antes de hacer fork de un worker"""
    pass

def post_fork(server, worker):
    """Se ejecuta después de hacer fork de un worker"""
    pass

def post_worker_init(worker):
    """Se ejecuta después de inicializar un worker"""
    pass

def worker_int(worker):
    """Se ejecuta cuando un worker recibe SIGINT o SIGQUIT"""
    pass

def worker_abort(worker):
    """Se ejecuta cuando un worker recibe SIGABRT"""
    pass

def pre_exec(server):
    """Se ejecuta antes de ejecutar un nuevo master process"""
    pass

def pre_request(worker, req):
    """Se ejecuta antes de procesar un request"""
    worker.log.debug("%s %s" % (req.method, req.path))

def post_request(worker, req, environ, resp):
    """Se ejecuta después de procesar un request"""
    pass

def child_exit(server, worker):
    """Se ejecuta cuando un worker termina"""
    pass

def worker_exit(server, worker):
    """Se ejecuta cuando un worker termina"""
    pass

def nworkers_changed(server, new_value, old_value):
    """Se ejecuta cuando cambia el número de workers"""
    pass

def on_exit(server):
    """Se ejecuta cuando el master process termina"""
    pass
