#!/bin/bash
# Script para buscar el historial completo de un número

if [ -z "$1" ]; then
    echo "Uso: $0 <numero_telefono>"
    echo "Ejemplo: $0 612345678"
    exit 1
fi

PHONE=$1

echo "=========================================="
echo "BÚSQUEDA COMPLETA DEL NÚMERO: $PHONE"
echo "=========================================="
echo ""

echo "📁 Buscando en LOGS..."
echo "------------------------------------------"
grep "$PHONE" /opt/apimovil/logger.log | grep "Phone:" | while read line; do
    # Extraer fecha del log
    DATE=$(echo "$line" | grep -oP 'INFO:root:\[\+\] Phone:' | head -1)
    echo "  ✅ $line"
done

if [ $(grep -c "$PHONE" /opt/apimovil/logger.log) -eq 0 ]; then
    echo "  ❌ No se encontraron logs para este número"
fi

echo ""
echo "💾 Buscando en BASE DE DATOS..."
echo "------------------------------------------"

cd /opt/apimovil
/opt/apimovil/venv/bin/python << PYTHON_EOF
import django
import os
import sys

sys.path.insert(0, '/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Movil

results = Movil.objects.filter(number='$PHONE').order_by('-fecha_hora')

if results.exists():
    for r in results:
        print(f"  ✅ {r.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} | Operador: {r.operator:40} | IP: {r.ip:15} | File: {r.file}")
else:
    print("  ❌ No se encontraron registros en la base de datos")

PYTHON_EOF

echo ""
echo "=========================================="
