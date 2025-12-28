#!/bin/bash
# Script de configuración inicial para servidor Debian 12
# Específico para servidor con PostgreSQL ya instalado
# Autor: Sistema de deployment

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Setup Inicial - Servidor Debian 12${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Función para preguntar
ask() {
    local prompt="$1"
    local default="$2"
    local response

    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " response
        response=${response:-$default}
    else
        read -p "$prompt: " response
    fi

    echo "$response"
}

# Función para preguntar contraseña
ask_password() {
    local prompt="$1"
    local password
    local password2

    while true; do
        read -sp "$prompt: " password
        echo ""
        read -sp "Confirmar password: " password2
        echo ""

        if [ "$password" = "$password2" ]; then
            echo "$password"
            return 0
        else
            echo -e "${RED}Las contraseñas no coinciden. Intenta de nuevo.${NC}"
        fi
    done
}

echo -e "${YELLOW}Este script te ayudará a configurar el servidor paso a paso${NC}"
echo ""

# 1. Información del proyecto
echo -e "${GREEN}1. Configuración del Proyecto${NC}"
PROJECT_DIR=$(ask "Ruta del proyecto" "/var/www/apimovil")
echo ""

# 2. Base de datos
echo -e "${GREEN}2. Configuración de PostgreSQL${NC}"
echo "Bases de datos disponibles:"
sudo -u postgres psql -c "\l" | grep -E "^\s" | head -n 15
echo ""

DB_NAME=$(ask "Nombre de la base de datos" "db_apimovil")
DB_USER=$(ask "Usuario de PostgreSQL" "admin")
DB_PASSWORD=$(ask_password "Password del usuario PostgreSQL")
echo ""

# 3. Django
echo -e "${GREEN}3. Configuración de Django${NC}"
DOMAIN=$(ask "Dominio del servidor (sin http://)" "20240807Ri7.vpsnet.es")
echo ""

# 4. Generar SECRET_KEY
echo -e "${YELLOW}Generando SECRET_KEY...${NC}"
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || echo "CHANGE-THIS-SECRET-KEY-$(date +%s)")
echo -e "${GREEN}✓ SECRET_KEY generada${NC}"
echo ""

# 5. Confirmar configuración
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Configuración a Aplicar:${NC}"
echo -e "${BLUE}================================================${NC}"
echo "Directorio del proyecto: $PROJECT_DIR"
echo "Base de datos: $DB_NAME"
echo "Usuario DB: $DB_USER"
echo "Dominio: $DOMAIN"
echo -e "${BLUE}================================================${NC}"
echo ""

read -p "¿Continuar con esta configuración? (s/n): " confirm
if [ "$confirm" != "s" ]; then
    echo "Configuración cancelada."
    exit 0
fi

echo ""
echo -e "${GREEN}Iniciando configuración...${NC}"
echo ""

# 6. Crear directorio del proyecto si no existe
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Creando directorio del proyecto...${NC}"
    sudo mkdir -p "$PROJECT_DIR"
    sudo chown $USER:www-data "$PROJECT_DIR"
    echo -e "${GREEN}✓ Directorio creado${NC}"
fi

cd "$PROJECT_DIR"

# 7. Verificar si Git está inicializado
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}No se detectó repositorio Git.${NC}"
    read -p "¿Clonar desde GitHub? (s/n): " clone_git

    if [ "$clone_git" = "s" ]; then
        GIT_URL=$(ask "URL del repositorio Git")
        git clone "$GIT_URL" "$PROJECT_DIR"
    else
        echo -e "${RED}Asegúrate de copiar los archivos del proyecto a $PROJECT_DIR${NC}"
        exit 1
    fi
fi

# 8. Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creando entorno virtual...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Entorno virtual creado${NC}"
fi

# 9. Activar entorno e instalar dependencias
echo -e "${YELLOW}Instalando dependencias...${NC}"
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install python-dotenv gunicorn -q
echo -e "${GREEN}✓ Dependencias instaladas${NC}"

# 10. Crear archivo .env
echo -e "${YELLOW}Creando archivo .env...${NC}"
cat > .env << EOF
# Django Settings
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN,localhost,127.0.0.1

# Database
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EOF

chmod 600 .env
echo -e "${GREEN}✓ Archivo .env creado${NC}"

# 11. Actualizar settings.py
echo -e "${YELLOW}Verificando settings.py...${NC}"
if ! grep -q "load_dotenv" apimovil/settings.py; then
    echo -e "${YELLOW}Actualizando settings.py para usar .env...${NC}"
    # Backup
    cp apimovil/settings.py apimovil/settings.py.backup

    # Agregar imports al inicio
    sed -i '1i from dotenv import load_dotenv\nload_dotenv()\n' apimovil/settings.py
    echo -e "${GREEN}✓ settings.py actualizado${NC}"
else
    echo -e "${GREEN}✓ settings.py ya configurado${NC}"
fi

