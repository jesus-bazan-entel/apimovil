#!/bin/bash
# Script de backup para la aplicación apimovil
# Autor: Sistema de deployment
# Fecha: $(date +%Y-%m-%d)

set -e

# Configuración
PROJECT_DIR="/var/www/apimovil"
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="apimovil_db"
DB_USER="apimovil_user"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

# Limpiar backups antiguos (más de 7 días)
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.json.gz" -mtime +7 -delete

echo "================================================"
echo "Iniciando backup - $(date)"
echo "================================================"

# Backup de PostgreSQL
echo "1. Respaldando base de datos PostgreSQL..."
pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"
echo "   ✓ Base de datos respaldada: db_backup_$DATE.sql.gz"

# Backup de datos en formato JSON (Django)
echo "2. Exportando datos en formato JSON..."
cd "$PROJECT_DIR"
source venv/bin/activate
python manage.py dumpdata \
    --natural-foreign \
    --natural-primary \
    --exclude=contenttypes \
    --exclude=auth.permission \
    --indent=2 | gzip > "$BACKUP_DIR/django_data_$DATE.json.gz"
echo "   ✓ Datos exportados: django_data_$DATE.json.gz"

# Backup de archivos media (si existen)
if [ -d "$PROJECT_DIR/media" ]; then
    echo "3. Respaldando archivos media..."
    tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" -C "$PROJECT_DIR" media/
    echo "   ✓ Archivos media respaldados: media_$DATE.tar.gz"
fi

# Backup de configuración
echo "4. Respaldando archivos de configuración..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    "$PROJECT_DIR/.env" \
    "$PROJECT_DIR/apimovil/settings.py" \
    /etc/nginx/sites-available/apimovil \
    /etc/supervisor/conf.d/apimovil*.conf \
    /etc/supervisor/conf.d/celery*.conf 2>/dev/null || true
echo "   ✓ Configuración respaldada: config_$DATE.tar.gz"

# Calcular tamaño total de backups
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo ""
echo "================================================"
echo "Backup completado exitosamente"
echo "================================================"
echo "Ubicación: $BACKUP_DIR"
echo "Tamaño total: $TOTAL_SIZE"
echo "Archivos creados:"
ls -lh "$BACKUP_DIR"/*_$DATE.* 2>/dev/null || echo "  (ninguno)"
echo "================================================"

# Opcional: Enviar notificación
# curl -X POST https://tu-webhook.com/notificacion \
#   -d "mensaje=Backup completado: $DATE"

exit 0
