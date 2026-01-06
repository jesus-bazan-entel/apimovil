"""
Extensión de DigiPhone con Rotación Automática de Proxies
Archivo: app/browser_extended.py (VERSIÓN CORREGIDA)

Este archivo extiende DigiPhone con capacidades de rotación automática
sin modificar el código original de browser.py
"""

from app.browser import DigiPhone
from app.proxy_rotation_system import get_proxy_rotator, make_request_with_rotation
import requests
import logging

logger = logging.getLogger(__name__)


class DigiPhoneWithRotation(DigiPhone):
    """
    Extensión de DigiPhone que agrega rotación automática de proxies
    """
    
    def __init__(self, user, reprocess=False):
        """Inicializa DigiPhone con rotación"""
        super().__init__(user, reprocess)
        self.rotator = get_proxy_rotator()
        self.rotation_enabled = True
        self.max_rotation_retries = 3
        
        # Asegurar que index_proxy existe
        if not hasattr(self, 'index_proxy'):
            self.index_proxy = 0
    
    def _get_current_proxy_index(self):
        """Obtiene el índice del proxy actual de forma segura"""
        return getattr(self, 'index_proxy', 0)
    
    def _set_proxy_index(self, index):
        """Establece el índice del proxy de forma segura"""
        self.index_proxy = index
    
    def _rotate_to_best_proxy(self):
        """Rota al mejor proxy disponible según métricas"""
        if self._len_proxy == 0:
            logger.error("❌ No hay proxies disponibles")
            return
        
        # Obtener índice actual de forma segura
        current_index = self._get_current_proxy_index()
        
        # Obtener mejor proxy
        best_index = self.rotator.get_best_proxy_index(self._len_proxy)
        
        if best_index != current_index:
            logger.info(f"🔄 Proxy rotado: {current_index} → {best_index}")
            self._set_proxy_index(best_index)
        else:
            logger.info(f"ℹ️ Manteniendo proxy actual: {current_index}")
    
    def _update_session_with_current_proxy(self):
        """Actualiza la sesión con el proxy actual"""
        if self._len_proxy == 0:
            logger.warning("⚠️ No hay proxies disponibles para actualizar sesión")
            return
        
        try:
            # Obtener índice actual
            current_index = self._get_current_proxy_index()
            
            # Verificar que el índice es válido
            if current_index >= len(self.listproxy):
                logger.warning(f"⚠️ Índice de proxy inválido: {current_index} (max: {len(self.listproxy)-1})")
                current_index = 0
                self._set_proxy_index(0)
            
            # Obtener configuración del proxy actual
            proxy_config = self.listproxy[current_index]
            
            # Crear nueva sesión con el proxy actual
            self.session = requests.Session()
            self.session.proxies = {
                "http": proxy_config['http'],
                "https": proxy_config['https']
            }
            
            # Limpiar cookies previas
            self.cookies = None
            
            logger.info(f"🔄 Sesión actualizada con proxy {current_index}")
            
        except Exception as e:
            logger.error(f"❌ Error actualizando sesión: {e}")
    
    def get_access(self, phone="", get_cart=False):
        """
        Override de get_access con rotación automática
        """
        if self._len_proxy == 0:
            logger.error("❌ No hay proxies disponibles")
            return False
        
        # Intentar obtener acceso con rotación
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"🔐 Intento {attempt + 1}/{max_attempts} de obtener acceso con proxy {self._get_current_proxy_index()}")
                
                # Llamar al método original del padre
                success = super().get_access(phone, get_cart)
                
                if success:
                    logger.info(f"✅ Acceso obtenido correctamente con proxy {self._get_current_proxy_index()}")
                    return True
                else:
                    logger.warning(f"⚠️ No se pudo obtener acceso (intento {attempt + 1})")
                    
                    # Blacklist del proxy actual
                    current_index = self._get_current_proxy_index()
                    proxy_id = f"proxy_{current_index}"
                    self.rotator.add_to_blacklist(proxy_id, reason="access_failed")
                    
                    if attempt < max_attempts - 1:
                        # Rotar al mejor proxy
                        self._rotate_to_best_proxy()
                        self._update_session_with_current_proxy()
                        
            except Exception as e:
                logger.error(f"❌ Error obteniendo acceso: {e}")
                
                # Blacklist del proxy actual
                current_index = self._get_current_proxy_index()
                proxy_id = f"proxy_{current_index}"
                self.rotator.add_to_blacklist(proxy_id, reason=f"error: {type(e).__name__}")
                
                if attempt < max_attempts - 1:
                    self._rotate_to_best_proxy()
                    self._update_session_with_current_proxy()
        
        logger.error(f"❌ No se pudo obtener acceso después de {max_attempts} intentos")
        return False
    
    def get_phone_number(self, phone):
        """
        Override de get_phone_number con rotación automática
        """
        if self._len_proxy == 0:
            return (500, "No hay proxies disponibles")
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                current_index = self._get_current_proxy_index()
                logger.info(f"📞 Consultando {phone} (intento {attempt + 1}/{max_attempts}, proxy {current_index})")
                
                # Llamar al método original
                result = super().get_phone_number(phone)
                
                # Verificar el resultado
                if isinstance(result, tuple) and len(result) == 2:
                    status_code, data = result
                    
                    if status_code in [200, 404]:
                        # Éxito
                        logger.info(f"✅ {phone} procesado: status {status_code}")
                        return result
                    else:
                        last_error = f"Status {status_code}"
                        logger.warning(f"⚠️ Status inesperado: {status_code}")
                        
                        # Blacklist del proxy
                        proxy_id = f"proxy_{current_index}"
                        self.rotator.add_to_blacklist(proxy_id, reason=f"status_{status_code}")
                else:
                    last_error = "Formato de respuesta inválido"
                    logger.warning(f"⚠️ Formato inválido: {result}")
                
                # Si llegamos aquí, hubo un problema - rotar
                if attempt < max_attempts - 1:
                    logger.info(f"🔄 Rotando proxy para siguiente intento")
                    self._rotate_to_best_proxy()
                    self._update_session_with_current_proxy()
                    
                    # Re-obtener acceso con nuevo proxy
                    if not self.get_access("", get_cart=False):
                        logger.warning(f"⚠️ No se pudo obtener acceso con nuevo proxy")
                        continue
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Error consultando {phone}: {e}")
                
                # Blacklist del proxy
                current_index = self._get_current_proxy_index()
                proxy_id = f"proxy_{current_index}"
                self.rotator.add_to_blacklist(proxy_id, reason=f"exception: {type(e).__name__}")
                
                if attempt < max_attempts - 1:
                    self._rotate_to_best_proxy()
                    self._update_session_with_current_proxy()
        
        logger.error(f"❌ {phone} falló después de {max_attempts} intentos. Último error: {last_error}")
        return (500, f"ERROR_SCRAPING: {last_error}")
    
    def enable_rotation(self):
        """Habilita la rotación automática"""
        self.rotation_enabled = True
        logger.info("✅ Rotación automática habilitada")
    
    def disable_rotation(self):
        """Deshabilita la rotación automática"""
        self.rotation_enabled = False
        logger.info("⚠️ Rotación automática deshabilitada")
    
    def get_rotation_stats(self):
        """Obtiene estadísticas de rotación"""
        return self.rotator.get_stats()


# Función auxiliar para crear DigiPhone con rotación
def create_digiphone_with_rotation(user, reprocess=False):
    """
    Factory function para crear DigiPhone con rotación
    
    Uso:
        digiPhone = create_digiphone_with_rotation(user)
    """
    return DigiPhoneWithRotation(user, reprocess)
