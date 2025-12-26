bind = "unix:/opt/apimovil/hypercorn.sock"  # Usando un socket Unix
workers = 4  # Número de trabajadores (ajusta según tus necesidades)
worker_class = "uvloop"  # Usar uvloop para mejorar el rendimiento (si está instalado)

