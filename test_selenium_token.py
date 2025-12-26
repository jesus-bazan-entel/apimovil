#!/usr/bin/env python3
"""
Prueba para interceptar el token de DigiMobil usando Selenium
"""
import sys
import os
import django

# Configurar Django
sys.path.insert(0, '/opt/apimovil')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apimovil.settings')
django.setup()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

print("="*100)
print("PRUEBA: Interceptar token de DigiMobil con Selenium")
print("="*100)

def get_digimobil_token_with_selenium():
    """
    Intenta obtener el token de autenticación de DigiMobil usando Selenium
    """

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Habilitar capacidades de rendimiento para capturar peticiones de red
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options
    )

    try:
        print("\n1. CARGANDO PÁGINA DE DIGIMOBIL")
        print("-"*100)

        # Cargar la página principal de la tienda
        driver.get("https://tienda.digimobil.es/")

        print(f"   ✓ Página cargada: {driver.title}")
        print(f"   ✓ URL actual: {driver.current_url}")

        # Esperar a que la página cargue completamente
        time.sleep(3)

        print("\n2. BUSCANDO TOKEN EN LOCALSTORAGE")
        print("-"*100)

        # Intentar obtener token de localStorage
        try:
            local_storage = driver.execute_script("return window.localStorage;")
            print(f"   localStorage keys: {list(local_storage.keys())}")

            for key in local_storage.keys():
                if isinstance(key, str):  # Solo procesar keys string
                    value = local_storage[key]
                    if isinstance(value, str) and len(value) > 50:  # Probablemente un token
                        print(f"   🔑 {key}: {value[:100]}...")

                        # Intentar decodificar si es JWT
                        if value.startswith('eyJ'):
                            print(f"      ✓ Parece un JWT token")
                            return value
        except Exception as e:
            print(f"   ⚠️ Error accediendo localStorage: {e}")

        print("\n3. BUSCANDO TOKEN EN SESSIONSTORAGE")
        print("-"*100)

        try:
            session_storage = driver.execute_script("return window.sessionStorage;")
            print(f"   sessionStorage keys: {list(session_storage.keys())}")

            for key in session_storage.keys():
                if isinstance(key, str):  # Solo procesar keys string
                    value = session_storage[key]
                    if isinstance(value, str) and len(value) > 50:
                        print(f"   🔑 {key}: {value[:100]}...")

                        if value.startswith('eyJ'):
                            print(f"      ✓ Parece un JWT token")
                            return value
        except Exception as e:
            print(f"   ⚠️ Error accediendo sessionStorage: {e}")

        print("\n4. BUSCANDO TOKEN EN COOKIES")
        print("-"*100)

        cookies = driver.get_cookies()
        print(f"   Cookies encontradas: {len(cookies)}")

        for cookie in cookies:
            print(f"   🍪 {cookie['name']}: {cookie['value'][:50] if len(cookie['value']) > 50 else cookie['value']}")

            if cookie['value'].startswith('eyJ'):
                print(f"      ✓ Parece un JWT token")
                return cookie['value']

        print("\n5. INTERCEPTANDO PETICIONES DE RED (Performance Logs)")
        print("-"*100)

        try:
            logs = driver.get_log('performance')
            print(f"   Logs de performance capturados: {len(logs)}")

            tokens_found = []

            for log in logs:
                try:
                    message = json.loads(log['message'])
                    method = message.get('message', {}).get('method', '')

                    # Buscar respuestas de red
                    if method == 'Network.responseReceived':
                        params = message['message']['params']
                        response_url = params.get('response', {}).get('url', '')

                        # Si es una petición a la API de DigiMobil
                        if 'store-backend.digimobil.es' in response_url and '/login' in response_url:
                            print(f"   🎯 Petición de login detectada: {response_url}")

                            # Intentar obtener el cuerpo de la respuesta
                            request_id = params['requestId']
                            try:
                                response_body = driver.execute_cdp_cmd(
                                    'Network.getResponseBody',
                                    {'requestId': request_id}
                                )

                                body = response_body.get('body', '')
                                print(f"      Response body: {body[:200]}")

                                # Parsear y buscar token
                                if body:
                                    data = json.loads(body)
                                    if 'token' in data:
                                        token = data['token']
                                        print(f"      ✓✓✓ TOKEN ENCONTRADO: {token[:100]}...")
                                        return token

                                    # A veces el token viene directamente
                                    if isinstance(data, str) and data.startswith('eyJ'):
                                        print(f"      ✓✓✓ TOKEN ENCONTRADO: {data[:100]}...")
                                        return data
                            except Exception as e:
                                print(f"      ⚠️ No se pudo obtener response body: {e}")

                except Exception as e:
                    continue

        except Exception as e:
            print(f"   ⚠️ Error obteniendo logs de performance: {e}")

        print("\n6. INTENTANDO NAVEGAR A SECCIÓN QUE REQUIERA AUTH")
        print("-"*100)

        # Navegar a la página de portabilidad que podría forzar la autenticación
        driver.get("https://tienda.digimobil.es/portabilidad")
        time.sleep(3)

        print(f"   ✓ Navegado a: {driver.current_url}")

        # Repetir búsqueda de token
        local_storage = driver.execute_script("return window.localStorage;")
        for key in local_storage.keys():
            if isinstance(key, str):
                value = local_storage[key]
                if isinstance(value, str) and value and value.startswith('eyJ'):
                    print(f"   ✓✓✓ TOKEN ENCONTRADO en localStorage['{key}']: {value[:100]}...")
                    return value

        print("\n   ❌ No se pudo encontrar el token")
        return None

    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver.quit()
        print("\n   Navegador cerrado")

# Ejecutar prueba
if __name__ == "__main__":
    token = get_digimobil_token_with_selenium()

    print("\n" + "="*100)
    print("RESULTADO")
    print("="*100)

    if token:
        print(f"\n✅ Token obtenido exitosamente:")
        print(f"   {token}")

        # Intentar decodificar el token
        try:
            import jwt
            decoded = jwt.decode(token, options={"verify_signature": False})
            print(f"\n   Contenido del token:")
            print(f"   {json.dumps(decoded, indent=4)}")
        except Exception as e:
            print(f"\n   No se pudo decodificar como JWT: {e}")
    else:
        print("\n❌ No se pudo obtener el token")
        print("\n💡 SIGUIENTE PASO:")
        print("   Necesitamos analizar el código JavaScript de la web")
        print("   para entender cómo genera/almacena el token")

    print("\n" + "="*100)
