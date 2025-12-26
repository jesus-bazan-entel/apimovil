#!/usr/bin/env python3
"""
Script para monitorear consultas a la API de DigiMobil
Uso: python monitor_api.py [numero_telefono]
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.models import Movil, Consecutive
from django.utils import timezone
from datetime import timedelta

def monitor_phone(phone_number=None):
    """Monitorear procesamiento de un número específico"""
    
    if phone_number:
        print(f"\n{'='*100}")
        print(f"HISTORIAL DE CONSULTAS PARA: {phone_number}")
        print(f"{'='*100}\n")
        
        results = Movil.objects.filter(number=phone_number).order_by('-fecha_hora')
        
        if results.exists():
            for r in results:
                print(f"📅 Fecha:    {r.fecha_hora}")
                print(f"📱 Número:   {r.number}")
                print(f"📡 Operador: {r.operator}")
                print(f"🌐 IP:       {r.ip}")
                print(f"📄 Archivo:  {r.file}")
                print(f"👤 Usuario:  {r.user.username}")
                print(f"{'-'*100}\n")
        else:
            print(f"❌ No se encontraron registros para el número {phone_number}\n")
    
    else:
        print(f"\n{'='*100}")
        print(f"ÚLTIMOS 20 NÚMEROS PROCESADOS")
        print(f"{'='*100}\n")
        
        recent = Movil.objects.all().order_by('-fecha_hora')[:20]
        
        if recent.exists():
            for r in recent:
                status_ip = "✅" if r.ip not in ['Pending', 'Error'] else "⚠️"
                print(f"{status_ip} {r.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} | "
                      f"{r.number:12} | {r.operator:40} | {r.ip:15} | {r.file}")
        else:
            print("❌ No hay números procesados en la base de datos\n")

def monitor_processes():
    """Monitorear procesos activos"""
    print(f"\n{'='*100}")
    print(f"PROCESOS EN EJECUCIÓN")
    print(f"{'='*100}\n")
    
    processes = Consecutive.objects.all().order_by('-created')[:10]
    
    for p in processes:
        status_emoji = "🟢" if p.active else ("🔵" if p.finish else "🟡")
        status_text = "ACTIVO" if p.active else ("FINALIZADO" if p.finish else "PAUSADO")
        progress_pct = (p.progres / p.total * 100) if p.total > 0 else 0
        
        print(f"{status_emoji} {status_text:12} | {p.file:40}")
        print(f"   Progreso: {p.progres:5}/{p.total:5} ({progress_pct:5.1f}%)")
        print(f"   Usuario:  {p.user.username}")
        print(f"   Creado:   {p.created}")
        print(f"{'-'*100}\n")

def show_stats():
    """Mostrar estadísticas generales"""
    print(f"\n{'='*100}")
    print(f"ESTADÍSTICAS GENERALES")
    print(f"{'='*100}\n")
    
    total_numbers = Movil.objects.count()
    total_processes = Consecutive.objects.count()
    active_processes = Consecutive.objects.filter(active=True).count()
    
    # Últimas 24 horas
    yesterday = timezone.now() - timedelta(days=1)
    last_24h = Movil.objects.filter(fecha_hora__gte=yesterday).count()
    
    # Operadores más frecuentes
    from django.db.models import Count
    top_operators = Movil.objects.values('operator').annotate(
        count=Count('operator')
    ).order_by('-count')[:5]
    
    print(f"📊 Total números procesados:     {total_numbers:,}")
    print(f"📊 Total procesos:               {total_processes:,}")
    print(f"🟢 Procesos activos:             {active_processes}")
    print(f"⏰ Procesados últimas 24h:       {last_24h:,}")
    
    print(f"\n{'='*100}")
    print(f"TOP 5 OPERADORES")
    print(f"{'='*100}\n")
    
    for op in top_operators:
        print(f"  {op['count']:8,} - {op['operator']}")
    
    print()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor API DigiMobil')
    parser.add_argument('--phone', '-p', help='Número de teléfono a buscar')
    parser.add_argument('--stats', '-s', action='store_true', help='Mostrar estadísticas')
    parser.add_argument('--processes', '-r', action='store_true', help='Mostrar procesos')
    
    args = parser.parse_args()
    
    if args.stats:
        show_stats()
    elif args.processes:
        monitor_processes()
    elif args.phone:
        monitor_phone(args.phone)
    else:
        # Mostrar todo por defecto
        monitor_processes()
        monitor_phone()
        show_stats()
