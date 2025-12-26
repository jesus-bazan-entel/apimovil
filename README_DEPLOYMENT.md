# Deployment Rápido - Debian 12

Esta es la guía de inicio rápido para desplegar la aplicación en Debian 12. Para instrucciones detalladas, consulta [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Tabla de Contenidos

- [Prerequisitos](#prerequisitos)
- [Instalación Rápida](#instalación-rápida)
- [Scripts Disponibles](#scripts-disponibles)
- [Archivos de Configuración](#archivos-de-configuración)
- [Comandos Útiles](#comandos-útiles)
- [Troubleshooting](#troubleshooting)

---

## Prerequisitos

- Servidor Debian 12 con acceso root/sudo
- Dominio apuntando al servidor (opcional pero recomendado)
- Puerto 80 y 443 abiertos en el firewall

---

## Instalación Rápida

### 1. Preparar el servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install -y \
    postgresql postgresql-contrib libpq-dev \
    redis-server \
    python3 python3-pip python3-venv python3-dev \
    nginx \
    supervisor \
    git curl wget build-essential

# Configurar firewall
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Configurar PostgreSQL

```bash
# Crear usuario y base de datos
sudo -u postgres psql << EOF
CREATE USER apimovil_user WITH PASSWORD 'TU_PASSWORD_SEGURO';
CREATE DATABASE apimovil_db OWNER apimovil_user;
GRANT ALL PRIVILEGES ON DATABASE apimovil_db TO apimovil_user;
\c apimovil_db
GRANT ALL ON SCHEMA public TO apimovil_user;
\q
EOF

# Configurar autenticación
echo "host    apimovil_db     apimovil_user   127.0.0.1/32    md5" | \
    sudo tee -a /etc/postgresql/15/main/pg_hba.conf
sudo systemctl restart postgresql
```

### 3. Configurar el proyecto

```bash
# Crear directorio
sudo mkdir -p /var/www/apimovil
sudo chown $USER:www-data /var/www/apimovil

# Clonar proyecto
cd /var/www/apimovil
git clone https://github.com/tu-usuario/apimovil.git .

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
pip install python-dotenv gunicorn
```

### 4. Configurar variables de entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar (usa tu editor favorito)
nano .env
```

Configuración mínima en `.env`:

```bash
SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com

DB_NAME=apimovil_db
DB_USER=apimovil_user
DB_PASSWORD=TU_PASSWORD_SEGURO
DB_HOST=localhost
DB_PORT=5432
```

### 5. Configurar Django

```bash
# Actualizar settings.py para cargar .env
nano apimovil/settings.py
```

Agregar al inicio (después de imports):

```python
from dotenv import load_dotenv
load_dotenv()
```

### 6. Aplicar migraciones y recolectar estáticos

```bash
source venv/bin/activate
cd /var/www/apimovil

# Crear directorios necesarios
mkdir -p logs backups

# Ejecutar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recolectar estáticos
python manage.py collectstatic --noinput

# Ajustar permisos
sudo chown -R $USER:www-data /var/www/apimovil
sudo chmod -R 755 /var/www/apimovil/staticfiles
```

### 7. Configurar servicios

```bash
# Copiar configuraciones de Supervisor
sudo cp configs/supervisor_apimovil.conf /etc/supervisor/conf.d/apimovil.conf
sudo cp configs/supervisor_celery_worker.conf /etc/supervisor/conf.d/celery_worker.conf
sudo cp configs/supervisor_celery_beat.conf /etc/supervisor/conf.d/celery_beat.conf

# Copiar configuración de Gunicorn
cp configs/gunicorn_config.py /var/www/apimovil/gunicorn_config.py

# Copiar configuración de Nginx
sudo cp configs/nginx.conf /etc/nginx/sites-available/apimovil

# IMPORTANTE: Edita y reemplaza "tu-dominio.com" con tu dominio real
sudo nano /etc/nginx/sites-available/apimovil

# Habilitar sitio Nginx
sudo ln -s /etc/nginx/sites-available/apimovil /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Probar configuración
sudo nginx -t
```

### 8. Iniciar servicios

```bash
# Recargar Supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Iniciar servicios
sudo supervisorctl start apimovil
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat

# Verificar estado
sudo supervisorctl status

# Reiniciar Nginx
sudo systemctl restart nginx
```

### 9. Configurar SSL (Certbot)

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com

# El certificado se renovará automáticamente
```

### 10. Verificar instalación

```bash
# Ejecutar health check
bash scripts/health_check.sh

# Acceder a la aplicación
# https://tu-dominio.com
# https://tu-dominio.com/admin
```

---

## Scripts Disponibles

Todos los scripts están en el directorio `scripts/`:

### `backup.sh` - Backup automático

```bash
# Crear backup de base de datos, media y configuración
bash scripts/backup.sh

# Configurar backup automático (cron diario a las 2 AM)
crontab -e
# Agregar: 0 2 * * * /var/www/apimovil/scripts/backup.sh
```

### `restore.sh` - Restaurar backup

```bash
# Listar backups disponibles
bash scripts/restore.sh

# Restaurar backup específico
bash scripts/restore.sh 20240101_120000
```

### `deploy.sh` - Deployment automatizado

```bash
# Deploy desde branch main (por defecto)
bash scripts/deploy.sh

# Deploy desde otra branch
bash scripts/deploy.sh develop
```

Este script hace:
1. Backup automático
2. Pull del código desde Git
3. Instalación de dependencias
4. Migraciones de BD
5. Recolección de estáticos
6. Reinicio de servicios

### `health_check.sh` - Verificación del sistema

```bash
# Verificar estado de todos los servicios
bash scripts/health_check.sh
```

Verifica:
- Servicios de Supervisor (Gunicorn, Celery)
- PostgreSQL (conexión y datos)
- Redis
- Nginx
- Espacio en disco
- Memoria
- SSL/Certificados

---

## Archivos de Configuración

Todos los archivos de configuración están en el directorio `configs/`:

| Archivo | Ubicación Final | Descripción |
|---------|----------------|-------------|
| `nginx.conf` | `/etc/nginx/sites-available/apimovil` | Configuración de Nginx |
| `supervisor_apimovil.conf` | `/etc/supervisor/conf.d/apimovil.conf` | Gunicorn supervisor |
| `supervisor_celery_worker.conf` | `/etc/supervisor/conf.d/celery_worker.conf` | Celery worker supervisor |
| `supervisor_celery_beat.conf` | `/etc/supervisor/conf.d/celery_beat.conf` | Celery beat supervisor |
| `gunicorn_config.py` | `/var/www/apimovil/gunicorn_config.py` | Configuración de Gunicorn |

---

## Comandos Útiles

### Supervisor (Gestión de servicios)

```bash
# Ver estado de todos los servicios
sudo supervisorctl status

# Reiniciar un servicio
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker

# Ver logs en tiempo real
sudo supervisorctl tail -f apimovil
sudo supervisorctl tail -f celery_worker stderr

# Detener/Iniciar todos
sudo supervisorctl stop all
sudo supervisorctl start all

# Recargar configuración
sudo supervisorctl reread
sudo supervisorctl update
```

### Nginx

```bash
# Probar configuración
sudo nginx -t

# Recargar (sin downtime)
sudo systemctl reload nginx

# Reiniciar
sudo systemctl restart nginx

# Ver logs
sudo tail -f /var/log/nginx/apimovil_access.log
sudo tail -f /var/log/nginx/apimovil_error.log
```

### Django Management

```bash
# Activar entorno virtual
source /var/www/apimovil/venv/bin/activate
cd /var/www/apimovil

# Shell de Django
python manage.py shell

# Crear superusuario
python manage.py createsuperuser

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Recolectar estáticos
python manage.py collectstatic --noinput

# Verificar configuración
python manage.py check
```

### PostgreSQL

```bash
# Conectar a la base de datos
psql -U apimovil_user -d apimovil_db -h localhost

# Backup manual
pg_dump -U apimovil_user apimovil_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Restaurar backup
gunzip -c backup_20240101.sql.gz | psql -U apimovil_user apimovil_db

# Ver tablas y datos
psql -U apimovil_user -d apimovil_db -h localhost -c "\dt"
psql -U apimovil_user -d apimovil_db -h localhost -c "SELECT COUNT(*) FROM app_movil;"
```

### Celery

```bash
# Ver estado de workers
celery -A apimovil inspect active

# Ver tareas programadas
celery -A apimovil inspect scheduled

# Purgar todas las tareas
celery -A apimovil purge

# Probar una tarea manualmente
python manage.py shell
>>> from app.tasks import process_incomplete_files_task
>>> process_incomplete_files_task.delay()
```

---

## Troubleshooting

### Error 502 Bad Gateway

```bash
# 1. Verificar que Gunicorn esté corriendo
sudo supervisorctl status apimovil

# 2. Ver logs de Gunicorn
sudo supervisorctl tail -f apimovil stderr

# 3. Verificar puerto
sudo netstat -tulpn | grep 8000

# 4. Reiniciar Gunicorn
sudo supervisorctl restart apimovil
```

### Cambios en el código no se reflejan

```bash
# 1. Recolectar estáticos
python manage.py collectstatic --noinput

# 2. Reiniciar Gunicorn
sudo supervisorctl restart apimovil

# 3. Limpiar caché del navegador
# Ctrl+Shift+R o Ctrl+F5
```

### Celery no procesa tareas

```bash
# 1. Verificar Redis
redis-cli ping

# 2. Ver logs de Celery
sudo supervisorctl tail -f celery_worker

# 3. Reiniciar worker
sudo supervisorctl restart celery_worker

# 4. Verificar tareas pendientes
celery -A apimovil inspect active
```

### No se puede conectar a PostgreSQL

```bash
# 1. Verificar que esté corriendo
sudo systemctl status postgresql

# 2. Ver logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log

# 3. Probar conexión
psql -U apimovil_user -d apimovil_db -h localhost

# 4. Verificar pg_hba.conf
sudo cat /etc/postgresql/15/main/pg_hba.conf | grep apimovil
```

### Ver todos los logs

```bash
# Logs de la aplicación
sudo supervisorctl tail -f apimovil
sudo supervisorctl tail -f apimovil stderr

# Logs de Celery
sudo supervisorctl tail -f celery_worker

# Logs de Nginx
sudo tail -f /var/log/nginx/apimovil_error.log

# Logs de Django (si están configurados)
tail -f /var/www/apimovil/logs/django_debug.log
```

---

## Mantenimiento Regular

### Diario (automatizado)

- Backup de base de datos (cron: 2 AM)

### Semanal

```bash
# Limpiar logs antiguos
sudo find /var/www/apimovil/logs -name "*.log" -mtime +30 -delete

# Vacuum de PostgreSQL
psql -U apimovil_user -d apimovil_db -h localhost -c "VACUUM ANALYZE;"

# Verificar espacio en disco
df -h
```

### Mensual

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Verificar certificado SSL
sudo certbot renew --dry-run

# Revisar logs de errores
sudo grep -i error /var/log/nginx/apimovil_error.log
```

---

## Estructura de Directorios

```
/var/www/apimovil/
├── apimovil/           # Configuración Django
├── app/                # Aplicación principal
├── static/             # Archivos estáticos del proyecto
├── staticfiles/        # Archivos estáticos recolectados
├── media/              # Archivos subidos por usuarios
├── venv/               # Entorno virtual Python
├── logs/               # Logs de la aplicación
│   ├── gunicorn_access.log
│   ├── gunicorn_error.log
│   ├── celery_worker.log
│   └── celery_beat.log
├── backups/            # Backups automáticos
├── scripts/            # Scripts de utilidad
│   ├── backup.sh
│   ├── restore.sh
│   ├── deploy.sh
│   └── health_check.sh
├── configs/            # Archivos de configuración
├── .env                # Variables de entorno (NO commitear)
├── .env.example        # Plantilla de variables
├── requirements.txt    # Dependencias Python
├── gunicorn_config.py  # Config de Gunicorn
└── manage.py           # Django management
```

---

## URLs Importantes

- **Aplicación**: https://tu-dominio.com
- **Admin Django**: https://tu-dominio.com/admin
- **Archivos estáticos**: https://tu-dominio.com/static/
- **Archivos media**: https://tu-dominio.com/media/

---

## Checklist Post-Deployment

- [ ] Todos los servicios corriendo (supervisor status)
- [ ] Aplicación accesible desde navegador
- [ ] Admin de Django accesible
- [ ] SSL/HTTPS funcionando
- [ ] Celery procesando tareas
- [ ] Backups automáticos configurados
- [ ] Logs rotando correctamente
- [ ] Firewall configurado
- [ ] Variables de entorno seguras
- [ ] DEBUG=False en producción

---

## Recursos

- **Guía completa**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Guía de migración**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Documentación Django**: https://docs.djangoproject.com
- **Documentación Nginx**: https://nginx.org/en/docs/
- **Documentación Supervisor**: http://supervisord.org/

---

**¿Necesitas ayuda?** Consulta la guía completa en [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
