#!/usr/bin/env python
"""
Script para verificar la migración de SQLite a PostgreSQL
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from django.conf import settings
from django.db import connection
from app.models import Movil, Consecutive, Proxy, BlockIp
from django.contrib.auth.models import User

def verify_database_connection():
    """Verificar que la conexión a la base de datos funcione"""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE CONEXIÓN A BASE DE DATOS")
    print("=" * 60)

    db_engine = settings.DATABASES['default']['ENGINE']
    db_name = settings.DATABASES['default']['NAME']
    db_host = settings.DATABASES['default'].get('HOST', 'N/A')
    db_port = settings.DATABASES['default'].get('PORT', 'N/A')

    print(f"\nMotor de BD: {db_engine}")
    print(f"Nombre: {db_name}")
    print(f"Host: {db_host}")
    print(f"Puerto: {db_port}")

    if 'postgresql' not in db_engine:
        print("\n⚠ ADVERTENCIA: No estás usando PostgreSQL")
        print(f"  Motor actual: {db_engine}")
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            print(f"\n✓ Conexión exitosa a PostgreSQL")
            print(f"  Versión: {version}")
        return True
    except Exception as e:
        print(f"\n✗ Error de conexión: {e}")
        return False

def count_records():
    """Contar registros en todas las tablas principales"""
    print("\n" + "=" * 60)
    print("CONTEO DE REGISTROS")
    print("=" * 60)

    models = {
        'Usuarios': User,
        'Móviles': Movil,
        'Consecutivos': Consecutive,
        'Proxies': Proxy,
        'IPs Bloqueadas': BlockIp,
    }

    total_records = 0
    for name, model in models.items():
        try:
            count = model.objects.count()
            total_records += count
            print(f"{name:20} {count:>10} registros")
        except Exception as e:
            print(f"{name:20} ✗ Error: {e}")

    print("-" * 60)
    print(f"{'TOTAL':20} {total_records:>10} registros")

    return total_records

def check_indexes():
    """Verificar que los índices estén creados"""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE ÍNDICES")
    print("=" * 60)

    try:
        with connection.cursor() as cursor:
            # Verificar índices en la tabla app_movil
            cursor.execute("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'app_movil';
            """)
            indexes = cursor.fetchall()

            if indexes:
                print("\nÍndices en tabla 'app_movil':")
                for idx_name, idx_def in indexes:
                    print(f"  - {idx_name}")
                print(f"\n✓ Se encontraron {len(indexes)} índices")
            else:
                print("\n⚠ No se encontraron índices en app_movil")

    except Exception as e:
        print(f"\n⚠ No se pudo verificar índices (puede ser normal en SQLite): {e}")

def check_foreign_keys():
    """Verificar integridad de claves foráneas"""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE INTEGRIDAD")
    print("=" * 60)

    issues = []

    # Verificar Movil -> User
    try:
        moviles_sin_usuario = Movil.objects.filter(user__isnull=True).count()
        if moviles_sin_usuario > 0:
            issues.append(f"⚠ {moviles_sin_usuario} móviles sin usuario asignado")
        else:
            print("✓ Todos los móviles tienen usuario asignado")
    except Exception as e:
        issues.append(f"✗ Error verificando móviles: {e}")

    # Verificar Consecutive -> User
    try:
        consecutivos_sin_usuario = Consecutive.objects.filter(user__isnull=True).count()
        if consecutivos_sin_usuario > 0:
            issues.append(f"⚠ {consecutivos_sin_usuario} consecutivos sin usuario")
        else:
            print("✓ Todos los consecutivos tienen usuario asignado")
    except Exception as e:
        issues.append(f"✗ Error verificando consecutivos: {e}")

    # Verificar BlockIp -> Proxy y User
    try:
        blockips_sin_proxy = BlockIp.objects.filter(proxy_ip__isnull=True).count()
        blockips_sin_usuario = BlockIp.objects.filter(user__isnull=True).count()
        if blockips_sin_proxy > 0:
            issues.append(f"⚠ {blockips_sin_proxy} IPs bloqueadas sin proxy")
        if blockips_sin_usuario > 0:
            issues.append(f"⚠ {blockips_sin_usuario} IPs bloqueadas sin usuario")
        if blockips_sin_proxy == 0 and blockips_sin_usuario == 0:
            print("✓ Todas las IPs bloqueadas tienen relaciones válidas")
    except Exception as e:
        issues.append(f"✗ Error verificando IPs bloqueadas: {e}")

    if issues:
        print("\nProblemas encontrados:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✓ Integridad de datos verificada correctamente")
        return True

def sample_queries():
    """Ejecutar algunas consultas de muestra para verificar funcionalidad"""
    print("\n" + "=" * 60)
    print("PRUEBAS DE CONSULTAS")
    print("=" * 60)

    try:
        # Consulta 1: Últimos 5 móviles procesados
        print("\nÚltimos 5 móviles procesados:")
        for movil in Movil.objects.select_related('user').order_by('-fecha_hora')[:5]:
            print(f"  - {movil.number} | {movil.operator} | {movil.fecha_hora}")

        # Consulta 2: Usuarios con más móviles procesados
        print("\nTop 3 usuarios con más móviles procesados:")
        from django.db.models import Count
        top_users = User.objects.annotate(
            movil_count=Count('movil')
        ).order_by('-movil_count')[:3]

        for user in top_users:
            print(f"  - {user.username}: {user.movil_count} móviles")

        print("\n✓ Consultas ejecutadas correctamente")
        return True
    except Exception as e:
        print(f"\n✗ Error ejecutando consultas: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE MIGRACIÓN A POSTGRESQL")
    print("=" * 60)

    results = {
        'conexion': False,
        'registros': 0,
        'integridad': False,
        'consultas': False,
    }

    # 1. Verificar conexión
    results['conexion'] = verify_database_connection()
    if not results['conexion']:
        print("\n✗ No se pudo conectar a la base de datos")
        print("  Verifica tu configuración en settings.py o .env")
        sys.exit(1)

    # 2. Contar registros
    results['registros'] = count_records()

    # 3. Verificar índices (solo informativo)
    check_indexes()

    # 4. Verificar integridad
    results['integridad'] = check_foreign_keys()

    # 5. Ejecutar consultas de prueba
    results['consultas'] = sample_queries()

    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN DE VERIFICACIÓN")
    print("=" * 60)
    print(f"Conexión a PostgreSQL: {'✓' if results['conexion'] else '✗'}")
    print(f"Total de registros:    {results['registros']}")
    print(f"Integridad de datos:   {'✓' if results['integridad'] else '⚠'}")
    print(f"Consultas funcionales: {'✓' if results['consultas'] else '✗'}")

    if all([results['conexion'], results['integridad'], results['consultas']]):
        print("\n✓ ¡Migración verificada exitosamente!")
        print("  Tu aplicación está lista para usar PostgreSQL")
        print("=" * 60 + "\n")
        sys.exit(0)
    else:
        print("\n⚠ Se encontraron algunos problemas")
        print("  Revisa los mensajes anteriores para más detalles")
        print("=" * 60 + "\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
