#!/usr/bin/env python
"""
Script para migrar datos de SQLite a PostgreSQL
Este script exporta los datos de SQLite y los prepara para importación en PostgreSQL
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from django.core.management import call_command
from django.conf import settings

def export_data_from_sqlite():
    """Exporta los datos de la base de datos SQLite actual"""
    print("=" * 60)
    print("EXPORTANDO DATOS DESDE SQLITE")
    print("=" * 60)

    # Verificar que estamos usando SQLite
    current_engine = settings.DATABASES['default']['ENGINE']
    if 'sqlite' not in current_engine:
        print("ERROR: Este script debe ejecutarse con SQLite configurado")
        print(f"Motor actual: {current_engine}")
        return False

    # Exportar datos a un archivo JSON
    output_file = 'sqlite_data_backup.json'
    print(f"\nExportando datos a {output_file}...")

    try:
        with open(output_file, 'w') as f:
            # Exportar todos los modelos excepto contenttypes y auth.permission
            # que se recrearán automáticamente
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--natural-primary',
                '--exclude=contenttypes',
                '--exclude=auth.permission',
                '--indent=2',
                stdout=f
            )
        print(f"✓ Datos exportados exitosamente a {output_file}")
        print(f"  Tamaño del archivo: {os.path.getsize(output_file)} bytes")
        return True
    except Exception as e:
        print(f"✗ Error al exportar datos: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("MIGRACIÓN DE SQLITE A POSTGRESQL")
    print("=" * 60)
    print("\nEste script exportará los datos de SQLite.")
    print("Asegúrate de que:")
    print("  1. La configuración actual apunta a SQLite")
    print("  2. La base de datos SQLite existe y tiene datos")
    print("\n" + "=" * 60 + "\n")

    response = input("¿Continuar con la exportación? (s/n): ")
    if response.lower() != 's':
        print("Operación cancelada.")
        return

    success = export_data_from_sqlite()

    if success:
        print("\n" + "=" * 60)
        print("EXPORTACIÓN COMPLETADA")
        print("=" * 60)
        print("\nPasos siguientes:")
        print("  1. Configurar PostgreSQL (crear base de datos y usuario)")
        print("  2. Actualizar settings.py o crear archivo .env")
        print("  3. Ejecutar: python manage.py migrate")
        print("  4. Ejecutar: python manage.py loaddata sqlite_data_backup.json")
        print("  5. Verificar que los datos se migraron correctamente")
        print("\nConsulta MIGRATION_GUIDE.md para instrucciones detalladas")
        print("=" * 60 + "\n")
    else:
        print("\n✗ La exportación falló. Revisa los errores anteriores.\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
