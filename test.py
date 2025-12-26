import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import ssl

class TLSAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.context = create_urllib3_context()
        # Define la versión mínima de TLS
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2  # TLS v1.2
        super().__init__(*args, **kwargs)

session = requests.Session()
session.mount("https://", TLSAdapter())

try:
    response = session.get("https://store-backend.digimobil.es/v1/preorders/None/products/None")
    print(response.status_code)
except requests.exceptions.SSLError as e:
    print("SSL error:", e)

