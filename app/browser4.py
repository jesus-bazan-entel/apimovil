from bs4 import BeautifulSoup
import random
import threading
from time import sleep
import requests
import json
import logging
import os

# ============================================================================
# CONFIGURACIÓN DE PROXY - Cambia esta sección según necesites:
# ============================================================================
# Para usar DJANGO (con base de datos):
from .models import Proxy

# Para usar MOCK (local, sin Django) - comenta la línea de arriba y descomenta las siguientes:
# from mock_proxy import MockProxyManager
# class Proxy:
#     objects = MockProxyManager()
# ============================================================================

# Configuración de logging más detallada para depuración
_logging = logging.basicConfig(
    filename="logger.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class DigiPhone:
    def __init__(self, user=None, reprocess=False) -> None:
        #if reprocess:
        #self.proxys = Proxy.objects.filter(user=user, username='668f064999df71e1de9e__cr.es').first()
        self.proxys = Proxy.objects.filter(user=user)
        #else:
            #self.proxys = Proxy.objects.filter(user=user, username='84937b4537718abef992__cr.es').first()
        #    self.proxys = Proxy.objects.filter(user=user).first()
        logging.info(f"proxys: {str(self.proxys)}")
        self.proxies = []

        if self.proxys.count() == 1:
            p = self.proxys.first()
            usernames = [u.strip() for u in p.username.splitlines() if u.strip()]
            for uname in usernames:
                print(f"username: {uname} - password: {p.password} - ip: {p.ip} - port: {p.port_min}")
                # Crear sesión para mantener cookies
                session = requests.Session()
                session.proxies = {
                    "http": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}",
                    "https": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}"
                }
                self.proxies.append({
                    "proxy": {
                        "http": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}",
                        "https": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}"
                    },
                    "session": session,  # Sesión para mantener cookies
                    "token": None,  # Mantener por compatibilidad, pero ya no se usa
                    "preorder": None,
                    "product": None,
                    "item": p,
                    "cart": None
                })
        else:
            #if self.proxys:
            for p in self.proxys:#range(int(self.proxys.port_min), int(self.proxys.port_max), 1):
                # Crear sesión para mantener cookies
                session = requests.Session()
                session.proxies = {
                    "http": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}",
                    "https": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}"
                }
                self.proxies.append({
                    "proxy": {
                        "http": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}",
                        "https": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}"
                    },
                    "session": session,  # Sesión para mantener cookies
                    "token": None,  # Mantener por compatibilidad, pero ya no se usa
                    "preorder": None,
                    "product": None,
                    "item": p,
                    "cart": None
                })

        self.position = 0


    @property
    def _len_proxy(self):
        return len(self.proxies)

    @property
    def _token(self):
        return self.proxies[self.position]["token"]

    @property
    def _proxy(self):
        return self.proxies[self.position]["item"]

    def change_position(self):
        if self.position < len(self.proxies) - 1:
            self.position += 1
        else:
            self.position = 0

    def update_cart(self):
        """
        Actualiza el carrito usando cookies (store_access_token) en lugar de Bearer token.
        """
        url = f"https://store-backend.digimobil.es/v2/preorders/{self.proxies[self.position]['preorder']}/shopping-carts"

        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "content-type": "application/json",
            "origin": "https://www.digimobil.es",
            "referer": "https://www.digimobil.es/",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Microsoft Edge\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
        }

        data = {
            "products": [1488],
            "contractId": None,
            "removePackagesIds": [],
        }

        session = self.proxies[self.position]["session"]
        logging.info(f"[update_cart] URL: {url} | payload: {data}")
        logging.info(f"[update_cart] Cookies disponibles: {list(session.cookies.keys())}")
        
        try:
            response = session.put(url, headers=headers, json=data, timeout=20)
            logging.info(f"[update_cart] Status: {response.status_code} | Body: {response.text[:200]}...")
            if response.status_code == 200:
                return response.status_code, response.json()
            else:
                return response.status_code, response.text
        except Exception as e:
            logging.exception(f"[update_cart] Error: {e}")
            return 500, str(e)

    def validate_phone_number(self, phone):
        """
        Valida un número de teléfono usando cookies (store_access_token).
        """
        url = f"https://store-backend.digimobil.es/v2/preorders/{self.proxies[self.position]['preorder']}/shopping-cart-lines/{self.proxies[self.position]['cart']}/validate-phonenumber/{phone}"

        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "origin": "https://www.digimobil.es",
            "referer": "https://www.digimobil.es/",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Microsoft Edge\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
        }

        session = self.proxies[self.position]["session"]
        logging.info(f"[validate_phone_number] URL: {url}")
        logging.info(f"[validate_phone_number] Cookies disponibles: {list(session.cookies.keys())}")
        
        try:
            response = session.get(url, headers=headers, timeout=20)
            logging.info(f"[validate_phone_number] Status: {response.status_code} | Body: {response.text[:200]}...")
            if response.status_code == 200:
                return response.status_code, response.json()
            else:
                return response.status_code, response.text
        except Exception as e:
            logging.exception(f"[validate_phone_number] Error: {e}")
            return 500, str(e)

    def get_phone_number(self, phone):
        """
        Obtiene información del operador de un número usando cookies (store_access_token).
        """
        url = f"https://store-backend.digimobil.es/v2/operators/by-line-code/{phone}"

        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "origin": "https://www.digimobil.es",
            "referer": "https://www.digimobil.es/",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Microsoft Edge\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
        }

        session = self.proxies[self.position]["session"]
        logging.info(f"[get_phone_number] URL: {url}")
        logging.info(f"[get_phone_number] Cookies disponibles: {list(session.cookies.keys())}")
        
        try:
            response = session.get(url, headers=headers, timeout=40)
            logging.info(f"[get_phone_number] Status: {response.status_code} | Body: {response.text[:200]}...")
            if response.status_code == 200:
                return response.status_code, response.json()
            else:
                return response.status_code, response.text
        except Exception as e:
            logging.exception(f"[get_phone_number] Error: {e}")
            return 500, str(e)

    # Get phone number
    def get_phone_by_request(self, phone):
        """
        Obtiene información de portabilidad usando cookies (store_access_token).
        """
        url = f"https://store-backend.digimobil.es/v1/preorders/{self.proxies[self.position]['preorder']}/products/{self.proxies[self.position]['product']}"

        payload = {
            "actionType": "portability",
            "phoneNumber": phone,
            "operatorId": "",
            "actualBillingType": "pospaid",
            "iccidPrepay": "",
            "iccidDigi": "",
            "doPortabilityAsSoonAsPossible": True
        }
        headers = {
            'accept': '*/*',
            'accept-language': 'es-ES,es;q=0.9',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'content-type': 'application/json',
            'origin': 'https://www.digimobil.es',
            'referer': 'https://www.digimobil.es/',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
        }
        session = self.proxies[self.position]["session"]
        logging.info(f"[get_phone_by_request] URL: {url} | payload: {payload}")
        logging.info(f"[get_phone_by_request] Cookies disponibles: {list(session.cookies.keys())}")
        
        try:
            response = session.put(url, headers=headers, json=payload, timeout=40)
            logging.info(f"[get_phone_by_request] Status: {response.status_code} | Body: {response.text[:200]}...")
            if response.text != "":
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    logging.error(f"[get_phone_by_request] ✗ Error parseando JSON: {response.text}")
                    return {"_info": {"status": 500}, "_error": f"Invalid JSON: {response.text[:100]}"}
            return {"_info": {"status": 401}, "_error": "Empty response"}
        except Exception as e:
            logging.exception(f"[get_phone_by_request] Error: {e}")
            return {"_info": {"status": 500}, "_error": str(e)}

    def check_ip(self):
        session = self.proxies[self.position]["session"]
        logging.info(f"[check_ip] Using proxy: {self.proxies[self.position]['proxy']}")
        try:
            response = session.get('https://api.ipify.org?format=json', timeout=15)
            logging.info(f"[check_ip] Status: {response.status_code}, Body: {response.text}")
            return response.json()
        except Exception as e:
            logging.exception(f"[check_ip] Error using proxy: {e}")
            return {"error": str(e)}

    # Get cookies (nuevo método basado en cookies)
    def login_with_cookies(self):
        """
        Obtiene la cookie store_access_token haciendo:
        1. GET a la página principal para obtener cookies previas
        2. POST a /v2/login/online sin body para obtener store_access_token
        
        Estructura exacta como en el navegador.
        """
        session = self.proxies[self.position]["session"]
        
        # Paso 1: Obtener cookies de la página principal
        main_url = "https://www.digimobil.es/"
        headers_get = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "connection": "keep-alive",
            "upgrade-insecure-requests": "1",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        }
        
        logging.info(f"[login_with_cookies] Paso 1: Obteniendo cookies de la página principal...")
        try:
            response_main = session.get(main_url, headers=headers_get, timeout=30)
            logging.info(f"[login_with_cookies] Página principal: Status {response_main.status_code}, Cookies: {len(session.cookies)}")
            if session.cookies:
                logging.info(f"[login_with_cookies] Cookies previas obtenidas: {list(session.cookies.keys())}")
        except Exception as e:
            logging.exception(f"[login_with_cookies] Error obteniendo cookies previas: {e}")
            return {"_info": {"status": 500}, "_error": f"Error obteniendo cookies previas: {str(e)}"}
        
        # Paso 2: POST a /v2/login/online para obtener store_access_token
        login_url = "https://store-backend.digimobil.es/v2/login/online"
        headers_post = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate, br, zstd",
            "content-type": "application/json",
            "content-length": "0",  # Como en el navegador
            "origin": "https://www.digimobil.es",
            "referer": "https://www.digimobil.es/",
            "connection": "keep-alive",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
        
        logging.info(f"[login_with_cookies] Paso 2: POST a {login_url} para obtener store_access_token...")
        try:
            # POST sin body (Content-Length: 0)
            response = session.post(login_url, headers=headers_post, timeout=30)
            logging.info(f"[login_with_cookies] Login: Status {response.status_code}, Cookies: {len(session.cookies)}")
            
            # Verificar si se obtuvo la cookie store_access_token
            if 'store_access_token' in session.cookies:
                store_token = session.cookies.get('store_access_token')
                logging.info(f"[login_with_cookies] ✓ Cookie store_access_token obtenida: {store_token[:50]}...")
                return {"_info": {"status": 200}, "_result": {"store_access_token": store_token}}
            else:
                logging.warning(f"[login_with_cookies] ⚠ No se obtuvo la cookie store_access_token")
                logging.info(f"[login_with_cookies] Cookies disponibles: {list(session.cookies.keys())}")
                logging.info(f"[login_with_cookies] Response headers: {dict(response.headers)}")
                return {"_info": {"status": 401}, "_error": "No se obtuvo store_access_token"}
                
        except Exception as e:
            logging.exception(f"[login_with_cookies] Error en POST login: {e}")
            return {"_info": {"status": 500}, "_error": str(e)}
    
    # Get token (método antiguo, mantener por compatibilidad pero ya no se usa)
    def login(self):
        url = "https://store-backend.digimobil.es/v1/users/login"
        payload = {}
        headers = {}
        proxy = self.proxies[self.position]["proxy"]
        logging.info(f"[login] URL: {url} | proxy: {proxy} (MÉTODO ANTIGUO - NO SE USA)")
        try:
            response = requests.request("POST", url, headers=headers, data=payload, proxies=proxy, timeout=40)
            logging.info(f"[login] Status: {response.status_code} | Body: {response.text}")
            return json.loads(response.text)
        except Exception as e:
            logging.exception(f"[login] Error: {e}")
            return {"_info": {"status": 500}, "_error": str(e)}
    
    def get_preorder(self):
        """
        Crea un preorder usando cookies (store_access_token) en lugar de Bearer token.
        Estructura exacta como en el navegador.
        """
        url = "https://store-backend.digimobil.es/v1/preorders"
        headers = {
            'accept': '*/*',
            'accept-language': 'es-ES,es;q=0.9',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'content-type': 'application/json',
            # Nota: Content-Length será calculado automáticamente por requests
            # El navegador puede mostrar Content-Length: 26, pero requests lo calculará basado en el body
            'origin': 'https://www.digimobil.es',
            'referer': 'https://www.digimobil.es/',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
        }
        session = self.proxies[self.position]["session"]
        
        # Verificar que tenemos cookies antes de hacer la petición
        if 'store_access_token' not in session.cookies:
            logging.warning(f"[get_preorder] ⚠ No se encontró store_access_token en cookies, intentando login...")
            login_result = self.login_with_cookies()
            if login_result.get("_info", {}).get("status") != 200:
                logging.error(f"[get_preorder] ✗ Error obteniendo cookies: {login_result.get('_error')}")
                return {"_info": {"status": 401}, "_error": "No se pudo obtener store_access_token"}
        
        logging.info(f"[get_preorder] URL: {url}")
        logging.info(f"[get_preorder] Cookies disponibles: {list(session.cookies.keys())}")
        if 'store_access_token' in session.cookies:
            logging.info(f"[get_preorder] store_access_token: {session.cookies.get('store_access_token')[:50]}...")
        
        try:
            # POST con body vacío (json={} enviará "{}" que es 2 bytes)
            # Si el navegador envía Content-Length: 26, puede ser por un body diferente
            # Por ahora, dejamos que requests calcule Content-Length automáticamente
            response = session.post(url, headers=headers, json={}, timeout=40)
            logging.info(f"[get_preorder] Status: {response.status_code} | Body: {response.text[:200]}...")
            
            if response.status_code == 201:
                if response.text:
                    try:
                        result = response.json()
                        # La respuesta ya tiene la estructura correcta: {"_result": {...}, "_info": {...}, "_error": []}
                        # Solo necesitamos asegurarnos de que _info.status sea 201
                        if "_info" in result:
                            result["_info"]["status"] = 201
                        else:
                            result["_info"] = {"status": 201}
                        logging.info(f"[get_preorder] ✓ Preorder creado exitosamente")
                        return result
                    except json.JSONDecodeError:
                        logging.error(f"[get_preorder] ✗ Error parseando JSON: {response.text}")
                        return {"_info": {"status": 500}, "_error": f"Invalid JSON: {response.text[:100]}"}
                else:
                    logging.warning(f"[get_preorder] ⚠ Respuesta vacía con status 201")
                    return {"_info": {"status": 201}, "_result": {}, "_error": []}
            else:
                logging.warning(f"[get_preorder] ⚠ Status inesperado: {response.status_code}")
                return {"_info": {"status": response.status_code}, "_error": response.text[:200], "_result": None}
                
        except Exception as e:
            logging.exception(f"[get_preorder] Error: {e}")
            return {"_info": {"status": 500}, "_error": str(e)}
    
    def get_config(self):
        """
        Obtiene configuración usando cookies (store_access_token).
        """
        url = f"https://store-backend.digimobil.es/v1/preorders/{self.proxies[self.position]['preorder']}/config"
        payload = {
            "products": [
                {
                    "id": 1498
                }
            ]
        }
        headers = {
            'accept': '*/*',
            'accept-language': 'es-ES,es;q=0.9',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'content-type': 'application/json',
            'origin': 'https://www.digimobil.es',
            'referer': 'https://www.digimobil.es/',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
        }
        session = self.proxies[self.position]["session"]
        logging.info(f"[get_config] URL: {url} | payload: {payload}")
        logging.info(f"[get_config] Cookies disponibles: {list(session.cookies.keys())}")
        
        try:
            response = session.post(url, headers=headers, json=payload, timeout=40)
            logging.info(f"[get_config] Status: {response.status_code} | Body: {response.text[:200]}...")
            if response.text:
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError:
                    logging.error(f"[get_config] ✗ Error parseando JSON: {response.text}")
                    return {"_info": {"status": 500}, "_error": f"Invalid JSON: {response.text[:100]}"}
            return {"_info": {"status": 500}, "_error": "Empty response"}
        except Exception as e:
            logging.exception(f"[get_config] Error: {e}")
            return {"_info": {"status": 500}, "_error": str(e)}

    def refresh_token(self):
        """
        Método antiguo - ya no se usa. Se usa login_with_cookies() en su lugar.
        Mantenido por compatibilidad.
        """
        logging.info(f"[refresh_token] MÉTODO ANTIGUO - Usar login_with_cookies() en su lugar")
        return self.login_with_cookies()

    def check_token_and_refresh(self, data):
        """
        Verifica si la respuesta indica que se necesita renovar la cookie.
        Si es necesario, obtiene nuevas cookies.
        """
        result = False
        if data.get("_info", {}).get("status") in [401, 498]:
            logging.info(f"[check_token_and_refresh] Status {data['_info']['status']} detectado, renovando cookies...")
            data_refresh = self.login_with_cookies()
            if data_refresh.get("_info", {}).get("status") == 200:
                logging.info(f"[check_token_and_refresh] ✓ Cookies renovadas correctamente")
                result = True
            else:
                logging.error(f"[check_token_and_refresh] ✗ Error renovando cookies: {data_refresh.get('_error')}")
        return result

    def get_access(self, token="", get_cart=True):
        """
        Obtiene acceso usando cookies (store_access_token) en lugar de tokens Bearer.
        
        Args:
            token: Mantenido por compatibilidad, ya no se usa
            get_cart: Si True, intenta obtener el cart (necesario para validate_phone_number).
                     Si False, solo obtiene cookies y preorder (suficiente para get_phone_number).
        """
        logging.info("[+] Init Get Access (usando cookies)...")
        
        # Obtener cookies (store_access_token)
        data_login = self.login_with_cookies()
        if data_login.get("_info", {}).get("status") != 200:
            logging.error(f"[get_access] ✗ Error obteniendo cookies: {data_login.get('_error')}")
            return False
        
        logging.info("[get_access] ✓ Cookies obtenidas correctamente")
        session = self.proxies[self.position]["session"]
        if 'store_access_token' in session.cookies:
            logging.info(f"[get_access] store_access_token: {session.cookies.get('store_access_token')[:50]}...")
        
        # Obtener preorder solo si get_cart es True (para validate_phone_number se necesita preorder)
        # Para get_phone_number no se necesita preorder ni cart, solo cookies
        if get_cart:
            # Obtener preorder
            while True:
                data_preorder = self.get_preorder()
                if not self.check_token_and_refresh(data_preorder):
                    break
            
            if data_preorder.get("_info", {}).get("status") != 201:
                logging.error(f"[get_access] ✗ Error obteniendo preorder: {data_preorder}")
                return False
            
            # Extraer trackingNumber del resultado
            result = data_preorder.get("_result", {})
            if isinstance(result, dict) and "trackingNumber" in result:
                tracking_number = result["trackingNumber"]
            elif isinstance(result, str):
                # Si _result es un string (trackingNumber directo)
                tracking_number = result
            else:
                logging.error(f"[get_access] ✗ No se pudo extraer trackingNumber de: {data_preorder}")
                return False
            
            logging.info(f"[get_access] ✓ Preorder obtenido: {tracking_number}")
            self.proxies[self.position]['preorder'] = tracking_number

            # Obtener cart
            cont = 0
            while True:
                cart_data = self.update_cart()
                logging.info(f"[get_access] Cart data: {cart_data}")
                if cart_data[0] == 200:
                    self.proxies[self.position]['cart'] = cart_data[1]["items"][0]["itemValidated"]["shoppingCartLineId"]
                    logging.info(f"[get_access] ✓ Cart obtenido: {self.proxies[self.position]['cart']}")
                    break
                else:
                    logging.info("[-] Error get shoppingCartLineId, Reintentando...")

                if cont >= 3:
                    logging.warning("[get_access] ⚠ Máximo de reintentos alcanzado para obtener cart (puede continuar sin cart)")
                    # No retornamos False, porque para get_phone_number no es necesario
                    break
                cont += 1
        else:
            logging.info("[get_access] ⚠ Modo simple: solo cookies (no se obtiene preorder ni cart)")
        
        logging.info("[+] Finish get access...")
        return True


