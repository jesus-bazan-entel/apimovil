#!/usr/bin/env python3
"""
Interceptar peticiones de red de DigiMobil para capturar el token
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
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import json
import time

print("="*100)
print("PRUEBA: Interceptar peticiones de red para capturar token")
print("="*100)

def intercept_network_traffic():
    """
    Captura todas las peticiones de red y busca el token
    """

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Habilitar logging de performance
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    # Habilitar DevTools Protocol
    chrome_options.add_experimental_option('perfLoggingPrefs', {
        'enableNetwork': True,
        'enablePage': False,
    })

    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options
    )

    try:
        print("\n1. NAVEGANDO A LA TIENDA DE DIGIMOBIL")
        print("-"*100)

        # Ir directamente a la tienda
        driver.get("https://tienda.digimobil.es/")

        print(f"   ✓ URL cargada: {driver.current_url}")
        print(f"   ✓ Título: {driver.title}")

        # Esperar a que se cargue completamente
        time.sleep(5)

        print("\n2. ANALIZANDO PETICIONES DE RED")
        print("-"*100)

        logs = driver.get_log('performance')
        print(f"   Total de logs capturados: {len(logs)}")

        api_requests = []
        token_found = None

        for log_entry in logs:
            try:
                message = json.loads(log_entry['message'])
                method = message.get('message', {}).get('method', '')

                # Analizar respuestas HTTP
                if method == 'Network.responseReceived':
                    params = message['message']['params']
                    response = params.get('response', {})
                    url = response.get('url', '')
                    status = response.get('status', 0)

                    # Buscar peticiones a store-backend
                    if 'store-backend.digimobil.es' in url:
                        api_requests.append({
                            'url': url,
                            'status': status,
                            'method': response.get('method', ''),
                            'requestId': params.get('requestId')
                        })

                        print(f"\n   🎯 API Request detectada:")
                        print(f"      URL: {url}")
                        print(f"      Status: {status}")
                        print(f"      Method: {response.get('method', '')}")

                # Buscar datos de respuesta que contengan tokens
                if method == 'Network.dataReceived':
                    params = message['message']['params']
                    request_id = params.get('requestId')

            except Exception as e:
                continue

        print(f"\n   Total de peticiones a API: {len(api_requests)}")

        # Intentar obtener el cuerpo de las respuestas
        if api_requests:
            print("\n3. OBTENIENDO CUERPO DE LAS RESPUESTAS API")
            print("-"*100)

            for req in api_requests:
                try:
                    print(f"\n   Intentando obtener response body de: {req['url']}")

                    # Usar Chrome DevTools Protocol para obtener response body
                    response_body = driver.execute_cdp_cmd(
                        'Network.getResponseBody',
                        {'requestId': req['requestId']}
                    )

                    body = response_body.get('body', '')

                    if body:
                        print(f"   ✓ Body obtenido ({len(body)} chars)")
                        print(f"   Primeros 500 chars: {body[:500]}")

                        # Intentar parsear como JSON
                        try:
                            data = json.loads(body)

                            # Buscar campo 'token' o campos que contengan JWT
                            if 'token' in data:
                                token_found = data['token']
                                print(f"\n   ✅✅✅ TOKEN ENCONTRADO EN RESPUESTA:")
                                print(f"   {token_found[:200]}...")
                                return token_found

                            # Buscar recursivamente en el JSON
                            def find_jwt_in_dict(d, path=""):
                                if isinstance(d, dict):
                                    for k, v in d.items():
                                        if isinstance(v, str) and v.startswith('eyJ'):
                                            print(f"\n   ✅✅✅ JWT ENCONTRADO en {path}.{k}:")
                                            print(f"   {v[:200]}...")
                                            return v
                                        elif isinstance(v, (dict, list)):
                                            result = find_jwt_in_dict(v, f"{path}.{k}")
                                            if result:
                                                return result
                                elif isinstance(d, list):
                                    for i, item in enumerate(d):
                                        result = find_jwt_in_dict(item, f"{path}[{i}]")
                                        if result:
                                            return result
                                return None

                            jwt_token = find_jwt_in_dict(data)
                            if jwt_token:
                                return jwt_token

                        except json.JSONDecodeError:
                            # Podría ser texto plano con el token
                            if body.startswith('eyJ'):
                                print(f"\n   ✅✅✅ TOKEN (texto plano) ENCONTRADO:")
                                print(f"   {body[:200]}...")
                                return body

                except Exception as e:
                    print(f"   ⚠️ Error obteniendo body: {e}")

        # Si no encontramos en las peticiones, buscar en variables JavaScript
        print("\n4. BUSCANDO EN VARIABLES JAVASCRIPT GLOBALES")
        print("-"*100)

        try:
            # Buscar en window.store, window.app, window.auth, etc.
            script = """
            var result = {};

            // Buscar en window
            for (var key in window) {
                try {
                    var value = window[key];
                    if (typeof value === 'string' && value.startsWith('eyJ')) {
                        result[key] = value;
                    } else if (typeof value === 'object' && value !== null) {
                        // Buscar un nivel más profundo
                        for (var subkey in value) {
                            var subvalue = value[subkey];
                            if (typeof subvalue === 'string' && subvalue.startsWith('eyJ')) {
                                result[key + '.' + subkey] = subvalue;
                            }
                        }
                    }
                } catch(e) {}
            }

            return result;
            """

            js_tokens = driver.execute_script(script)

            if js_tokens:
                print(f"   ✓ Tokens encontrados en JavaScript: {len(js_tokens)}")
                for key, value in js_tokens.items():
                    print(f"\n   🔑 {key}:")
                    print(f"      {value[:200]}...")
                    return value
            else:
                print(f"   No se encontraron tokens en variables JavaScript")

        except Exception as e:
            print(f"   ⚠️ Error buscando en JavaScript: {e}")

        return None

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        driver.quit()

# Ejecutar
if __name__ == "__main__":
    token = intercept_network_traffic()

    print("\n" + "="*100)
    print("RESULTADO FINAL")
    print("="*100)

    if token:
        print(f"\n✅ TOKEN OBTENIDO:")
        print(f"   {token}")

        # Decodificar
        try:
            import jwt
            decoded = jwt.decode(token, options={"verify_signature": False})
            print(f"\n   Contenido decodificado:")
            print(json.dumps(decoded, indent=4))
        except Exception as e:
            print(f"   No se pudo decodificar: {e}")
    else:
        print(f"\n❌ No se pudo capturar el token")
        print(f"\n💡 Esto significa que:")
        print(f"   1. La web NO genera un token automáticamente al cargar")
        print(f"   2. El token solo se genera cuando el usuario interactúa")
        print(f"   3. Necesitamos simular la interacción del usuario")

    print("\n" + "="*100)
