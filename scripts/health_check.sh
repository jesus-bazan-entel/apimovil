#!/bin/bash
# Script de verificación de salud del sistema
# Autor: Sistema de deployment
# Fecha: $(date +%Y-%m-%d)

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "================================================"
echo "Health Check - apimovil"
echo "$(date)"
echo "================================================"
echo ""

# 1. Verificar servicios de Supervisor
echo "1. Estado de servicios (Supervisor):"
if command -v supervisorctl &> /dev/null; then
    sudo supervisorctl status | while read line; do
        if echo "$line" | grep -q "RUNNING"; then
            echo -e "   ${GREEN}✓${NC} $line"
        else
            echo -e "   ${RED}✗${NC} $line"
        fi
    done
else
    echo -e "   ${RED}✗ Supervisor no instalado${NC}"
fi
echo ""

# 2. Verificar PostgreSQL
echo "2. PostgreSQL:"
if systemctl is-active --quiet postgresql; then
    echo -e "   ${GREEN}✓${NC} PostgreSQL está corriendo"

    # Verificar conexión
    if psql -U apimovil_user -d apimovil_db -h localhost -c "SELECT 1;" &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} Conexión a base de datos OK"

        # Contar registros
        MOVILES=$(psql -U apimovil_user -d apimovil_db -h localhost -t -c "SELECT COUNT(*) FROM app_movil;" 2>/dev/null | xargs)
        echo "     - Móviles: $MOVILES"
    else
        echo -e "   ${RED}✗${NC} No se puede conectar a la base de datos"
    fi
else
    echo -e "   ${RED}✗${NC} PostgreSQL no está corriendo"
fi
echo ""

# 3. Verificar Redis
echo "3. Redis:"
if systemctl is-active --quiet redis-server; then
    echo -e "   ${GREEN}✓${NC} Redis está corriendo"

    # Verificar conexión
    if redis-cli ping &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} Conexión a Redis OK"

        # Info de memoria
        REDIS_MEM=$(redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        echo "     - Memoria usada: $REDIS_MEM"
    else
        echo -e "   ${RED}✗${NC} No se puede conectar a Redis"
    fi
else
    echo -e "   ${RED}✗${NC} Redis no está corriendo"
fi
echo ""

# 4. Verificar Nginx
echo "4. Nginx:"
if systemctl is-active --quiet nginx; then
    echo -e "   ${GREEN}✓${NC} Nginx está corriendo"

    # Verificar configuración
    if sudo nginx -t &> /dev/null; then
        echo -e "   ${GREEN}✓${NC} Configuración de Nginx OK"
    else
        echo -e "   ${YELLOW}⚠${NC} Problemas en configuración de Nginx"
    fi
else
    echo -e "   ${RED}✗${NC} Nginx no está corriendo"
fi
echo ""

# 5. Verificar aplicación web
echo "5. Aplicación web:"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "   ${GREEN}✓${NC} Aplicación respondiendo (HTTP $HTTP_CODE)"
else
    echo -e "   ${RED}✗${NC} Aplicación no responde (HTTP $HTTP_CODE)"
fi
echo ""

# 6. Verificar espacio en disco
echo "6. Espacio en disco:"
df -h / | tail -n 1 | while read line; do
    USAGE=$(echo $line | awk '{print $5}' | sed 's/%//')
    if [ "$USAGE" -lt 80 ]; then
        echo -e "   ${GREEN}✓${NC} Espacio suficiente: $line"
    elif [ "$USAGE" -lt 90 ]; then
        echo -e "   ${YELLOW}⚠${NC} Espacio limitado: $line"
    else
        echo -e "   ${RED}✗${NC} Espacio crítico: $line"
    fi
done
echo ""

# 7. Verificar memoria
echo "7. Memoria:"
free -h | grep Mem | while read line; do
    TOTAL=$(echo $line | awk '{print $2}')
    USED=$(echo $line | awk '{print $3}')
    AVAIL=$(echo $line | awk '{print $7}')
    echo "   Total: $TOTAL | Usado: $USED | Disponible: $AVAIL"
done
echo ""

# 8. Verificar carga del sistema
echo "8. Carga del sistema:"
LOAD=$(uptime | awk -F'load average:' '{print $2}')
echo "   Carga promedio:$LOAD"
echo ""

# 9. Verificar SSL (si está configurado)
echo "9. Certificado SSL:"
if [ -d "/etc/letsencrypt/live" ]; then
    CERT_DIR=$(ls -t /etc/letsencrypt/live | head -n 1)
    if [ -n "$CERT_DIR" ]; then
        CERT_FILE="/etc/letsencrypt/live/$CERT_DIR/cert.pem"
        if [ -f "$CERT_FILE" ]; then
            EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_FILE" | cut -d= -f2)
            echo -e "   ${GREEN}✓${NC} Certificado encontrado"
            echo "     - Dominio: $CERT_DIR"
            echo "     - Expira: $EXPIRY"
        fi
    fi
else
    echo "   - SSL no configurado"
fi
echo ""

# 10. Verificar últimos errores en logs
echo "10. Últimos errores en logs:"
ERROR_COUNT=$(sudo tail -n 100 /var/www/apimovil/logs/gunicorn_error.log 2>/dev/null | grep -i error | wc -l || echo "0")
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "   ${GREEN}✓${NC} No hay errores recientes"
else
    echo -e "   ${YELLOW}⚠${NC} $ERROR_COUNT errores en los últimos 100 registros"
    echo "     Ver: sudo tail -n 50 /var/www/apimovil/logs/gunicorn_error.log"
fi
echo ""

echo "================================================"
echo "Health Check completado"
echo "================================================"
echo ""

exit 0
