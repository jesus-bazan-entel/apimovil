# Guía de Deployment - Tu Servidor Actual

Basado en tu servidor Debian 12 con PostgreSQL ya instalado.

## Estado Actual

✅ PostgreSQL 15 instalado y corriendo
✅ Base de datos `db_apimovil` ya existe
✅ Usuario `admin` con privilegios

## Paso 1: Configurar Usuario y Permisos en PostgreSQL

```sql
-- Ya estás en psql como postgres, ejecuta estos comandos:

-- Opción A: Usar el usuario 'admin' existente
-- Otorgar permisos completos a admin sobre db_apimovil
GRANT ALL PRIVILEGES ON DATABASE db_apimovil TO admin;

-- Conectar a la base de datos
\c db_apimovil

-- Otorgar permisos en el esquema público
GRANT ALL ON SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;

-- Para tablas futuras
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO admin;

-- Verificar
\l
\q
```

O si prefieres crear un usuario nuevo específico:

```sql
-- Opción B: Crear usuario específico para apimovil
CREATE USER apimovil_user WITH PASSWORD 'TU_PASSWORD_SEGURO';

-- Cambiar owner de la base de datos
ALTER DATABASE db_apimovil OWNER TO apimovil_user;

-- Conectar a la base de datos
\c db_apimovil

-- Otorgar permisos
GRANT ALL ON SCHEMA public TO apimovil_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO apimovil_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO apimovil_user;

-- Para tablas futuras
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO apimovil_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO apimovil_user;

-- Verificar y salir
\du
\q
```

## Paso 2: Verificar Conexión desde Shell

```bash
# Salir del usuario postgres
exit

# Probar conexión (usa el usuario que configuraste)
# Si usaste 'admin':
psql -U admin -d db_apimovil -h localhost -W

# O si creaste 'apimovil_user':
psql -U apimovil_user -d db_apimovil -h localhost -W

# Ingresa el password y verifica que funcione
# Luego sal con: \q
```

## Paso 3: Ubicar tu Proyecto

¿Dónde está tu proyecto actualmente? Verifica:

```bash
# Buscar el proyecto
find /home -name "manage.py" 2>/dev/null
find /var/www -name "manage.py" 2>/dev/null
find /opt -name "manage.py" 2>/dev/null

# O si sabes la ubicación aproximada:
ls -la /var/www/
ls -la /home/*/
```

Una vez que sepas dónde está, continúa con los siguientes pasos.

## Paso 4: Configurar Variables de Entorno

```bash
# Ir al directorio del proyecto (ajusta la ruta según tu caso)
cd /ruta/a/tu/proyecto/apimovil

# Crear archivo .env
nano .env
```

Contenido del `.env` (ajusta según el usuario que configuraste):

```bash
# Django
SECRET_KEY=tu-secret-key-generada-aqui
DEBUG=False
ALLOWED_HOSTS=20240807Ri7.vpsnet.es,tu-dominio.com,tu-ip

# Database (usa el usuario que configuraste)
DB_NAME=db_apimovil
DB_USER=admin
DB_PASSWORD=el_password_del_usuario_admin
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

Para generar SECRET_KEY:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Paso 5: Instalar Dependencias y Configurar Proyecto

```bash
# Asegúrate de estar en el directorio del proyecto
cd /ruta/a/tu/proyecto/apimovil

# Si no tienes entorno virtual, créalo
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
pip install python-dotenv

# Verificar que psycopg2 esté instalado
python -c "import psycopg2; print('PostgreSQL OK')"
```

## Paso 6: Actualizar settings.py

```bash
nano apimovil/settings.py
```

Asegúrate de que tenga estas líneas al inicio (después de los imports):

```python
import os
from dotenv import load_dotenv
load_dotenv()
```

Y la configuración de DATABASES debe ser:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'db_apimovil'),
        'USER': os.environ.get('DB_USER', 'admin'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

## Paso 7: Ejecutar Migraciones

```bash
# Activar entorno virtual si no está activado
source venv/bin/activate

# Verificar conexión a BD
python manage.py check --database default

# Si hay datos en SQLite que quieres migrar:
# 1. Exportar de SQLite (si db.sqlite3 existe)
python manage.py dumpdata --natural-foreign --natural-primary \
    --exclude=contenttypes --exclude=auth.permission \
    --indent=2 > data_backup.json

# 2. Aplicar migraciones a PostgreSQL
python manage.py migrate

# 3. Cargar datos (si exportaste)
python manage.py loaddata data_backup.json

# O si es una instalación nueva:
python manage.py migrate
python manage.py createsuperuser

