# Guía de Deployment - Debian 12

Esta guía te ayudará a desplegar la aplicación Django con PostgreSQL en un servidor Debian 12 en producción.

## Tabla de Contenidos

1. [Preparación del Servidor](#1-preparación-del-servidor)
2. [Instalación de PostgreSQL](#2-instalación-de-postgresql)
3. [Instalación de Redis](#3-instalación-de-redis)
4. [Instalación de Python y Dependencias](#4-instalación-de-python-y-dependencias)
5. [Configuración del Proyecto](#5-configuración-del-proyecto)
6. [Configuración de la Base de Datos](#6-configuración-de-la-base-de-datos)
7. [Configuración de Gunicorn](#7-configuración-de-gunicorn)
8. [Configuración de Nginx](#8-configuración-de-nginx)
9. [Configuración de Celery](#9-configuración-de-celery)
10. [Configuración de Supervisor](#10-configuración-de-supervisor)
11. [Configuración de SSL/HTTPS](#11-configuración-de-sslhttps)
12. [Scripts de Mantenimiento](#12-scripts-de-mantenimiento)
13. [Seguridad y Optimización](#13-seguridad-y-optimización)

---

## 1. Preparación del Servidor

### 1.1 Actualizar el sistema

```bash
# Actualizar paquetes
sudo apt update
sudo apt upgrade -y

# Instalar herramientas básicas
sudo apt install -y git curl wget vim build-essential
```

### 1.2 Crear usuario para la aplicación

```bash
# Crear usuario (si no existe)
sudo adduser apimovil
sudo usermod -aG sudo apimovil

# Cambiar a usuario apimovil
su - apimovil
```

### 1.3 Configurar firewall (UFW)

```bash
# Instalar y configurar firewall
sudo apt install -y ufw

# Permitir SSH, HTTP y HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Activar firewall
sudo ufw enable
sudo ufw status
```

---

## 2. Instalación de PostgreSQL

### 2.1 Instalar PostgreSQL

```bash
# Instalar PostgreSQL 15
sudo apt install -y postgresql postgresql-contrib libpq-dev

# Verificar que esté corriendo
sudo systemctl status postgresql
sudo systemctl enable postgresql
```

### 2.2 Configurar PostgreSQL

```bash
# Acceder como usuario postgres
sudo -u postgres psql

# En el prompt de PostgreSQL:
```

```sql
-- Crear usuario para la aplicación
CREATE USER apimovil_user WITH PASSWORD 'TU_PASSWORD_SEGURO_AQUI';

-- Crear base de datos
CREATE DATABASE apimovil_db OWNER apimovil_user;

-- Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE apimovil_db TO apimovil_user;

-- Configurar para PostgreSQL 15+
\c apimovil_db
GRANT ALL ON SCHEMA public TO apimovil_user;

-- Salir
\q
```

### 2.3 Configurar autenticación

```bash
# Editar pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

Agregar/modificar estas líneas:

```
# IPv4 local connections:
host    apimovil_db     apimovil_user   127.0.0.1/32    md5
host    all             all             127.0.0.1/32    md5
```

```bash
# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

### 2.4 Verificar conexión

```bash
# Probar conexión
psql -U apimovil_user -d apimovil_db -h localhost
# Ingresa el password cuando lo pida
# \q para salir
```

---

## 3. Instalación de Redis

```bash
# Instalar Redis
sudo apt install -y redis-server

# Configurar Redis
sudo nano /etc/redis/redis.conf
```

Configuración recomendada:

```
supervised systemd
bind 127.0.0.1
maxmemory 256mb
maxmemory-policy allkeys-lru
```

```bash
# Reiniciar Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Verificar
redis-cli ping
# Debería responder: PONG
```

---

## 4. Instalación de Python y Dependencias

### 4.1 Instalar Python 3.11+

```bash
# Debian 12 incluye Python 3.11 por defecto
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Verificar versión
python3 --version
```

### 4.2 Configurar directorio del proyecto

```bash
# Crear directorio para aplicaciones
sudo mkdir -p /var/www/apimovil
sudo chown apimovil:apimovil /var/www/apimovil
cd /var/www/apimovil
```

---

## 5. Configuración del Proyecto

### 5.1 Clonar el repositorio

```bash
# Clonar el proyecto
cd /var/www/apimovil
git clone https://github.com/tu-usuario/apimovil.git .

# O si ya lo tienes, copiar archivos
# scp -r /ruta/local/apimovil/* usuario@servidor:/var/www/apimovil/
```

### 5.2 Crear entorno virtual

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip
```

### 5.3 Instalar dependencias

```bash
# Instalar dependencias del proyecto
pip install -r requirements.txt

# Verificar instalación
python -c "import django; print(django.get_version())"
python -c "import psycopg2; print('PostgreSQL OK')"
```

### 5.4 Configurar variables de entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar variables de entorno
nano .env
```

Contenido del `.env`:

```bash
# Django Settings
SECRET_KEY=genera-una-clave-secreta-muy-larga-y-aleatoria-aqui
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com,tu-ip-del-servidor

# Database
DB_NAME=apimovil_db
DB_USER=apimovil_user
DB_PASSWORD=TU_PASSWORD_SEGURO_AQUI
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**IMPORTANTE**: Generar una SECRET_KEY segura:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5.5 Actualizar settings.py para producción

```bash
nano apimovil/settings.py
```

Agregar al inicio (después de los imports):

```python
from dotenv import load_dotenv
load_dotenv()

import os
```

Y modificar:

```python
# Security Settings
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY debe estar definida en .env")

# HTTPS Settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

**Instalar python-dotenv**:

```bash
pip install python-dotenv
```

---

## 6. Configuración de la Base de Datos

### 6.1 Ejecutar migraciones

```bash
# Verificar configuración
python manage.py check

# Crear migraciones si es necesario
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser
```

### 6.2 Migrar datos desde SQLite (si aplica)

```bash
# Si tienes datos en SQLite, primero exporta desde tu máquina local:
# python migrate_to_postgresql.py

# Luego copia el archivo al servidor:
# scp sqlite_data_backup.json usuario@servidor:/var/www/apimovil/

# En el servidor, cargar datos:
python manage.py loaddata sqlite_data_backup.json

# Verificar
python verify_migration.py
```

### 6.3 Recolectar archivos estáticos

```bash
# Recolectar archivos estáticos
python manage.py collectstatic --noinput

# Verificar permisos
sudo chown -R apimovil:www-data /var/www/apimovil/staticfiles
sudo chmod -R 755 /var/www/apimovil/staticfiles
```

---

## 7. Configuración de Gunicorn

### 7.1 Crear archivo de configuración

```bash
nano /var/www/apimovil/gunicorn_config.py
```

Contenido:

```python
"""Configuración de Gunicorn para producción"""
import multiprocessing

# Bind
bind = "127.0.0.1:8000"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts
timeout = 60
keepalive = 5

# Logging
accesslog = "/var/www/apimovil/logs/gunicorn_access.log"
errorlog = "/var/www/apimovil/logs/gunicorn_error.log"
loglevel = "info"

# Process naming
proc_name = "apimovil"

# Server mechanics
daemon = False
pidfile = "/var/www/apimovil/gunicorn.pid"
user = "apimovil"
group = "www-data"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
```

### 7.2 Crear directorio de logs

```bash
mkdir -p /var/www/apimovil/logs
```

### 7.3 Probar Gunicorn

```bash
# Activar entorno virtual
source /var/www/apimovil/venv/bin/activate

# Probar Gunicorn
cd /var/www/apimovil
gunicorn apimovil.wsgi:application -c gunicorn_config.py

# Si funciona, detener con Ctrl+C
```

---

## 8. Configuración de Nginx

### 8.1 Instalar Nginx

```bash
sudo apt install -y nginx
```

### 8.2 Crear configuración del sitio

```bash
sudo nano /etc/nginx/sites-available/apimovil
```

Contenido:

```nginx
# Upstream para Gunicorn
upstream apimovil_app {
    server 127.0.0.1:8000 fail_timeout=0;
}

# Redirigir HTTP a HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name tu-dominio.com www.tu-dominio.com;

    # Permitir certbot para SSL
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirigir todo a HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# Servidor HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name tu-dominio.com www.tu-dominio.com;

    # SSL Configuration (se configurará después con certbot)
    # ssl_certificate /etc/letsencrypt/live/tu-dominio.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/tu-dominio.com/privkey.pem;

    # Logs
    access_log /var/log/nginx/apimovil_access.log;
    error_log /var/log/nginx/apimovil_error.log;

    # Max upload size
    client_max_body_size 100M;

    # Archivos estáticos
    location /static/ {
        alias /var/www/apimovil/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Archivos media (si los hay)
    location /media/ {
        alias /var/www/apimovil/media/;
        expires 7d;
    }

    # Proxy a Gunicorn
    location / {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_buffering off;

        proxy_pass http://apimovil_app;
    }

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
}
```

### 8.3 Habilitar sitio

```bash
# Crear enlace simbólico
sudo ln -s /etc/nginx/sites-available/apimovil /etc/nginx/sites-enabled/

# Eliminar sitio por defecto
sudo rm /etc/nginx/sites-enabled/default

# Probar configuración
sudo nginx -t

# Reiniciar Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 9. Configuración de Celery

### 9.1 Verificar tareas de Celery

```bash
# Verificar que tasks.py existe
cat /var/www/apimovil/app/tasks.py
```

### 9.2 Probar Celery manualmente

```bash
# Activar entorno virtual
source /var/www/apimovil/venv/bin/activate
cd /var/www/apimovil

# Probar worker
celery -A apimovil worker --loglevel=info

# En otra terminal, probar beat
celery -A apimovil beat --loglevel=info
```

Si funciona, continuar con Supervisor.

---

## 10. Configuración de Supervisor

### 10.1 Instalar Supervisor

```bash
sudo apt install -y supervisor
```

### 10.2 Configurar Gunicorn en Supervisor

```bash
sudo nano /etc/supervisor/conf.d/apimovil.conf
```

Contenido:

```ini
[program:apimovil]
command=/var/www/apimovil/venv/bin/gunicorn apimovil.wsgi:application -c gunicorn_config.py
directory=/var/www/apimovil
user=apimovil
group=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/apimovil/logs/gunicorn_supervisor.log
stderr_logfile=/var/www/apimovil/logs/gunicorn_supervisor_error.log
environment=PATH="/var/www/apimovil/venv/bin"
```

### 10.3 Configurar Celery Worker

```bash
sudo nano /etc/supervisor/conf.d/celery_worker.conf
```

Contenido:

```ini
[program:celery_worker]
command=/var/www/apimovil/venv/bin/celery -A apimovil worker --loglevel=info --concurrency=4
directory=/var/www/apimovil
user=apimovil
group=apimovil
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/apimovil/logs/celery_worker.log
stderr_logfile=/var/www/apimovil/logs/celery_worker_error.log
stopwaitsecs=600
stopasgroup=true
killasgroup=true
environment=PATH="/var/www/apimovil/venv/bin"
```

### 10.4 Configurar Celery Beat

```bash
sudo nano /etc/supervisor/conf.d/celery_beat.conf
```

Contenido:

```ini
[program:celery_beat]
command=/var/www/apimovil/venv/bin/celery -A apimovil beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
directory=/var/www/apimovil
user=apimovil
group=apimovil
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/www/apimovil/logs/celery_beat.log
stderr_logfile=/var/www/apimovil/logs/celery_beat_error.log
environment=PATH="/var/www/apimovil/venv/bin"
```

### 10.5 Activar servicios

```bash
# Recargar configuración
sudo supervisorctl reread
sudo supervisorctl update

# Iniciar servicios
sudo supervisorctl start apimovil
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat

# Verificar estado
sudo supervisorctl status
```

Deberías ver algo como:

```
apimovil                         RUNNING   pid 12345, uptime 0:00:10
celery_worker                    RUNNING   pid 12346, uptime 0:00:10
celery_beat                      RUNNING   pid 12347, uptime 0:00:10
```

---

## 11. Configuración de SSL/HTTPS

### 11.1 Instalar Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 11.2 Obtener certificado SSL

```bash
# Obtener certificado
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com

# Seguir las instrucciones:
# - Ingresa tu email
# - Acepta términos
# - Elige si compartir email
# - Certbot configurará Nginx automáticamente
```

### 11.3 Configurar renovación automática

```bash
# Probar renovación
sudo certbot renew --dry-run

# Certbot agrega automáticamente un cron job
# Verificar:
sudo systemctl status certbot.timer
```

### 11.4 Actualizar configuración de Nginx

Certbot debería haber actualizado automáticamente `/etc/nginx/sites-available/apimovil`.

Verificar:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. Scripts de Mantenimiento

### 12.1 Script de backup

```bash
nano /var/www/apimovil/backup.sh
```

Ver archivo `backup.sh` creado en el proyecto.

```bash
chmod +x /var/www/apimovil/backup.sh
```

### 12.2 Configurar cron para backups

```bash
crontab -e
```

Agregar:

```cron
# Backup diario a las 2 AM
0 2 * * * /var/www/apimovil/backup.sh

# Limpiar logs viejos semanalmente
0 3 * * 0 find /var/www/apimovil/logs -name "*.log" -mtime +30 -delete
```

---

## 13. Seguridad y Optimización

### 13.1 Configurar límites de PostgreSQL

```bash
sudo nano /etc/postgresql/15/main/postgresql.conf
```

Ajustar según tu RAM:

```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB
max_connections = 100
```

```bash
sudo systemctl restart postgresql
```

### 13.2 Configurar log rotation

```bash
sudo nano /etc/logrotate.d/apimovil
```

Contenido:

```
/var/www/apimovil/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 apimovil apimovil
    sharedscripts
    postrotate
        supervisorctl restart apimovil celery_worker celery_beat > /dev/null 2>&1 || true
    endscript
}
```

### 13.3 Configurar fail2ban (opcional)

```bash
sudo apt install -y fail2ban

sudo nano /etc/fail2ban/jail.local
```

Contenido:

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true
```

```bash
sudo systemctl restart fail2ban
```

---

## Comandos Útiles para Administración

### Supervisor

```bash
# Ver estado de servicios
sudo supervisorctl status

# Reiniciar servicio
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker

# Ver logs en tiempo real
sudo supervisorctl tail -f apimovil
sudo supervisorctl tail -f celery_worker

# Detener/iniciar todos los servicios
sudo supervisorctl stop all
sudo supervisorctl start all
```

### Django

```bash
# Activar entorno
source /var/www/apimovil/venv/bin/activate
cd /var/www/apimovil

# Django shell
python manage.py shell

# Crear superusuario
python manage.py createsuperuser

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Recolectar estáticos
python manage.py collectstatic --noinput
```

### Nginx

```bash
# Probar configuración
sudo nginx -t

# Recargar configuración
sudo systemctl reload nginx

# Reiniciar Nginx
sudo systemctl restart nginx

# Ver logs
sudo tail -f /var/log/nginx/apimovil_access.log
sudo tail -f /var/log/nginx/apimovil_error.log
```

### PostgreSQL

```bash
# Conectar a base de datos
psql -U apimovil_user -d apimovil_db -h localhost

# Backup manual
pg_dump -U apimovil_user apimovil_db > backup_$(date +%Y%m%d).sql

# Restaurar backup
psql -U apimovil_user apimovil_db < backup_20240101.sql
```

---

## Troubleshooting

### Gunicorn no inicia

```bash
# Ver logs
sudo supervisorctl tail -f apimovil stderr

# Verificar permisos
ls -la /var/www/apimovil

# Probar manualmente
source /var/www/apimovil/venv/bin/activate
cd /var/www/apimovil
gunicorn apimovil.wsgi:application -c gunicorn_config.py
```

### Error 502 Bad Gateway

```bash
# Verificar que Gunicorn esté corriendo
sudo supervisorctl status apimovil

# Ver logs de Nginx
sudo tail -f /var/log/nginx/apimovil_error.log

# Verificar que el socket/puerto esté escuchando
sudo netstat -tulpn | grep 8000
```

### Celery no procesa tareas

```bash
# Verificar worker
sudo supervisorctl status celery_worker

# Ver logs
sudo supervisorctl tail -f celery_worker

# Verificar Redis
redis-cli ping

# Probar manualmente
source /var/www/apimovil/venv/bin/activate
cd /var/www/apimovil
celery -A apimovil worker --loglevel=debug
```

### No se puede conectar a PostgreSQL

```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Verificar conexión
psql -U apimovil_user -d apimovil_db -h localhost

# Ver logs de PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

---

## Checklist de Deployment

- [ ] Servidor actualizado
- [ ] Firewall configurado
- [ ] PostgreSQL instalado y configurado
- [ ] Redis instalado y corriendo
- [ ] Python y entorno virtual configurados
- [ ] Proyecto clonado/copiado
- [ ] Dependencias instaladas
- [ ] Variables de entorno configuradas (.env)
- [ ] Migraciones ejecutadas
- [ ] Archivos estáticos recolectados
- [ ] Gunicorn configurado
- [ ] Nginx configurado
- [ ] Supervisor configurado
- [ ] Celery worker funcionando
- [ ] Celery beat funcionando
- [ ] SSL/HTTPS configurado
- [ ] Backups automáticos configurados
- [ ] Aplicación accesible desde navegador
- [ ] Admin de Django accesible
- [ ] Tareas programadas ejecutándose

---

## Recursos Adicionales

- [Documentación de Django Deployment](https://docs.djangoproject.com/en/3.2/howto/deployment/)
- [Guía de Nginx](https://nginx.org/en/docs/)
- [Documentación de Supervisor](http://supervisord.org/)
- [Guía de Seguridad Django](https://docs.djangoproject.com/en/3.2/topics/security/)

---

**¡Tu aplicación está lista para producción!**
