#!/usr/bin/env python3
"""
Simular flujo completo para capturar el token de autenticación
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
print("CAPTURA DE TOKEN: Simulando flujo completo de usuario")
print("="*100)

def capture_token_from_user_flow():
    """
    Simula el flujo de usuario para capturar el token
    """

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Habilitar captura de logs de red
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options
    )

    try:
        print("\n1. NAVEGANDO A PÁGINA DE PRODUCTO")
        print("-"*100)

        # Usar el mismo flujo que tienen en el código existente
        product_url = "https://www.digimobil.es/combina-telefonia-internet?movil=1498"
        driver.get(product_url)

        print(f"   ✓ URL cargada: {driver.current_url}")
        time.sleep(2)

        print("\n2. HACIENDO CLIC EN 'LO QUIERO'")
        print("-"*100)

        try:
            link = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'config_loquiero'))
            )
            driver.execute_script("arguments[0].click();", link)
            print("   ✓ Clic realizado")

            # Esperar redirección
            WebDriverWait(driver, 10).until(
                lambda d: 'tienda.digimobil.es' in d.current_url
            )

            print(f"   ✓ Redirigido a: {driver.current_url}")
            time.sleep(2)

        except Exception as e:
            print(f"   ⚠️ Error en el clic: {e}")
            print(f"   Continuando de todas formas...")

        print("\n3. BUSCANDO CAMPO DE TELÉFONO")
        print("-"*100)

        try:
            phone_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'phoneNumber-0'))
            )

            print("   ✓ Campo de teléfono encontrado")

            # ANTES de ingresar el número, limpiar logs
            driver.get_log('performance')

            print("\n4. INGRESANDO NÚMERO DE TELÉFONO DE PRUEBA")
            print("-"*100)

            test_phone = "612345678"
            phone_input.clear()
            phone_input.send_keys(test_phone)

            print(f"   ✓ Número ingresado: {test_phone}")

            # Esperar a que se procese
            time.sleep(5)

            print("\n5. CAPTURANDO PETICIONES A LA API")
            print("-"*100)

            # Obtener logs DESPUÉS de ingresar el número
            logs = driver.get_log('performance')
            print(f"   Logs capturados: {len(logs)}")

            api_calls = []
            token_found = None

            for log_entry in logs:
                try:
                    message = json.loads(log_entry['message'])
                    method = message.get('message', {}).get('method', '')

                    if method == 'Network.responseReceived':
                        params = message['message']['params']
                        response = params.get('response', {})
                        url = response.get('url', '')

                        # Buscar peticiones a store-backend
                        if 'store-backend.digimobil.es' in url:
                            api_calls.append({
                                'url': url,
                                'status': response.get('status', 0),
                                'method': response.get('method', ''),
                                'headers': response.get('headers', {}),
                                'requestId': params.get('requestId')
                            })

                            print(f"\n   🎯 API Call detectado:")
                            print(f"      URL: {url}")
                            print(f"      Status: {response.get('status', 0)}")

                    # También buscar peticiones REQUEST (antes de la respuesta)
                    if method == 'Network.requestWillBeSent':
                        params = message['message']['params']
                        request = params.get('request', {})
                        url = request.get('url', '')

                        if 'store-backend.digimobil.es' in url:
                            headers = request.get('headers', {})

                            print(f"\n   📤 Request Headers para: {url}")

                            # Buscar token en headers de la petición
                            for header_name, header_value in headers.items():
                                print(f"      {header_name}: {str(header_value)[:100]}")

                                if header_name.lower() in ['authorization', 'x-auth-token', 'auth-token']:
                                    if 'Bearer' in header_value:
                                        token_found = header_value.replace('Bearer ', '').strip()
                                        print(f"\n   ✅✅✅ TOKEN ENCONTRADO EN HEADER {header_name}:")
                                        print(f"      {token_found[:200]}...")
                                    elif header_value.startswith('eyJ'):
                                        token_found = header_value
                                        print(f"\n   ✅✅✅ TOKEN ENCONTRADO EN HEADER {header_name}:")
                                        print(f"      {token_found[:200]}...")

                except Exception as e:
                    continue

            if token_found:
                return token_found

            # Si no encontramos el token en headers, buscar en response bodies
            print(f"\n   Total de peticiones a API: {len(api_calls)}")

            if api_calls:
                print("\n6. ANALIZANDO RESPONSE BODIES")
                print("-"*100)

                for call in api_calls:
                    try:
                        print(f"\n   Obteniendo body de: {call['url']}")

                        response_body = driver.execute_cdp_cmd(
                            'Network.getResponseBody',
                            {'requestId': call['requestId']}
                        )

                        body = response_body.get('body', '')

                        if body:
                            print(f"   ✓ Body: {body[:300]}")

                            try:
                                data = json.loads(body)

                                # Buscar token en la respuesta
                                if 'token' in data:
                                    token_found = data['token']
                                    print(f"\n   ✅✅✅ TOKEN EN RESPUESTA:")
                                    print(f"      {token_found[:200]}...")
                                    return token_found

                            except:
                                if body.startswith('eyJ'):
                                    print(f"\n   ✅✅✅ TOKEN (texto):")
                                    print(f"      {body[:200]}...")
                                    return body

                    except Exception as e:
                        print(f"   ⚠️ No se pudo obtener body: {e}")

            # Último intento: buscar en cookies después de la interacción
            print("\n7. VERIFICANDO COOKIES DESPUÉS DE LA INTERACCIÓN")
            print("-"*100)

            cookies = driver.get_cookies()
            for cookie in cookies:
                print(f"   🍪 {cookie['name']}: {str(cookie['value'])[:80]}")

                if cookie['value'].startswith('eyJ'):
                    print(f"\n   ✅✅✅ TOKEN EN COOKIE:")
                    print(f"      {cookie['value'][:200]}...")
                    return cookie['value']

            # Último último intento: buscar en localStorage/sessionStorage
            print("\n8. VERIFICANDO STORAGE DESPUÉS DE LA INTERACCIÓN")
            print("-"*100)

            storage_script = """
            var tokens = [];

            // localStorage
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                var value = localStorage.getItem(key);
                if (typeof value === 'string' && value.startsWith('eyJ')) {
                    tokens.push({source: 'localStorage', key: key, value: value});
                }
            }

            // sessionStorage
            for (var i = 0; i < sessionStorage.length; i++) {
                var key = sessionStorage.key(i);
                var value = sessionStorage.getItem(key);
                if (typeof value === 'string' && value.startsWith('eyJ')) {
                    tokens.push({source: 'sessionStorage', key: key, value: value});
                }
            }

            return tokens;
            """

            tokens = driver.execute_script(storage_script)

            if tokens:
                for t in tokens:
                    print(f"\n   ✅✅✅ TOKEN EN {t['source']}['{t['key']}']:")
                    print(f"      {t['value'][:200]}...")
                    return t['value']

        except Exception as e:
            print(f"\n   ⚠️ Error en la interacción: {e}")
            import traceback
            traceback.print_exc()

        return None

    except Exception as e:
        print(f"\n❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver.quit()
        print("\n   Navegador cerrado")

# Ejecutar
if __name__ == "__main__":
    token = capture_token_from_user_flow()

    print("\n" + "="*100)
    print("RESULTADO")
    print("="*100)

    if token:
        print(f"\n✅ TOKEN CAPTURADO:")
        print(f"{token}\n")

        # Intentar decodificar
        try:
            import jwt
            decoded = jwt.decode(token, options={"verify_signature": False})
            print("Contenido decodificado:")
            print(json.dumps(decoded, indent=2))

            # Verificar si está expirado
            import time
            if 'exp' in decoded:
                exp_time = decoded['exp']
                current_time = int(time.time())
                if current_time < exp_time:
                    minutes_left = (exp_time - current_time) / 60
                    print(f"\n✅ Token válido por {minutes_left:.1f} minutos más")
                else:
                    print(f"\n⚠️ Token EXPIRADO")

        except Exception as e:
            print(f"No se pudo decodificar: {e}")

        print(f"\n📝 SIGUIENTE PASO:")
        print(f"   Implementar esta lógica en browser.py para obtener tokens frescos")

    else:
        print(f"\n❌ NO SE PUDO CAPTURAR EL TOKEN")
        print(f"\n🤔 Posibles razones:")
        print(f"   1. La API ya no usa tokens JWT visibles")
        print(f"   2. El token se genera server-side y no se expone")
        print(f"   3. Necesitamos un enfoque diferente")

    print("\n" + "="*100)
