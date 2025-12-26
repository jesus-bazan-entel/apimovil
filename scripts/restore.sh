#!/bin/bash
# Script de restauración para la aplicación apimovil
# Autor: Sistema de deployment
# Fecha: $(date +%Y-%m-%d)

set -e

# Configuración
PROJECT_DIR="/var/www/apimovil"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_NAME="apimovil_db"
DB_USER="apimovil_user"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para mostrar uso
usage() {
    echo "Uso: $0 [FECHA]"
    echo ""
    echo "Ejemplo: $0 20240101_120000"
    echo ""
    echo "Backups disponibles:"
    ls -1 "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | \
        sed 's/.*db_backup_\(.*\)\.sql\.gz/  - \1/' || echo "  (ninguno)"
    exit 1
}

# Verificar argumento
if [ -z "$1" ]; then
    usage
fi

DATE=$1

# Verificar que exista el backup
if [ ! -f "$BACKUP_DIR/db_backup_$DATE.sql.gz" ]; then
    echo -e "${RED}Error: No se encontró el backup para la fecha $DATE${NC}"
    echo ""
    usage
fi

# Confirmación
echo -e "${YELLOW}================================================${NC}"
echo -e "${YELLOW}ADVERTENCIA: Restauración de backup${NC}"
echo -e "${YELLOW}================================================${NC}"
echo ""
echo "Esto restaurará los datos de: $DATE"
echo ""
echo -e "${RED}ESTO ELIMINARÁ TODOS LOS DATOS ACTUALES${NC}"
echo ""
read -p "¿Estás seguro? (escribe 'SI' para continuar): " confirm

if [ "$confirm" != "SI" ]; then
    echo "Operación cancelada."
    exit 0
fi

echo ""
echo -e "${GREEN}Iniciando restauración...${NC}"
echo ""

# Detener servicios
echo "1. Deteniendo servicios..."
sudo supervisorctl stop apimovil celery_worker celery_beat 2>/dev/null || true
echo "   ✓ Servicios detenidos"

# Restaurar base de datos
echo "2. Restaurando base de datos..."
gunzip -c "$BACKUP_DIR/db_backup_$DATE.sql.gz" | psql -U "$DB_USER" "$DB_NAME"
echo "   ✓ Base de datos restaurada"

# Restaurar media (si existe)
if [ -f "$BACKUP_DIR/media_$DATE.tar.gz" ]; then
    echo "3. Restaurando archivos media..."
    rm -rf "$PROJECT_DIR/media"
    tar -xzf "$BACKUP_DIR/media_$DATE.tar.gz" -C "$PROJECT_DIR"
    echo "   ✓ Archivos media restaurados"
fi

# Aplicar migraciones pendientes
echo "4. Aplicando migraciones..."
cd "$PROJECT_DIR"
source venv/bin/activate
python manage.py migrate
echo "   ✓ Migraciones aplicadas"

# Reiniciar servicios
echo "5. Reiniciando servicios..."
sudo supervisorctl start apimovil celery_worker celery_beat
sleep 3
sudo supervisorctl status
echo "   ✓ Servicios reiniciados"

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Restauración completada exitosamente${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

exit 0
