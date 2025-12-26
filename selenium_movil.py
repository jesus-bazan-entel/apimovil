import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys  # Importar Keys para presionar Enter
from time import sleep
from selenium.common.exceptions import TimeoutException

# Configurar las opciones del navegador
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")  # Evitar problemas con permisos
chrome_options.add_argument("--disable-dev-shm-usage")  # Evitar problemas de memoria compartida
chrome_options.add_argument("--disable-gpu")  # Si estás corriendo en un entorno sin GPU
  

# Agregar los headers personalizados
custom_headers = {
    'Host': 'tienda.digimobil.es',
    'Sec-Ch-Ua': '"Chromium";v="127", "Not)A;Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"macOS"',
    'Accept-Language': 'es-419',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.100 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
    'Accept-Encoding': 'gzip, deflate, br',
    'Priority': 'u=0, i',
    'Connection': 'keep-alive'
}

# Crear el WebDriver remoto
driver = None

try:
    # Crear el WebDriver remoto con Selenium Wire
    driver = webdriver.Remote(
        #command_executor='http://172.17.0.2:4444/wd/hub',
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=chrome_options,  # Usar 'options' en lugar de 'desired_capabilities'
    )

    # Acceder al DevTools Protocol
    #driver.execute_cdp_cmd('Network.enable', {})
    # Modificar las solicitudes usando DevTools Protocol
    #driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {'headers': custom_headers})

    # Abrir una página web
    #driver.get("https://www.google.com")
    driver.get("https://www.digimobil.es/combina-telefonia-internet?movil=1494")

    # Imprimir información sobre la página
    #print(driver.title)
    #print(driver.page_source)
    #print(driver.get_cookies())
    #print(driver.current_window_handle)
    #print(driver.window_handles)
    #print("FASE 1")

    # Espera hasta que el enlace esté presente en el DOM
    link = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'config_loquiero'))
    )

    # Usa JavaScript para hacer clic en el enlace
    driver.execute_script("arguments[0].click();", link)
    #print(driver.title)
    #print(driver.page_source)
    #print(driver.current_url)
    #print("FASE 2")

    # Esperar unos segundos para que la redirección ocurra
    WebDriverWait(driver, 10).until(lambda driver: driver.current_url != 'https://tienda.digimobil.es/')

    # Capturar la URL redirigida
    redirected_url = driver.current_url
    #print(f"Página redirigida a: {redirected_url}")
    #print(driver.title)
    #print(driver.page_source)
    #print("FASE 3")

    # Localizar el campo de número telefónico
    phone_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'phoneNumber-0'))
    )

    # Ingresar el número telefónico
    phone_input.clear()  # Limpiar cualquier valor previo
    #phone_input.send_keys("607719518")  # Ingresar el número telefónico
    #phone_input.send_keys("698765432")  # Ingresar el número telefónico
    phone_input.send_keys("607650212")  # Ingresar el número telefónico

    sleep(3)
    #print(driver.page_source)
    #print("FASE 4")

    operator_value = driver.find_element(By.NAME, 'operator-0').get_attribute('value')
    print(f"Operador detectado: {operator_value}")

    # 5. Capturar el valor del operador
    #operator_value = driver.find_element(By.ID, 'operator-0').get_attribute('value')
    #print(f"Operador detectado: {operator_value}")

except TimeoutException:
    print("La URL no cambió dentro del tiempo esperado. Continuando con la ejecución.")

except Exception as e:
    # Manejar cualquier excepción (opcionalmente imprime el error)
    print(f"Error durante la ejecución de Selenium: {e}")
    traceback.print_exc()

finally:
    # Cerrar el navegador (independientemente de si hubo un error o no)
    if driver is not None:
        driver.quit()
