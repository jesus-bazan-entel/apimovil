#!/bin/bash
# Script de deployment automatizado para apimovil
# Autor: Sistema de deployment
# Fecha: $(date +%Y-%m-%d)

set -e

# Configuración
PROJECT_DIR="/var/www/apimovil"
VENV_DIR="$PROJECT_DIR/venv"
GIT_BRANCH="${1:-main}"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Iniciando deployment de apimovil${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# 1. Backup antes de deployment
echo -e "${YELLOW}1. Creando backup de seguridad...${NC}"
bash "$PROJECT_DIR/scripts/backup.sh"
echo ""

# 2. Actualizar código desde Git
echo -e "${YELLOW}2. Actualizando código desde Git (branch: $GIT_BRANCH)...${NC}"
cd "$PROJECT_DIR"
git fetch origin
git checkout "$GIT_BRANCH"
git pull origin "$GIT_BRANCH"
echo -e "${GREEN}   ✓ Código actualizado${NC}"
echo ""

# 3. Activar entorno virtual
echo -e "${YELLOW}3. Activando entorno virtual...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}   ✓ Entorno virtual activado${NC}"
echo ""

# 4. Instalar/actualizar dependencias
echo -e "${YELLOW}4. Instalando/actualizando dependencias...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}   ✓ Dependencias actualizadas${NC}"
echo ""

# 5. Ejecutar migraciones
echo -e "${YELLOW}5. Ejecutando migraciones de base de datos...${NC}"
python manage.py makemigrations --noinput
python manage.py migrate --noinput
echo -e "${GREEN}   ✓ Migraciones aplicadas${NC}"
echo ""

# 6. Recolectar archivos estáticos
echo -e "${YELLOW}6. Recolectando archivos estáticos...${NC}"
python manage.py collectstatic --noinput
echo -e "${GREEN}   ✓ Archivos estáticos recolectados${NC}"
echo ""

# 7. Verificar configuración
echo -e "${YELLOW}7. Verificando configuración de Django...${NC}"
python manage.py check
echo -e "${GREEN}   ✓ Configuración verificada${NC}"
echo ""

# 8. Reiniciar servicios
echo -e "${YELLOW}8. Reiniciando servicios...${NC}"
sudo supervisorctl restart apimovil
sudo supervisorctl restart celery_worker
sudo supervisorctl restart celery_beat
sleep 3
echo -e "${GREEN}   ✓ Servicios reiniciados${NC}"
echo ""

# 9. Verificar estado de servicios
echo -e "${YELLOW}9. Verificando estado de servicios...${NC}"
sudo supervisorctl status
echo ""

# 10. Recargar Nginx
echo -e "${YELLOW}10. Recargando Nginx...${NC}"
sudo nginx -t
sudo systemctl reload nginx
echo -e "${GREEN}   ✓ Nginx recargado${NC}"
echo ""

# 11. Verificar aplicación
echo -e "${YELLOW}11. Verificando que la aplicación responda...${NC}"
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}   ✓ Aplicación respondiendo (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}   ✗ Aplicación no responde correctamente (HTTP $HTTP_CODE)${NC}"
    echo -e "${RED}   Verifica los logs con: sudo supervisorctl tail -f apimovil${NC}"
fi
echo ""

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Deployment completado exitosamente${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Información del deployment:"
echo "  - Fecha: $(date)"
echo "  - Branch: $GIT_BRANCH"
echo "  - Commit: $(git rev-parse --short HEAD)"
echo "  - Mensaje: $(git log -1 --pretty=%B | head -n 1)"
echo ""
echo "Comandos útiles:"
echo "  - Ver logs: sudo supervisorctl tail -f apimovil"
echo "  - Ver estado: sudo supervisorctl status"
echo "  - Rollback: bash scripts/restore.sh [FECHA]"
echo ""

exit 0
