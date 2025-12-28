# Migración SQLite → PostgreSQL

Este proyecto ha sido configurado para migrar de SQLite a PostgreSQL.

## Inicio Rápido

Si quieres realizar la migración inmediatamente, sigue estos pasos:

### 1. Instalar PostgreSQL
```bash
sudo apt install postgresql postgresql-contrib
```

### 2. Crear base de datos
```bash
sudo -u postgres psql
```
```sql
CREATE USER apimovil_user WITH PASSWORD 'tu_password';
CREATE DATABASE apimovil_db OWNER apimovil_user;
GRANT ALL PRIVILEGES ON DATABASE apimovil_db TO apimovil_user;
\q
```

### 3. Configurar variables de entorno
```bash
cp .env.example .env
nano .env  # Editar con tus credenciales
```

### 4. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 5. Ejecutar migración
```bash
# Exportar datos de SQLite (si tienes datos existentes)
python migrate_to_postgresql.py

# Aplicar migraciones a PostgreSQL
python manage.py migrate

# Importar datos (si exportaste en el paso anterior)
python manage.py loaddata sqlite_data_backup.json

# Verificar migración
python verify_migration.py
```

## Archivos Importantes

- **`MIGRATION_GUIDE.md`** - Guía detallada paso a paso
- **`migrate_to_postgresql.py`** - Script para exportar datos de SQLite
- **`verify_migration.py`** - Script para verificar que la migración fue exitosa
- **`.env.example`** - Plantilla de variables de entorno
- **`requirements.txt`** - Dependencias actualizadas (incluye psycopg2-binary)

## Cambios Realizados

### 1. `requirements.txt`
Se agregaron las siguientes dependencias:
- `psycopg2-binary==2.9.9` - Driver de PostgreSQL
- `Django==3.2.25` - Framework (ahora explícito)
- `django-cors-headers==4.3.1` - CORS
- `celery==5.3.6` - Tareas asíncronas
- `redis==5.0.1` - Backend para Celery

### 2. `apimovil/settings.py`
- Configuración de PostgreSQL usando variables de entorno
- Configuración de SQLite comentada (por si necesitas volver)
- Soporte para `.env` file (requiere `python-dotenv`)

### 3. `.gitignore`
- Se agregó `.env` para proteger credenciales

### 4. Scripts de Migración
- **`migrate_to_postgresql.py`**: Exporta datos de SQLite a JSON
- **`verify_migration.py`**: Verifica que la migración fue exitosa

## Configuración

### Variables de Entorno Requeridas

```bash
DB_NAME=apimovil_db          # Nombre de la base de datos
DB_USER=apimovil_user        # Usuario de PostgreSQL
DB_PASSWORD=password         # Contraseña del usuario
DB_HOST=localhost            # Host (localhost para local)
DB_PORT=5432                 # Puerto (5432 por defecto)
```

### Configuración Opcional: python-dotenv

Si quieres usar archivos `.env`, instala:
```bash
pip install python-dotenv
```

Y agrega al inicio de `settings.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Verificación Post-Migración

Después de migrar, ejecuta:

```bash
python verify_migration.py
```

Este script verificará:
- ✓ Conexión a PostgreSQL
- ✓ Cantidad de registros migrados
- ✓ Índices creados correctamente
- ✓ Integridad de relaciones (foreign keys)
- ✓ Consultas funcionan correctamente

## Rollback (Volver a SQLite)

Si algo sale mal, puedes volver a SQLite:

1. En `settings.py`, comenta la sección de PostgreSQL
2. Descomenta la sección de SQLite
3. Restaura el backup: `cp db.sqlite3.backup db.sqlite3`
4. Reinicia la aplicación

## Ventajas de PostgreSQL

- **Mejor rendimiento** en consultas complejas
- **Concurrencia real** (múltiples escrituras simultáneas)
- **Tipos de datos avanzados** (JSON, Arrays, etc.)
- **Índices más potentes** (GiN, GiST, etc.)
- **Escalabilidad** para producción
- **Integridad de datos** más robusta
- **Full-text search** nativo
- **Replicación y alta disponibilidad**

## Modelos Incluidos

El proyecto tiene 4 modelos principales:

1. **Consecutive** - Gestión de consecutivos de archivos
2. **Movil** - Información de números móviles (indexado)
3. **Proxy** - Configuración de proxies
4. **BlockIp** - IPs bloqueadas

Todos con relaciones ForeignKey hacia User y entre sí.

## Soporte

Para más información, consulta:
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Guía detallada
- [Documentación de Django](https://docs.djangoproject.com/en/3.2/)
- [Documentación de PostgreSQL](https://www.postgresql.org/docs/)

## Troubleshooting Común

### Error: "psycopg2.OperationalError: FATAL: Peer authentication failed"
Solución: Edita `/etc/postgresql/XX/main/pg_hba.conf` y cambia `peer` a `md5`

### Error: "django.db.utils.OperationalError: could not connect to server"
Solución: Verifica que PostgreSQL esté corriendo: `sudo systemctl status postgresql`

### Los datos no se importaron
Solución: Verifica que ejecutaste `migrate` antes de `loaddata`

---

**¿Necesitas ayuda?** Revisa [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) para instrucciones detalladas.