# Recolectar archivos estáticos
mkdir -p staticfiles logs backups
python manage.py collectstatic --noinput
```

## Paso 8: Probar que Funciona

```bash
# Probar el servidor de desarrollo
python manage.py runserver 0.0.0.0:8000

# En otra terminal o desde tu navegador:
# http://20240807Ri7.vpsnet.es:8000
# http://tu-ip:8000

# Si funciona, detén el servidor (Ctrl+C) y continúa
```

## Paso 9: Configurar Gunicorn con Supervisor

```bash
# Copiar configuraciones
sudo cp configs/supervisor_apimovil.conf /etc/supervisor/conf.d/
sudo cp configs/supervisor_celery_worker.conf /etc/supervisor/conf.d/
sudo cp configs/supervisor_celery_beat.conf /etc/supervisor/conf.d/

# IMPORTANTE: Editar las rutas si tu proyecto NO está en /var/www/apimovil
sudo nano /etc/supervisor/conf.d/apimovil.conf
# Ajusta 'directory=' y 'command=' con la ruta correcta de tu proyecto

# Copiar configuración de Gunicorn
cp configs/gunicorn_config.py ./

# Editar rutas en gunicorn_config.py
nano gunicorn_config.py
# Ajusta las rutas de logs si es necesario

# Recargar supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Iniciar servicios
sudo supervisorctl start apimovil
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat

# Verificar estado
sudo supervisorctl status
```

## Paso 10: Configurar Nginx

```bash
# Verificar si Nginx está instalado
nginx -v

# Si no está instalado:
sudo apt install -y nginx

# Copiar configuración
sudo cp configs/nginx.conf /etc/nginx/sites-available/apimovil

# Editar y ajustar el dominio
sudo nano /etc/nginx/sites-available/apimovil
# Reemplaza "tu-dominio.com" con "20240807Ri7.vpsnet.es" o tu dominio real

# Habilitar sitio
sudo ln -s /etc/nginx/sites-available/apimovil /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Probar configuración
sudo nginx -t

# Si está OK, reiniciar
sudo systemctl restart nginx
```

## Paso 11: Verificar que Todo Funcione

```bash
# Verificar servicios
sudo supervisorctl status

# Debe mostrar:
# apimovil                         RUNNING
# celery_worker                    RUNNING
# celery_beat                      RUNNING

# Probar la aplicación
curl http://localhost:8000
curl http://20240807Ri7.vpsnet.es

# Verificar salud del sistema
bash scripts/health_check.sh
```

## Paso 12: Configurar SSL (Opcional)

```bash
# Instalar certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado (usa tu dominio real)
sudo certbot --nginx -d 20240807Ri7.vpsnet.es

# O si tienes un dominio personalizado:
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com
```

## Troubleshooting Común

### Error: "relation does not exist"
```bash
# Asegúrate de que las migraciones se ejecutaron
python manage.py migrate --run-syncdb
```

### Error: "FATAL: Peer authentication failed"
```bash
# Editar pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Cambiar la línea de 'local' de 'peer' a 'md5':
# local   all             all                                     md5

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

### Gunicorn no inicia
```bash
# Ver logs
sudo supervisorctl tail -f apimovil stderr

# Verificar que el entorno virtual tenga gunicorn
source venv/bin/activate
which gunicorn
```

### Ver todos los logs
```bash
# Logs de Gunicorn
sudo supervisorctl tail -f apimovil

# Logs de Celery
sudo supervisorctl tail -f celery_worker

# Logs de Nginx
sudo tail -f /var/log/nginx/error.log
```

## Comandos de Administración

```bash
# Reiniciar aplicación después de cambios en código
sudo supervisorctl restart apimovil

# Reiniciar Celery
sudo supervisorctl restart celery_worker

# Ver estado general
sudo supervisorctl status

# Hacer backup
bash scripts/backup.sh

# Deployment de nuevos cambios
bash scripts/deploy.sh
```

## Resumen de lo que Necesitas

1. ✅ PostgreSQL ya está listo
2. ⏳ Configurar usuario y permisos en PostgreSQL
3. ⏳ Ubicar tu proyecto (o clonarlo si aún no está)
4. ⏳ Crear archivo .env con credenciales
5. ⏳ Instalar dependencias en entorno virtual
6. ⏳ Ejecutar migraciones
7. ⏳ Configurar Supervisor
8. ⏳ Configurar Nginx
9. ⏳ Verificar que funcione

---

**Siguiente paso:** ¿Dónde está ubicado tu proyecto actualmente? O ¿necesitas clonarlo desde GitHub?
