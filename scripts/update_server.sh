#!/bin/bash
# Script de actualización rápida del servidor
# Ejecutar en el servidor: bash scripts/update_server.sh

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Actualización del Servidor - apimovil${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Detectar ubicación del proyecto
if [ -d "/opt/apimovil" ]; then
    PROJECT_DIR="/opt/apimovil"
elif [ -d "/var/www/apimovil" ]; then
    PROJECT_DIR="/var/www/apimovil"
else
    echo -e "${RED}No se encontró el proyecto en /opt/apimovil ni /var/www/apimovil${NC}"
    read -p "Ingresa la ruta del proyecto: " PROJECT_DIR
fi

echo -e "${YELLOW}Proyecto detectado en: $PROJECT_DIR${NC}"
echo ""

cd "$PROJECT_DIR"

# Verificar que estamos en un repo Git
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: $PROJECT_DIR no es un repositorio Git${NC}"
    exit 1
fi

# Mostrar rama actual
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${YELLOW}Rama actual: $CURRENT_BRANCH${NC}"
echo ""

# Preguntar qué tipo de actualización
echo "Selecciona el tipo de actualización:"
echo ""
echo "1) Fix Rápido (solo KeyError thread safety) - 2 minutos"
echo "2) Actualización Completa - 5 minutos"
echo "3) Ver cambios disponibles sin aplicar"
echo "4) Cancelar"
echo ""
read -p "Opción [1-4]: " OPTION

case $OPTION in
    1)
        echo ""
        echo -e "${GREEN}Opción 1: Fix Rápido${NC}"
        ;;
    2)
        echo ""
        echo -e "${GREEN}Opción 2: Actualización Completa${NC}"
        ;;
    3)
        echo ""
        echo -e "${YELLOW}Cambios disponibles:${NC}"
        git fetch origin
        git log HEAD..origin/claude/migrate-sqlite-postgresql-wj32J --oneline --decorate
        echo ""
        git diff HEAD..origin/claude/migrate-sqlite-postgresql-wj32J --stat
        exit 0
        ;;
    4)
        echo "Cancelado."
        exit 0
        ;;
    *)
        echo -e "${RED}Opción inválida${NC}"
        exit 1
        ;;
esac

echo ""
read -p "¿Continuar con la actualización? (s/n): " CONFIRM
if [ "$CONFIRM" != "s" ]; then
    echo "Cancelado."
    exit 0
fi

# Paso 1: Backup del código actual
echo ""
echo -e "${YELLOW}1. Creando backup del código actual...${NC}"
BACKUP_FILE="$PROJECT_DIR/backup_pre_update_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$BACKUP_FILE" \
    --exclude='venv' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='staticfiles' \
    --exclude='logs' \
    --exclude='*.log' \
    . 2>/dev/null || true
echo -e "${GREEN}✓ Backup creado: $BACKUP_FILE${NC}"

# Paso 2: Verificar servicios antes
echo ""
echo -e "${YELLOW}2. Estado de servicios antes de actualizar:${NC}"
sudo supervisorctl status || echo "Supervisor no disponible"

# Paso 3: Fetch y Pull
echo ""
echo -e "${YELLOW}3. Descargando cambios...${NC}"
git fetch origin

echo ""
echo -e "${YELLOW}Cambios que se aplicarán:${NC}"
git log HEAD..origin/claude/migrate-sqlite-postgresql-wj32J --oneline | head -10

echo ""
read -p "¿Aplicar estos cambios? (s/n): " APPLY
if [ "$APPLY" != "s" ]; then
    echo "Actualización cancelada."
    exit 0
fi

git pull origin claude/migrate-sqlite-postgresql-wj32J
echo -e "${GREEN}✓ Código actualizado${NC}"

# Paso 4: Instalar dependencias (solo si es actualización completa)
if [ "$OPTION" = "2" ]; then
    echo ""
    echo -e "${YELLOW}4. Instalando dependencias...${NC}"

    if [ -d "venv" ]; then
        source venv/bin/activate
        pip install -r requirements.txt -q
        pip install python-dotenv -q 2>/dev/null || true
        echo -e "${GREEN}✓ Dependencias instaladas${NC}"
    else
        echo -e "${YELLOW}⚠ No se encontró entorno virtual, saltando...${NC}"
    fi

    # Paso 5: Ejecutar migraciones (solo si es actualización completa)
    echo ""
    echo -e "${YELLOW}5. Ejecutando migraciones...${NC}"
    if [ -f "manage.py" ]; then
        python manage.py migrate --noinput
        echo -e "${GREEN}✓ Migraciones aplicadas${NC}"
    fi

    # Paso 6: Collectstatic
    echo ""
    echo -e "${YELLOW}6. Recolectando archivos estáticos...${NC}"
    python manage.py collectstatic --noinput
    echo -e "${GREEN}✓ Estáticos recolectados${NC}"
fi

# Paso 7: Reiniciar servicios
echo ""
echo -e "${YELLOW}7. Reiniciando servicios...${NC}"

if command -v supervisorctl &> /dev/null; then
    sudo supervisorctl restart apimovil 2>/dev/null || echo "No se pudo reiniciar apimovil"
    sudo supervisorctl restart celery_worker 2>/dev/null || echo "No se pudo reiniciar celery_worker"
    sudo supervisorctl restart celery_beat 2>/dev/null || echo "No se pudo reiniciar celery_beat"

    sleep 2

    echo -e "${GREEN}✓ Servicios reiniciados${NC}"
else
    echo -e "${YELLOW}⚠ Supervisor no disponible, reinicia manualmente${NC}"
fi

# Paso 8: Verificar estado
echo ""
echo -e "${YELLOW}8. Verificando estado de servicios...${NC}"
sleep 2

if command -v supervisorctl &> /dev/null; then
    sudo supervisorctl status
else
    echo "Supervisor no disponible"
fi

# Resumen final
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Actualización Completada${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo -e "${GREEN}Cambios aplicados exitosamente${NC}"
echo ""
echo "Backup creado en: $BACKUP_FILE"
echo ""
echo -e "${YELLOW}Siguientes pasos:${NC}"
echo "  1. Monitorear logs: sudo supervisorctl tail -f apimovil"
echo "  2. Verificar salud: bash scripts/health_check.sh"
echo "  3. Probar aplicación en navegador"
echo ""
echo -e "${YELLOW}Rollback (si algo sale mal):${NC}"
echo "  cd $PROJECT_DIR"
echo "  tar -xzf $BACKUP_FILE"
echo "  sudo supervisorctl restart all"
echo ""
echo -e "${BLUE}================================================${NC}"

# Preguntar si quiere ver logs
echo ""
read -p "¿Ver logs en tiempo real? (s/n): " VIEW_LOGS
if [ "$VIEW_LOGS" = "s" ]; then
    echo ""
    echo -e "${YELLOW}Mostrando logs... (Ctrl+C para salir)${NC}"
    echo ""
    sleep 2
    sudo supervisorctl tail -f apimovil
fi

exit 0
