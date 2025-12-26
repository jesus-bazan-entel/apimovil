# Guía de Actualización del Servidor

## Cambios Disponibles en la Rama

La rama `claude/migrate-sqlite-postgresql-wj32J` contiene:

1. ✅ **Migración SQLite → PostgreSQL**
   - Configuración de PostgreSQL en settings.py
   - Scripts de migración y verificación
   - Soporte para variables de entorno (.env)

2. ✅ **Scripts de Deployment**
   - Setup automatizado completo
   - Backups automáticos
   - Health checks
   - Configuraciones de Nginx, Supervisor, Gunicorn

3. ✅ **Fix de Concurrencia (CRÍTICO)**
   - Solución al KeyError en threads
   - Thread-safety en QUEUE_USER

---

## Opción 1: Actualización Solo del Fix de Concurrencia (RÁPIDO)

Si solo quieres el fix del KeyError y ya tienes el servidor funcionando:

```bash
# 1. Conectar al servidor
ssh root@20240807Ri7.vpsnet.es

# 2. Ir al directorio del proyecto
cd /opt/apimovil

# 3. Verificar qué cambios hay
git fetch origin
git log HEAD..origin/claude/migrate-sqlite-postgresql-wj32J --oneline

# 4. Hacer backup del código actual
cp app/views.py app/views.py.backup

# 5. Pull de los cambios
git pull origin claude/migrate-sqlite-postgresql-wj32J

# 6. Verificar cambios en views.py
git diff HEAD~1 app/views.py | head -50

# 7. Reiniciar servicios para aplicar cambios
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker
sudo supervisorctl restart celery_beat

# 8. Verificar que no haya errores
sudo supervisorctl status
sudo supervisorctl tail -f apimovil

# 9. Monitorear logs por 1-2 minutos
# Buscar que NO aparezca más el KeyError
# Ctrl+C para salir cuando confirmes que está bien
```

**Tiempo estimado: 2-3 minutos**

---

## Opción 2: Actualización Completa con PostgreSQL (RECOMENDADO)

Si quieres migrar a PostgreSQL y tener toda la infraestructura mejorada:

### Paso 1: Backup Completo

```bash
# Conectar al servidor
ssh root@20240807Ri7.vpsnet.es

# Ir al proyecto
cd /opt/apimovil

# Crear backup de SQLite (si existe)
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d) 2>/dev/null || true

# Backup de código actual
tar -czf /root/apimovil_backup_$(date +%Y%m%d).tar.gz /opt/apimovil
```

### Paso 2: Actualizar Código

```bash
cd /opt/apimovil

# Fetch de cambios
git fetch origin

# Ver qué cambios se traerán
git log HEAD..origin/claude/migrate-sqlite-postgresql-wj32J --oneline

# Pull de la rama
git pull origin claude/migrate-sqlite-postgresql-wj32J
```

### Paso 3: Configurar PostgreSQL

Ya tienes PostgreSQL instalado con `db_apimovil`, así que:

```bash
# Configurar permisos (ejecutar como postgres)
sudo -u postgres psql -f scripts/setup_postgres.sql

# O manualmente:
sudo -u postgres psql << EOF
GRANT ALL PRIVILEGES ON DATABASE db_apimovil TO admin;
\c db_apimovil
GRANT ALL ON SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO admin;
ALTER DATABASE db_apimovil OWNER TO admin;
\q
EOF
```

### Paso 4: Configurar Variables de Entorno

```bash
cd /opt/apimovil

# Crear archivo .env
nano .env
```

Contenido (ajusta el password):

```bash
# Django
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
DEBUG=False
ALLOWED_HOSTS=20240807Ri7.vpsnet.es,tu-dominio.com,localhost

# Database
DB_NAME=db_apimovil
DB_USER=admin
DB_PASSWORD=TU_PASSWORD_DE_ADMIN_AQUI
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

O genera el SECRET_KEY primero:

```bash
# Generar SECRET_KEY
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Copia el resultado y úsalo en .env
```

### Paso 5: Actualizar settings.py

```bash
nano apimovil/settings.py
```

Agregar al inicio (después de los imports):

```python
import os
from dotenv import load_dotenv
load_dotenv()
```

### Paso 6: Instalar Dependencias

```bash
# Activar entorno virtual
source venv/bin/activate

# Instalar nuevas dependencias
pip install python-dotenv psycopg2-binary

# Verificar que psycopg2 funcione
python -c "import psycopg2; print('PostgreSQL OK')"
```

### Paso 7: Migrar Datos (Opcional)

```bash
# Si tienes datos en SQLite que quieres migrar:

