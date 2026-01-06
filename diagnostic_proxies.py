"""
Script de diagnóstico de proxies para apimovil
Prueba cada proxy y detecta exactamente dónde falla
"""

import sys
import os
import django

# Setup Django
sys.path.append('/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from app.browser import DigiPhone
from app.models import Proxy
from django.contrib.auth.models import User
import time
from datetime import datetime
import json

# Número de prueba
TEST_PHONE = "622450594"

def test_proxy_full_flow(proxy_obj, username_line, index):
    """
    Prueba completa de un proxy individual
    Retorna dict con resultados detallados
    """
    proxy_id = f"{proxy_obj.ip}:{proxy_obj.port_min}:{username_line.strip()}"
    
    result = {
        "proxy_id": proxy_id,
        "user": proxy_obj.user.username,
        "index": index,
        "step_1_ip_check": {"success": False, "error": None, "response": None},
        "step_2_cookies": {"success": False, "error": None, "response": None},
        "step_3_phone_query": {"success": False, "error": None, "response": None},
        "overall_success": False,
        "total_time": 0
    }
    
    start_time = time.time()
    
    try:
        # Crear sesión manualizada para este proxy
        import requests
        session = requests.Session()
        session.proxies = {
            "http": f"socks5h://{username_line.strip()}:{proxy_obj.password}@{proxy_obj.ip}:{proxy_obj.port_min}",
            "https": f"socks5h://{username_line.strip()}:{proxy_obj.password}@{proxy_obj.ip}:{proxy_obj.port_min}"
        }
        
        # PASO 1: Verificar IP del proxy
        print(f"\n{'='*80}")
        print(f"[{index}] Testing: {proxy_id}")
        print(f"    Usuario Django: {proxy_obj.user.username}")
        print(f"{'='*80}")
        print(f"  [1/3] Verificando IP del proxy...")
        
        try:
            ip_response = session.get('https://api.ipify.org?format=json', timeout=20)
            if ip_response.status_code == 200:
                ip_data = ip_response.json()
                result["step_1_ip_check"]["success"] = True
                result["step_1_ip_check"]["response"] = ip_data
                print(f"        ✓ IP detectada: {ip_data.get('ip', 'N/A')}")
            else:
                result["step_1_ip_check"]["error"] = f"Status {ip_response.status_code}"
                print(f"        ✗ Error status: {ip_response.status_code}")
                return result
        except Exception as e:
            result["step_1_ip_check"]["error"] = str(e)
            print(f"        ✗ Error: {type(e).__name__}: {str(e)[:100]}")
            return result
        
        # PASO 2: Obtener cookies de DIGI
        print(f"  [2/3] Obteniendo cookies de DIGI...")
        
        try:
            # Paso 2.1: Página principal
            main_url = "https://www.digimobil.es/"
            headers_get = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            print(f"        → GET {main_url}")
            response_main = session.get(main_url, headers=headers_get, timeout=60)
            print(f"        → Status: {response_main.status_code}")
            
            if response_main.status_code != 200:
                result["step_2_cookies"]["error"] = f"Main page status {response_main.status_code}"
                print(f"        ✗ Página principal falló: {response_main.status_code}")
                print(f"        Response: {response_main.text[:200]}")
                return result
            
            # Paso 2.2: Login para obtener store_access_token
            login_url = "https://store-backend.digimobil.es/v2/login/online"
            headers_post = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "content-type": "application/json",
                "origin": "https://www.digimobil.es",
                "referer": "https://www.digimobil.es/",
            }
            
            print(f"        → POST {login_url}")
            response_login = session.post(login_url, headers=headers_post, timeout=60)
            print(f"        → Status: {response_login.status_code}")
            
            if 'store_access_token' in session.cookies:
                result["step_2_cookies"]["success"] = True
                result["step_2_cookies"]["response"] = {
                    "status": response_login.status_code,
                    "cookie_obtained": True,
                    "cookie_preview": session.cookies.get('store_access_token')[:50] + "..."
                }
                print(f"        ✓ Cookie obtenida: {session.cookies.get('store_access_token')[:50]}...")
            else:
                result["step_2_cookies"]["error"] = "store_access_token not in cookies"
                result["step_2_cookies"]["response"] = {
                    "status": response_login.status_code,
                    "cookies": list(session.cookies.keys()),
                    "response_preview": response_login.text[:500]
                }
                print(f"        ✗ Cookie NO obtenida")
                print(f"        Cookies disponibles: {list(session.cookies.keys())}")
                print(f"        Response: {response_login.text[:300]}")
                return result
                
        except Exception as e:
            result["step_2_cookies"]["error"] = str(e)
            print(f"        ✗ Error: {type(e).__name__}: {str(e)[:100]}")
            return result
        
        # PASO 3: Consultar número de prueba
        print(f"  [3/3] Consultando número {TEST_PHONE}...")
        
        try:
            phone_url = f"https://store-backend.digimobil.es/v2/operators/by-line-code/{TEST_PHONE}"
            headers_phone = {
                "accept": "*/*",
                "origin": "https://www.digimobil.es",
                "referer": "https://www.digimobil.es/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            print(f"        → GET {phone_url}")
            response_phone = session.get(phone_url, headers=headers_phone, timeout=60)
            print(f"        → Status: {response_phone.status_code}")
            
            if response_phone.status_code == 200:
                phone_data = response_phone.json()
                result["step_3_phone_query"]["success"] = True
                result["step_3_phone_query"]["response"] = {
                    "status": 200,
                    "operator": phone_data.get('name', 'Unknown'),
                    "full_response": phone_data
                }
                print(f"        ✓ Operador: {phone_data.get('name', 'Unknown')}")
                result["overall_success"] = True
                
            elif response_phone.status_code == 404:
                # 404 puede significar que es DIGI (válido)
                result["step_3_phone_query"]["success"] = True
                result["step_3_phone_query"]["response"] = {
                    "status": 404,
                    "operator": "DIGI SPAIN TELECOM, S.L.",
                    "note": "404 = número de DIGI"
                }
                print(f"        ✓ Número de DIGI (404)")
                result["overall_success"] = True
                
            else:
                result["step_3_phone_query"]["error"] = f"Status {response_phone.status_code}"
                result["step_3_phone_query"]["response"] = {
                    "status": response_phone.status_code,
                    "response_preview": response_phone.text[:500]
                }
                print(f"        ✗ Status inesperado: {response_phone.status_code}")
                print(f"        Response: {response_phone.text[:300]}")
                
        except Exception as e:
            result["step_3_phone_query"]["error"] = str(e)
            print(f"        ✗ Error: {type(e).__name__}: {str(e)[:100]}")
            
    except Exception as e:
        result["step_2_cookies"]["error"] = f"General error: {str(e)}"
        print(f"  ✗ Error general: {type(e).__name__}: {str(e)[:100]}")
    
    finally:
        result["total_time"] = round(time.time() - start_time, 2)
        print(f"\n  ⏱ Tiempo total: {result['total_time']}s")
        
        if result["overall_success"]:
            print(f"  ✅ PROXY FUNCIONAL")
        else:
            print(f"  ❌ PROXY FALLIDO")
    
    return result


def main():
    """
    Script principal de diagnóstico
    """
    print("\n" + "="*80)
    print("  DIAGNÓSTICO DE PROXIES - APIMOVIL")
    print("="*80)
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Número de prueba: {TEST_PHONE}")
    print("="*80 + "\n")
    
    # Obtener todos los proxies
    #all_proxies = Proxy.objects.all()
    #print(f"📊 Total de registros de proxy en BD: {all_proxies.count()}\n")
    target_username = "GCCDianaramirez"  # ← CAMBIAR AQUÍ
    
    try:
        target_user = User.objects.get(username=target_username)
        all_proxies = Proxy.objects.filter(user=target_user)
        print(f"👤 Usuario seleccionado: {target_username}")
    except User.DoesNotExist:
        print(f"❌ ERROR: Usuario '{target_username}' no existe")
        print(f"\n📋 Usuarios con proxies disponibles:")
        users_with_proxies = Proxy.objects.values_list('user__username', flat=True).distinct()
        for username in users_with_proxies:
            print(f"  - {username}")
        return None, None
    
    # ========================================
    
    print(f"📊 Total de registros de proxy para este usuario:  {all_proxies.count()}\n")
    
    # Contador global
    total_proxies_tested = 0
    results = []
    
    # Estadísticas
    stats = {
        "total_proxies": 0,
        "step_1_success": 0,
        "step_2_success": 0,
        "step_3_success": 0,
        "overall_success": 0,
        "failed_at_ip": 0,
        "failed_at_cookies": 0,
        "failed_at_query": 0
    }
    
    # Probar cada proxy
    for proxy_obj in all_proxies:
        # Cada registro puede tener múltiples usernames (líneas)
        usernames = [u.strip() for u in proxy_obj.username.strip().splitlines() if u.strip()]
        
        for idx, username_line in enumerate(usernames, 1):
            total_proxies_tested += 1
            stats["total_proxies"] += 1
            
            # Probar este proxy
            result = test_proxy_full_flow(proxy_obj, username_line, total_proxies_tested)
            results.append(result)
            
            # Actualizar estadísticas
            if result["step_1_ip_check"]["success"]:
                stats["step_1_success"] += 1
            else:
                stats["failed_at_ip"] += 1
                
            if result["step_2_cookies"]["success"]:
                stats["step_2_success"] += 1
            elif result["step_1_ip_check"]["success"]:
                stats["failed_at_cookies"] += 1
                
            if result["step_3_phone_query"]["success"]:
                stats["step_3_success"] += 1
            elif result["step_2_cookies"]["success"]:
                stats["failed_at_query"] += 1
                
            if result["overall_success"]:
                stats["overall_success"] += 1
            
            # Pausa entre proxies para no saturar
            time.sleep(2)
    
    # REPORTE FINAL
    print("\n\n" + "="*80)
    print("  📊 REPORTE FINAL DE DIAGNÓSTICO")
    print("="*80)
    print(f"\nTotal de proxies probados: {stats['total_proxies']}")
    print(f"\n✅ PROXIES FUNCIONALES: {stats['overall_success']} ({stats['overall_success']/stats['total_proxies']*100:.1f}%)")
    print(f"❌ PROXIES FALLIDOS: {stats['total_proxies'] - stats['overall_success']} ({(stats['total_proxies'] - stats['overall_success'])/stats['total_proxies']*100:.1f}%)")
    
    print(f"\n📈 DESGLOSE POR ETAPA:")
    print(f"  Paso 1 (IP Check):     {stats['step_1_success']}/{stats['total_proxies']} exitosos ({stats['step_1_success']/stats['total_proxies']*100:.1f}%)")
    print(f"  Paso 2 (Cookies):      {stats['step_2_success']}/{stats['total_proxies']} exitosos ({stats['step_2_success']/stats['total_proxies']*100:.1f}%)")
    print(f"  Paso 3 (Query número): {stats['step_3_success']}/{stats['total_proxies']} exitosos ({stats['step_3_success']/stats['total_proxies']*100:.1f}%)")
    
    print(f"\n🔍 PUNTOS DE FALLA:")
    print(f"  Fallaron en IP Check:    {stats['failed_at_ip']} ({stats['failed_at_ip']/stats['total_proxies']*100:.1f}%)")
    print(f"  Fallaron en Cookies:     {stats['failed_at_cookies']} ({stats['failed_at_cookies']/stats['total_proxies']*100:.1f}%)")
    print(f"  Fallaron en Query:       {stats['failed_at_query']} ({stats['failed_at_query']/stats['total_proxies']*100:.1f}%)")
    
    # Lista de proxies funcionales
    working_proxies = [r for r in results if r["overall_success"]]
    if working_proxies:
        print(f"\n✅ PROXIES FUNCIONALES ({len(working_proxies)}):")
        for r in working_proxies[:10]:  # Mostrar solo los primeros 10
            print(f"  - {r['proxy_id'][:80]}... (Usuario: {r['user']})")
        if len(working_proxies) > 10:
            print(f"  ... y {len(working_proxies) - 10} más")
    
    # Lista de proxies fallidos con detalles
    failed_proxies = [r for r in results if not r["overall_success"]]
    if failed_proxies:
        print(f"\n❌ PROXIES FALLIDOS ({len(failed_proxies)}) - Primeros 5 con detalles:")
        for r in failed_proxies[:5]:
            print(f"\n  Proxy: {r['proxy_id'][:60]}...")
            print(f"  Usuario: {r['user']}")
            if not r["step_1_ip_check"]["success"]:
                print(f"    ✗ Falló en IP Check: {r['step_1_ip_check']['error'][:100]}")
            elif not r["step_2_cookies"]["success"]:
                print(f"    ✗ Falló en Cookies: {r['step_2_cookies']['error'][:100]}")
                if r["step_2_cookies"]["response"]:
                    print(f"      Response: {str(r['step_2_cookies']['response'])[:150]}")
            elif not r["step_3_phone_query"]["success"]:
                print(f"    ✗ Falló en Query: {r['step_3_phone_query']['error'][:100]}")
    
    # Guardar reporte JSON
    report_file = f"/tmp/proxy_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "test_phone": TEST_PHONE,
            "statistics": stats,
            "results": results
        }, f, indent=2)
    
    print(f"\n📄 Reporte completo guardado en: {report_file}")
    print("="*80 + "\n")
    
    return stats, results


if __name__ == "__main__":
    try:
        stats, results = main()
    except KeyboardInterrupt:
        print("\n\n⚠ Diagnóstico interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error crítico: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