# 12. Crear directorios necesarios
echo -e "${YELLOW}Creando directorios necesarios...${NC}"
mkdir -p logs backups staticfiles media
echo -e "${GREEN}✓ Directorios creados${NC}"

# 13. Verificar conexión a PostgreSQL
echo -e "${YELLOW}Verificando conexión a PostgreSQL...${NC}"
if PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Conexión a PostgreSQL exitosa${NC}"
else
    echo -e "${RED}✗ No se pudo conectar a PostgreSQL${NC}"
    echo "Verifica el usuario, password y base de datos"
    exit 1
fi

# 14. Ejecutar migraciones
echo -e "${YELLOW}Ejecutando migraciones...${NC}"
python manage.py migrate
echo -e "${GREEN}✓ Migraciones aplicadas${NC}"

# 15. Crear superusuario
echo ""
echo -e "${YELLOW}¿Deseas crear un superusuario de Django ahora? (s/n)${NC}"
read -p "> " create_super
if [ "$create_super" = "s" ]; then
    python manage.py createsuperuser
fi

# 16. Recolectar archivos estáticos
echo -e "${YELLOW}Recolectando archivos estáticos...${NC}"
python manage.py collectstatic --noinput
echo -e "${GREEN}✓ Archivos estáticos recolectados${NC}"

# 17. Ajustar permisos
echo -e "${YELLOW}Ajustando permisos...${NC}"
sudo chown -R $USER:www-data "$PROJECT_DIR"
sudo chmod -R 755 "$PROJECT_DIR/staticfiles"
echo -e "${GREEN}✓ Permisos ajustados${NC}"

# 18. Probar Django
echo -e "${YELLOW}Verificando configuración de Django...${NC}"
python manage.py check
echo -e "${GREEN}✓ Django configurado correctamente${NC}"

# 19. Configurar Supervisor
echo ""
echo -e "${GREEN}Configurando Supervisor...${NC}"

# Actualizar rutas en configs
sed -i "s|/var/www/apimovil|$PROJECT_DIR|g" configs/supervisor_*.conf configs/gunicorn_config.py

# Copiar configs
sudo cp configs/supervisor_apimovil.conf /etc/supervisor/conf.d/
sudo cp configs/supervisor_celery_worker.conf /etc/supervisor/conf.d/
sudo cp configs/supervisor_celery_beat.conf /etc/supervisor/conf.d/
cp configs/gunicorn_config.py ./

echo -e "${GREEN}✓ Configuración de Supervisor copiada${NC}"

# 20. Configurar Nginx
echo -e "${GREEN}Configurando Nginx...${NC}"

# Crear config de Nginx con el dominio correcto
cp configs/nginx.conf /tmp/apimovil_nginx.conf
sed -i "s|tu-dominio.com|$DOMAIN|g" /tmp/apimovil_nginx.conf
sed -i "s|/var/www/apimovil|$PROJECT_DIR|g" /tmp/apimovil_nginx.conf

sudo cp /tmp/apimovil_nginx.conf /etc/nginx/sites-available/apimovil
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/apimovil /etc/nginx/sites-enabled/

# Probar config
if sudo nginx -t 2>/dev/null; then
    echo -e "${GREEN}✓ Configuración de Nginx válida${NC}"
else
    echo -e "${YELLOW}⚠ Advertencia: Revisa la configuración de Nginx${NC}"
fi

# 21. Iniciar servicios
echo ""
echo -e "${GREEN}Iniciando servicios...${NC}"

sudo supervisorctl reread
sudo supervisorctl update

sleep 2

sudo supervisorctl start apimovil
sudo supervisorctl start celery_worker
sudo supervisorctl start celery_beat

sleep 2

# Verificar estado
echo ""
echo -e "${GREEN}Estado de servicios:${NC}"
sudo supervisorctl status

# 22. Reiniciar Nginx
echo ""
echo -e "${YELLOW}Reiniciando Nginx...${NC}"
sudo systemctl restart nginx
echo -e "${GREEN}✓ Nginx reiniciado${NC}"

# 23. Resumen final
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Configuración Completada${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Proyecto: $PROJECT_DIR"
echo "Base de datos: $DB_NAME"
echo "Dominio: $DOMAIN"
echo ""
echo -e "${GREEN}Accede a tu aplicación en:${NC}"
echo "  http://$DOMAIN"
echo "  http://$DOMAIN/admin"
echo ""
echo -e "${YELLOW}Siguientes pasos:${NC}"
echo "  1. Configurar SSL: sudo certbot --nginx -d $DOMAIN"
echo "  2. Verificar salud: bash scripts/health_check.sh"
echo "  3. Crear backup: bash scripts/backup.sh"
echo ""
echo -e "${GREEN}Comandos útiles:${NC}"
echo "  Ver logs: sudo supervisorctl tail -f apimovil"
echo "  Reiniciar: sudo supervisorctl restart apimovil"
echo "  Estado: sudo supervisorctl status"
echo ""
echo -e "${BLUE}================================================${NC}"

exit 0