# 1. Exportar datos de SQLite
python manage.py dumpdata --natural-foreign --natural-primary \
    --exclude=contenttypes --exclude=auth.permission \
    --indent=2 > sqlite_data_backup.json

# 2. Aplicar migraciones a PostgreSQL
python manage.py migrate

# 3. Cargar datos
python manage.py loaddata sqlite_data_backup.json

# 4. Verificar
python verify_migration.py
```

O si es instalación nueva:

```bash
# Ejecutar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser
```

### Paso 8: Recolectar Estáticos

```bash
python manage.py collectstatic --noinput
```

### Paso 9: Reiniciar Servicios

```bash
# Reiniciar todos los servicios
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker
sudo supervisorctl restart celery_beat

# Verificar estado
sudo supervisorctl status
```

### Paso 10: Verificar

```bash
# Ejecutar health check
bash scripts/health_check.sh

# Ver logs
sudo supervisorctl tail -f apimovil

# Probar la aplicación
curl http://localhost:8000
curl http://20240807Ri7.vpsnet.es
```

**Tiempo estimado: 15-20 minutos**

---

## Opción 3: Actualización con Script Automatizado (MÁS FÁCIL)

Si quieres hacer todo automáticamente:

```bash
cd /opt/apimovil

# Pull de cambios
git pull origin claude/migrate-sqlite-postgresql-wj32J

# Ejecutar script de deployment
bash scripts/deploy.sh

# El script hace:
# - Backup automático
# - Pull del código
# - Instalación de dependencias
# - Migraciones
# - Collectstatic
# - Reinicio de servicios
```

**Tiempo estimado: 5-10 minutos**

---

## Verificación Post-Actualización

Después de cualquier opción, verifica:

```bash
# 1. Estado de servicios
sudo supervisorctl status
# Todos deben estar RUNNING

# 2. Logs en tiempo real
sudo supervisorctl tail -f apimovil
# NO debe aparecer KeyError

# 3. Health check completo
bash scripts/health_check.sh

# 4. Probar la aplicación
# Accede desde el navegador o:
curl -I http://20240807Ri7.vpsnet.es
```

---

## Rollback (Si Algo Sale Mal)

Si algo no funciona:

```bash
# Volver al código anterior
cd /opt/apimovil
git reset --hard HEAD~4  # Volver 4 commits atrás

# Reiniciar servicios
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker
```

O restaurar backup completo:

```bash
cd /opt
sudo rm -rf apimovil
sudo tar -xzf /root/apimovil_backup_YYYYMMDD.tar.gz
sudo supervisorctl restart all
```

---

## Resumen de Comandos (Copy-Paste Ready)

### Para Fix Rápido Solo (Opción 1):
```bash
ssh root@20240807Ri7.vpsnet.es
cd /opt/apimovil
git fetch origin
git pull origin claude/migrate-sqlite-postgresql-wj32J
sudo supervisorctl restart apimovil celery_worker celery_beat
sudo supervisorctl status
sudo supervisorctl tail -f apimovil
```

### Para Deployment Automatizado (Opción 3):
```bash
ssh root@20240807Ri7.vpsnet.es
cd /opt/apimovil
git pull origin claude/migrate-sqlite-postgresql-wj32J
bash scripts/deploy.sh
bash scripts/health_check.sh
```

---

## ¿Cuál Opción Elegir?

| Opción | Cuándo Usar | Tiempo |
|--------|-------------|--------|
| **Opción 1** | Solo necesitas el fix del KeyError | 2-3 min |
| **Opción 2** | Quieres migrar a PostgreSQL completo | 15-20 min |
| **Opción 3** | Quieres automatizar todo | 5-10 min |

---

## Recomendación

**Para ahora mismo**: Usa **Opción 1** (fix rápido) para eliminar el error inmediatamente.

**Para después**: Planea migrar a PostgreSQL con **Opción 2** en un momento de menos tráfico.

---

## Monitoreo Continuo

Después de actualizar:

```bash
# Monitorear logs por 5-10 minutos
sudo supervisorctl tail -f apimovil

# Buscar estas señales:
# ✓ NO debe aparecer: KeyError: 'GCCDianaramirez'
# ✓ Debe aparecer: "Porfavor asigne proxys" (si no hay proxies)
# ✓ Debe aparecer: "ÉXITO: Teléfono" (si hay proxies y funciona)
```

---

**¿Necesitas ayuda con algún paso específico?**
