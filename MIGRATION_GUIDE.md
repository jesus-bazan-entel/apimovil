# Guía de Migración: SQLite a PostgreSQL

Esta guía te ayudará a migrar tu aplicación Django de SQLite a PostgreSQL de manera segura.

## Tabla de Contenidos
1. [Pre-requisitos](#pre-requisitos)
2. [Paso 1: Backup de datos actuales](#paso-1-backup-de-datos-actuales)
3. [Paso 2: Instalar PostgreSQL](#paso-2-instalar-postgresql)
4. [Paso 3: Configurar PostgreSQL](#paso-3-configurar-postgresql)
5. [Paso 4: Actualizar dependencias](#paso-4-actualizar-dependencias)
6. [Paso 5: Configurar variables de entorno](#paso-5-configurar-variables-de-entorno)
7. [Paso 6: Migrar esquema y datos](#paso-6-migrar-esquema-y-datos)
8. [Paso 7: Verificar migración](#paso-7-verificar-migración)
9. [Troubleshooting](#troubleshooting)

---

## Pre-requisitos

- Acceso al servidor con permisos de administrador
- Python 3.x instalado
- Git instalado (para control de versiones)

---

## Paso 1: Backup de datos actuales

Antes de hacer cualquier cambio, haz un backup completo:

```bash
# 1. Backup de la base de datos SQLite
cp db.sqlite3 db.sqlite3.backup

# 2. Exportar datos usando el script proporcionado
# IMPORTANTE: Primero asegúrate de que settings.py esté configurado para SQLite
python migrate_to_postgresql.py
```

Esto creará un archivo `sqlite_data_backup.json` con todos tus datos.

---

## Paso 2: Instalar PostgreSQL

### En Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### En CentOS/RHEL:
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Verificar instalación:
```bash
sudo systemctl status postgresql
```

---

## Paso 3: Configurar PostgreSQL

### 3.1 Acceder a PostgreSQL como superusuario:
```bash
sudo -u postgres psql
```

### 3.2 Crear base de datos y usuario:
```sql
-- Crear usuario
CREATE USER apimovil_user WITH PASSWORD 'tu_password_seguro';

-- Crear base de datos
CREATE DATABASE apimovil_db OWNER apimovil_user;

-- Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE apimovil_db TO apimovil_user;

-- Salir
\q
```

### 3.3 Configurar autenticación (opcional):
Edita el archivo `pg_hba.conf`:
```bash
sudo nano /etc/postgresql/[version]/main/pg_hba.conf
```

Asegúrate de que estas líneas estén presentes:
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
# IPv6 local connections:
host    all             all             ::1/128                 md5
```

Reinicia PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## Paso 4: Actualizar dependencias

```bash
# Instalar nuevas dependencias
pip install -r requirements.txt

# Verificar instalación de psycopg2
python -c "import psycopg2; print('psycopg2 instalado correctamente')"
```

---

## Paso 5: Configurar variables de entorno

### Opción A: Crear archivo .env
```bash
# Copiar el ejemplo
cp .env.example .env

# Editar con tus credenciales
nano .env
```

Contenido del archivo `.env`:
```bash
DB_NAME=apimovil_db
DB_USER=apimovil_user
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432
```

### Opción B: Variables de entorno del sistema
```bash
export DB_NAME=apimovil_db
export DB_USER=apimovil_user
export DB_PASSWORD=tu_password_seguro
export DB_HOST=localhost
export DB_PORT=5432
```

**IMPORTANTE**: Si usas la opción A, necesitas instalar `python-dotenv` y modificar `settings.py`:

```bash
pip install python-dotenv
```

Agregar al inicio de `settings.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Paso 6: Migrar esquema y datos

### 6.1 Probar conexión a PostgreSQL:
```bash
python manage.py check --database default
```

### 6.2 Crear esquema en PostgreSQL:
```bash
# Aplicar migraciones
python manage.py migrate
```

### 6.3 Importar datos desde SQLite:
```bash
# Cargar los datos exportados
python manage.py loaddata sqlite_data_backup.json
```

### 6.4 Crear superusuario (si es necesario):
```bash
python manage.py createsuperuser
```

---

## Paso 7: Verificar migración

### 7.1 Verificar cantidad de registros:

```bash
python manage.py shell
```

En el shell de Python:
```python
from app.models import Movil, Consecutive, Proxy, BlockIp
from django.contrib.auth.models import User

print(f"Usuarios: {User.objects.count()}")
print(f"Móviles: {Movil.objects.count()}")
print(f"Consecutivos: {Consecutive.objects.count()}")
print(f"Proxies: {Proxy.objects.count()}")
print(f"IPs bloqueadas: {BlockIp.objects.count()}")
```

### 7.2 Probar el servidor:
```bash
python manage.py runserver
```

Accede a: `http://localhost:8000/admin`

### 7.3 Verificar tareas de Celery:
```bash
# Iniciar worker de Celery
celery -A apimovil worker --loglevel=info

# En otra terminal, iniciar Beat
celery -A apimovil beat --loglevel=info
```

---

## Troubleshooting

### Error: "FATAL: role 'postgres' does not exist"
```bash
# Crear el rol postgres si no existe
sudo -u postgres createuser -s postgres
```

### Error: "FATAL: database 'apimovil_db' does not exist"
```bash
# Crear la base de datos manualmente
sudo -u postgres createdb apimovil_db
```

### Error: "psycopg2.OperationalError: FATAL: Peer authentication failed"
Revisa el archivo `pg_hba.conf` y cambia `peer` a `md5` para conexiones locales.

### Error al importar datos: "IntegrityError"
```bash
# Limpiar la base de datos y volver a intentar
python manage.py flush
python manage.py migrate
python manage.py loaddata sqlite_data_backup.json
```

### Los datos no aparecen después de loaddata
Verifica que el archivo JSON no esté vacío:
```bash
ls -lh sqlite_data_backup.json
```

### Error: "relation does not exist"
```bash
# Asegúrate de ejecutar las migraciones antes de cargar datos
python manage.py migrate
```

---

## Rollback a SQLite (en caso de emergencia)

Si algo sale mal, puedes volver a SQLite:

1. Edita `apimovil/settings.py` y comenta la configuración de PostgreSQL
2. Descomenta la configuración de SQLite
3. Restaura el backup: `cp db.sqlite3.backup db.sqlite3`
4. Reinicia la aplicación

---

## Mejoras de Rendimiento Post-Migración

Una vez que la migración esté completa, considera:

### 1. Indexar campos frecuentemente consultados:
```python
# Ya tienes índices en los modelos, pero puedes agregar más si es necesario
```

### 2. Configurar connection pooling:
```python
# En settings.py, bajo DATABASES['default']['OPTIONS']:
'OPTIONS': {
    'connect_timeout': 10,
    'options': '-c statement_timeout=30000',  # 30 segundos
},
'CONN_MAX_AGE': 600,  # Mantener conexiones por 10 minutos
```

### 3. Configurar PostgreSQL para mejor rendimiento:
```bash
sudo nano /etc/postgresql/[version]/main/postgresql.conf
```

Ajustar según tu RAM disponible:
```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 16MB
```

---

## Mantenimiento PostgreSQL

### Backup regular:
```bash
# Backup de la base de datos
pg_dump -U apimovil_user apimovil_db > backup_$(date +%Y%m%d).sql

# Backup comprimido
pg_dump -U apimovil_user apimovil_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restaurar backup:
```bash
psql -U apimovil_user apimovil_db < backup_20240101.sql
```

### Vacuuming regular (limpieza):
```bash
# Ejecutar manualmente
psql -U apimovil_user -d apimovil_db -c "VACUUM ANALYZE;"
```

---

## Checklist final

- [ ] Backup de SQLite realizado
- [ ] PostgreSQL instalado y funcionando
- [ ] Base de datos y usuario creados
- [ ] Dependencias instaladas (`psycopg2-binary`)
- [ ] Variables de entorno configuradas
- [ ] Migraciones aplicadas (`python manage.py migrate`)
- [ ] Datos importados (`loaddata`)
- [ ] Verificación de cantidad de registros
- [ ] Servidor de desarrollo funciona
- [ ] Admin de Django accesible
- [ ] Celery worker funcionando
- [ ] Celery beat funcionando
- [ ] Plan de backup implementado

---

## Recursos adicionales

- [Documentación oficial de PostgreSQL](https://www.postgresql.org/docs/)
- [Django Database Configuration](https://docs.djangoproject.com/en/3.2/ref/settings/#databases)
- [psycopg2 documentation](https://www.psycopg.org/docs/)

---

## Soporte

Si encuentras problemas durante la migración, verifica:
1. Los logs de PostgreSQL: `/var/log/postgresql/`
2. Los logs de Django: `django_debug.log`
3. Los logs de Celery

Para preguntas específicas, consulta la documentación oficial o abre un issue en el repositorio.
