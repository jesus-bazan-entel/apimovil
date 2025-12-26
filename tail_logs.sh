#!/bin/bash
# Script para monitorear logs en tiempo real con filtros útiles

echo "=========================================="
echo "MONITOR DE LOGS EN TIEMPO REAL"
echo "=========================================="
echo ""
echo "Mostrando logs de procesamiento de números..."
echo "Presiona Ctrl+C para salir"
echo ""

tail -f /opt/apimovil/logger.log | grep --line-buffered -E 'Phone:|Operator:|S.A.M. worker|Error|Exception' | while read line; do
    if [[ $line == *"Phone:"* ]]; then
        echo -e "\033[0;32m$line\033[0m"  # Verde para números procesados
    elif [[ $line == *"Error"* ]] || [[ $line == *"Exception"* ]]; then
        echo -e "\033[0;31m$line\033[0m"  # Rojo para errores
    else
        echo "$line"
    fi
done
