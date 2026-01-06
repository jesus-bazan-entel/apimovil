#!/bin/bash
#
# Script para aplicar fix del error index_proxy
# Uso: bash apply_fix.sh
#

echo "==============================================="
echo "  APLICANDO FIX - index_proxy"
echo "==============================================="
echo ""

APIMOVIL_DIR="/opt/apimovil"
APP_DIR="$APIMOVIL_DIR/app"

# Verificar que existe el directorio
if [ ! -d "$APP_DIR" ]; then
    echo "❌ ERROR: No se encuentra $APP_DIR"
    exit 1
fi

# Hacer backup del archivo actual
if [ -f "$APP_DIR/browser_extended.py" ]; then
    echo "📦 Creando backup..."
    cp "$APP_DIR/browser_extended.py" "$APP_DIR/browser_extended.py.before_fix"
    echo "   ✅ Backup guardado en: browser_extended.py.before_fix"
fi

# Verificar que existe el archivo de fix
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$SCRIPT_DIR/browser_extended.py" ]; then
    echo "❌ ERROR: No se encuentra browser_extended.py en $SCRIPT_DIR"
    echo "   Asegúrate de tener el archivo en el mismo directorio que este script"
    exit 1
fi

# Copiar archivo corregido
echo ""
echo "📥 Aplicando fix..."
cp "$SCRIPT_DIR/browser_extended.py" "$APP_DIR/browser_extended.py"

# Ajustar permisos
chown www-data:www-data "$APP_DIR/browser_extended.py"
chmod 644 "$APP_DIR/browser_extended.py"
echo "   ✅ Archivo actualizado"

# Verificar que el método nuevo existe
if grep -q "_get_current_proxy_index" "$APP_DIR/browser_extended.py"; then
    echo "   ✅ Verificación: Método _get_current_proxy_index encontrado"
else
    echo "   ⚠️  ADVERTENCIA: No se encontró el método _get_current_proxy_index"
fi

# Reiniciar Celery
echo ""
echo "🔄 Reiniciando Celery..."
if command -v supervisorctl &> /dev/null; then
    supervisorctl restart celery_worker
    echo "   ✅ Celery reiniciado"
    sleep 2
    echo ""
    echo "📊 Estado de Celery:"
    supervisorctl status celery_worker
else
    echo "   ⚠️  supervisorctl no encontrado"
    echo "   Reinicia Celery manualmente:"
    echo "   sudo supervisorctl restart celery_worker"
fi

echo ""
echo "==============================================="
echo "  ✅ FIX APLICADO CORRECTAMENTE"
echo "==============================================="
echo ""
echo "📝 Próximos pasos:"
echo ""
echo "1. Verificar logs:"
echo "   sudo supervisorctl tail -f celery_worker stderr"
echo ""
echo "2. Buscar el error anterior (no debe aparecer):"
echo "   sudo supervisorctl tail -1000 celery_worker stderr | grep 'index_proxy'"
echo ""
echo "3. Si todo está bien, debería estar vacío ✅"
echo ""
echo "Para restaurar versión anterior:"
echo "   cp $APP_DIR/browser_extended.py.before_fix $APP_DIR/browser_extended.py"
echo "   sudo supervisorctl restart celery_worker"
echo ""
