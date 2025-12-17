from bs4 import BeautifulSoup
import random
import threading
from time import sleep
import requests
import json
from .models import Proxy
from .models import Movil
import logging

_logging = logging.basicConfig(filename="logger.log", level=logging.INFO)


class DigiPhone:
    def __init__(self, user, reprocess) -> None:
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
                self.proxies.append({
                    "proxy": {
                        "http": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}",
                        "https": f"socks5h://{uname}:{p.password}@{p.ip}:{p.port_min}"
                    },
                    "token": None,
                    "preorder": None,
                    "product": None,
                    "item": p,
                    "cart": None
                })
        else:
            #if self.proxys:
            for p in self.proxys:#range(int(self.proxys.port_min), int(self.proxys.port_max), 1):
                self.proxies.append({
                    "proxy": {
                        "http": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}",
                        "https": f"socks5h://{p.username}:{p.password}@{p.ip}:{p.port_min}"
                    },
                    "token": None,
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
        url = f"https://store-backend.digimobil.es/v2/preorders/{self.proxies[self.position]['preorder']}/shopping-carts"
    
        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "authorization": f'Bearer {self.proxies[self.position]["token"]}',
            "content-type": "application/json",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Google Chrome\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": "\"Android\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        }

        data = {
            "products": [1577],
            "contractId": None,
            "removePackagesIds": []
        }

        response = requests.put(url, headers=headers, json=data, proxies=self.proxies[self.position]["proxy"])
        return response.status_code, response.json() if response.status_code == 200 else response.text
    
    def validate_phone_number(self, phone):
        url = f"https://store-backend.digimobil.es/v2/preorders/{self.proxies[self.position]['preorder']}/shopping-cart-lines/{self.proxies[self.position]['cart']}/validate-phonenumber/{phone}"
        
        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "authorization": f'Bearer {self.proxies[self.position]["token"]}',
            "content-type": "application/json",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Google Chrome\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": "\"Android\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        }

        response = requests.get(url, headers=headers, proxies=self.proxies[self.position]["proxy"])
        return response.status_code, response.json() if response.status_code == 200 else response.text

    def get_phone_number(self, phone):
        url = f"https://store-backend.digimobil.es/v2/operators/by-line-code/{phone}"
    
        headers = {
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "authorization": f'Bearer {self.proxies[self.position]["token"]}',
            "content-type": "application/json",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Not(A:Brand\";v=\"99\", \"Google Chrome\";v=\"133\", \"Chromium\";v=\"133\"",
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": "\"Android\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        }

        response = requests.get(url, headers=headers, proxies=self.proxies[self.position]["proxy"])
        return response.status_code, response.json() if response.status_code == 200 else response.text


    # Get phone number
    def get_phone_by_request(self, phone):
        #Execute Web Scraping
        #logging.info(f"S.A.M. proxies: {self.proxies}") 
        #logging.info(f"S.A.M. proxies: {self.proxies[self.position]}") 
        #logging.info(f"S.A.M. proxies: {self.proxies[self.position]['preorder']}") 
        url = f"https://store-backend.digimobil.es/v1/preorders/{self.proxies[self.position]['preorder']}/products/{self.proxies[self.position]['product']}"
                
        payload = json.dumps({
            "actionType": "portability",
            "phoneNumber": phone,
            "operatorId": "",
            "actualBillingType": "pospaid",
            "iccidPrepay": "",
            "iccidDigi": "",
            "doPortabilityAsSoonAsPossible": True
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.proxies[self.position]["token"]}'
        }
        response = requests.request("PUT", url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        #response = self.session.put(url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        logging.info(f"response.text: {response.text}")
        if response.text != "":
            return json.loads(response.text)
        return {"_info": {"status": 401}}

    def check_ip(self):
        response = requests.get('https://api.ipify.org?format=json', proxies=self.proxies[self.position]["proxy"])
        return response.json()

    # Get token
    def login(self):
        logging.info("[LOGIN] Starting login...")
        url = "https://store-backend.digimobil.es/v1/users/login"
        payload = {}
        headers = {}
        response = requests.request("POST", url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        logging.info(f"[LOGIN] Status: {response.status_code}")
        return json.loads(response.text)
    
    def get_preorder(self):
        logging.info("[PREORDER] Requesting preorder...")
        url = "https://store-backend.digimobil.es/v1/preorders"
        payload = {}
        headers = {
            'Authorization': f'Bearer {self.proxies[self.position]["token"]}'
        }
        response = requests.request("POST", url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        logging.info(f"[PREORDER] Status: {response.status_code}")
        return json.loads(response.text)
    
    def get_config(self):
        url = f"https://store-backend.digimobil.es/v1/preorders/{self.proxies[self.position]['preorder']}/config"
        payload = json.dumps({
            "products": [
                {
                    "id": 1577
                }
            ]
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.proxies[self.position]["token"]}'
        }
        response = requests.request("POST", url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        return json.loads(response.text)

    def refresh_token(self):
        url = "https://store-backend.digimobil.es/v1/users/refresh-token"
        payload = {}
        headers = {
            'Authorization': f'Bearer {self.proxies[self.position]["token"]}'
        }
        response = requests.request("POST", url, headers=headers, data=payload, proxies=self.proxies[self.position]["proxy"])
        return json.loads(response.text)

    def check_token_and_refresh(self, data):
        result = False
        #print(data)
        if data["_info"]["status"] in [401, 498]:
            data_refresh = self.login()
            self.proxies[self.position]["token"] = data_refresh["_result"]["token"]
            result = True
        #if result:
        #    print("Get Token: "+str(self.token))
        return result

    def get_access(self, token=""):
        logging.info("[GET_ACCESS] Init Get Token...")
        if not token:
            data_login = self.login()
            self.proxies[self.position]["token"] = data_login["_result"]["token"]
        else:
            self.proxies[self.position]["token"] = token
        #print("Current Token: "+str(self.token))
        while True:
            data_preorder = self.get_preorder()
            if not self.check_token_and_refresh(data_preorder):
                break
        logging.info(f"[GET_ACCESS] Preorder data: {data_preorder}")
        self.proxies[self.position]['preorder'] = data_preorder["_result"]["trackingNumber"]

        cont = 0
        while True:
            cart_data = self.update_cart()
            logging.info(f"[CART] Update response: {cart_data}")
            if cart_data[0] == 200:
                self.proxies[self.position]['cart'] = cart_data[1]["items"][0]["itemValidated"]["shoppingCartLineId"]
                break
            else:
                logging.warning("[CART] Error getting shoppingCartLineId, Retrying...")

            if cont >= 3:
                break
            cont += 1


if __name__ == "__main__":
    phone = DigiPhone()
    #token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOm51bGwsImlzcyI6Imh0dHBzOlwvXC9cL2luZGV4LnBocCIsImNpZCI6Imh0dHBzOlwvXC9zdG9yZS1hcGkuZGlnaW1vYmlsLmVzIiwiaWF0IjoxNzE3MjY4NDMxLCJleHAiOjE3MTcyNjkwMzEsInNjb3BlIjoicmVhZCB3cml0ZSIsImRhdGEiOnsiaWQiOm51bGwsImFub24iOnRydWUsImlwIjoiOTguOTguMTcxLjUwIiwic2Vzc2lvbl91aWQiOiIxNzE3MjY4NDMxOTY1MjIwIiwidXMiOjEwMCwiYyI6MX19.fBUWh1fVvq-6AcZSCeqxpz6J0qTOzhBH-a4w6PnZ_68"
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOm51bGwsImlzcyI6Imh0dHBzOlwvXC9cL2luZGV4LnBocCIsImNpZCI6Imh0dHBzOlwvXC9zdG9yZS1hcGkuZGlnaW1vYmlsLmVzIiwiaWF0IjoxNzI5NzYzODQ5LCJleHAiOjE3Mjk3NjQ0NDksInNjb3BlIjoicmVhZCB3cml0ZSIsImRhdGEiOnsiaWQiOm51bGwsImFub24iOnRydWUsImlwIjoiMTg1LjQ3LjEzMS41MyIsInNlc3Npb25fdWlkIjoiMTcyOTc2Mzg0OTM5NzA4OCIsInVzIjoxMDAsImMiOjF9fQ.nimDL37T2kx9BUduGIC5JAotYR_fNeiljsP3Vt3obsg",