if __name__ == "__main__":
    phone = DigiPhone(user="admin", reprocess=False)
    
    # Verificar IP del proxy
    ip = phone.check_ip()
    logging.info(f"[main] IP del proxy: {ip.get('ip', 'unknown')}")
    print(f"IP del proxy: {ip.get('ip', 'unknown')}")
    
    # Obtener acceso usando cookies (nuevo método)
    logging.info("[main] Obteniendo acceso con cookies...")
    access_success = phone.get_access()
    
    if access_success:
        logging.info("[main] ✓ Acceso obtenido correctamente")
        print("✓ Acceso obtenido correctamente")
        # Acceder a los atributos usando la posición actual
        current_proxy = phone.proxies[phone.position]
        print(f"  Preorder: {current_proxy.get('preorder', 'N/A')}")
        print(f"  Cart: {current_proxy.get('cart', 'N/A')}")
        
        # Consultar 100 números telefónicos
        total_numbers = 100
        successful = 0
        failed = 0
        operators_count = {}
        
        print(f"\n{'='*60}")
        print(f"INICIANDO CONSULTA DE {total_numbers} NÚMEROS")
        print(f"{'='*60}\n")
        
        for i in range(total_numbers):
            _phone_number = random.randint(600000000, 700000000)
            logging.info(f"[main] [{i+1}/{total_numbers}] Consultando número: {_phone_number}")
            print(f"[{i+1:3d}/{total_numbers}] Consultando {_phone_number}...", end=" ")
            
            data_phone = phone.get_phone_number(phone=_phone_number)
            
            if isinstance(data_phone, tuple):
                status, result = data_phone
                if status == 200 and isinstance(result, dict):
                    # Consulta exitosa - operador encontrado
                    operator_name = result.get('name', 'Desconocido')
                    operator_trade = result.get('tradeName', '')
                    operator_id = result.get('operatorId', 'N/A')
                    
                    # Contar operadores
                    if operator_name not in operators_count:
                        operators_count[operator_name] = 0
                    operators_count[operator_name] += 1
                    
                    successful += 1
                    print(f"✓ {operator_name}" + (f" ({operator_trade})" if operator_trade else ""))
                    logging.info(f"[main] [{i+1}/{total_numbers}] ✓ {operator_name} (ID: {operator_id})")
                elif status == 404:
                    # 404 con "Operator not found" = número de Digi (no es un error)
                    error_msg = result if isinstance(result, str) else str(result)
                    if "Operator not found" in error_msg or (isinstance(result, dict) and result.get("message") == "Operator not found"):
                        operator_name = "DIGI SPAIN TELECOM, S.L."
                        
                        # Contar operadores
                        if operator_name not in operators_count:
                            operators_count[operator_name] = 0
                        operators_count[operator_name] += 1
                        
                        successful += 1
                        print(f"✓ {operator_name} (Operator not found)")
                        logging.info(f"[main] [{i+1}/{total_numbers}] ✓ {operator_name} (Operator not found - Digi)")
                    else:
                        # Otro tipo de 404 (error real)
                        failed += 1
                        print(f"✗ Error {status}: {error_msg[:50]}")
                        logging.warning(f"[main] [{i+1}/{total_numbers}] ✗ Error {status}: {error_msg}")
                else:
                    # Error en la consulta (otros códigos de error)
                    failed += 1
                    error_msg = result if isinstance(result, str) else str(result)
                    print(f"✗ Error {status}: {error_msg[:50]}")
                    logging.warning(f"[main] [{i+1}/{total_numbers}] ✗ Error {status}: {error_msg}")
            else:
                # Formato inesperado
                failed += 1
                print(f"✗ Formato inesperado")
                logging.warning(f"[main] [{i+1}/{total_numbers}] ✗ Formato inesperado: {data_phone}")
            
            # Pequeña pausa para no saturar el servidor
            if (i + 1) % 10 == 0:
                print(f"\n  Progreso: {i+1}/{total_numbers} | Exitosas: {successful} | Fallidas: {failed}")
                sleep(0.5)  # Pausa cada 10 consultas
            else:
                sleep(0.1)  # Pausa pequeña entre consultas
        
        # Resumen final
        print(f"\n{'='*60}")
        print(f"RESUMEN FINAL")
        print(f"{'='*60}")
        print(f"Total consultados: {total_numbers}")
        print(f"Exitosas: {successful} ({successful*100/total_numbers:.1f}%)")
        print(f"Fallidas: {failed} ({failed*100/total_numbers:.1f}%)")
        print(f"\nOperadores encontrados:")
        for operator, count in sorted(operators_count.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {operator}: {count} ({count*100/total_numbers:.1f}%)")
        print(f"{'='*60}\n")
        
        logging.info(f"[main] ========== RESUMEN FINAL ==========")
        logging.info(f"[main] Total: {total_numbers}, Exitosas: {successful}, Fallidas: {failed}")
        logging.info(f"[main] Operadores: {operators_count}")
    else:
        logging.error("[main] ✗ Error obteniendo acceso")
        print("✗ Error obteniendo acceso")