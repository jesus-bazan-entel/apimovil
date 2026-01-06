"""
Sistema de Rotación de Proxies para APIMOVIL
Integrado con DigiPhone existente

Archivo: app/proxy_rotation_system.py
"""

import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ProxyRotator:
    """Gestor de rotación de proxies con blacklist y métricas"""
    
    def __init__(self, max_response_time=5.0, blacklist_duration=300):
        """
        Args:
            max_response_time: Tiempo máximo en segundos (default: 5s)
            blacklist_duration: Duración de blacklist en segundos (default: 300s = 5min)
        """
        self.max_response_time = max_response_time
        self.blacklist_duration = blacklist_duration
        
        # Blacklist temporal: {proxy_id: timestamp_expiracion}
        self.blacklist = {}
        
        # Métricas: {proxy_id: [tiempo1, tiempo2, ...]}
        self.metrics = {}
        
        # Contador de intentos: {proxy_id: num_intentos}
        self.attempt_counts = {}
    
    def is_blacklisted(self, proxy_id: str) -> bool:
        """Verifica si un proxy está en blacklist"""
        if proxy_id not in self.blacklist:
            return False
        
        if datetime.now().timestamp() > self.blacklist[proxy_id]:
            del self.blacklist[proxy_id]
            return False
        
        return True
    
    def add_to_blacklist(self, proxy_id: str, reason: str = "timeout"):
        """Añade proxy a blacklist temporal"""
        expiry_time = datetime.now() + timedelta(seconds=self.blacklist_duration)
        self.blacklist[proxy_id] = expiry_time.timestamp()
        logger.warning(f"⚫ Proxy blacklisted: {proxy_id[:60]}... - Razón: {reason}")
    
    def record_response_time(self, proxy_id: str, response_time: float):
        """Registra tiempo de respuesta"""
        if proxy_id not in self.metrics:
            self.metrics[proxy_id] = []
        
        self.metrics[proxy_id].append(response_time)
        
        # Mantener solo últimos 10
        if len(self.metrics[proxy_id]) > 10:
            self.metrics[proxy_id] = self.metrics[proxy_id][-10:]
    
    def get_avg_response_time(self, proxy_id: str) -> float:
        """Obtiene tiempo promedio de respuesta"""
        if proxy_id not in self.metrics or not self.metrics[proxy_id]:
            return 0.0
        return sum(self.metrics[proxy_id]) / len(self.metrics[proxy_id])
    
    def increment_attempts(self, proxy_id: str):
        """Incrementa contador de intentos"""
        self.attempt_counts[proxy_id] = self.attempt_counts.get(proxy_id, 0) + 1
    
    def get_best_proxy_index(self, total_proxies: int) -> int:
        """
        Retorna el índice del mejor proxy disponible
        Compatible con lista de proxies de DigiPhone
        """
        # Filtrar proxies disponibles (no en blacklist)
        available_indices = []
        for idx in range(total_proxies):
            proxy_id = f"proxy_{idx}"
            if not self.is_blacklisted(proxy_id):
                available_indices.append((idx, self.get_avg_response_time(proxy_id)))
        
        if not available_indices:
            logger.warning("⚠️ Todos los proxies en blacklist. Limpiando...")
            self.blacklist.clear()
            return 0  # Retornar primer proxy
        
        # Ordenar por tiempo de respuesta (menor es mejor)
        available_indices.sort(key=lambda x: x[1])
        return available_indices[0][0]
    
    def get_stats(self) -> Dict:
        """Estadísticas del sistema"""
        total_proxies = len(self.metrics)
        blacklisted = len(self.blacklist)
        avg_times = {pid: self.get_avg_response_time(pid) for pid in self.metrics.keys()}
        fast_proxies = sum(1 for t in avg_times.values() if 0 < t < self.max_response_time)
        slow_proxies = sum(1 for t in avg_times.values() if t >= self.max_response_time)
        
        return {
            "total_proxies_tested": total_proxies,
            "blacklisted": blacklisted,
            "fast_proxies": fast_proxies,
            "slow_proxies": slow_proxies,
            "max_response_time": self.max_response_time,
        }


# Instancia global del rotador
_global_rotator = None


def get_proxy_rotator():
    """Obtiene instancia global del rotador"""
    global _global_rotator
    if _global_rotator is None:
        _global_rotator = ProxyRotator(
            max_response_time=5.0,
            blacklist_duration=300
        )
    return _global_rotator


def make_request_with_rotation(session, method: str, url: str, proxy_index: int, 
                               max_retries: int = 3, **kwargs) -> Tuple[Optional[requests.Response], int]:
    """
    Hace una petición HTTP con rotación automática de proxies
    Compatible con DigiPhone
    
    Args:
        session: requests.Session con proxies configurados
        method: 'GET', 'POST', etc.
        url: URL destino
        proxy_index: Índice del proxy actual
        max_retries: Número máximo de reintentos
        **kwargs: Argumentos para requests
    
    Returns:
        (response, proxy_index_usado) o (None, -1) si falla
    """
    rotator = get_proxy_rotator()
    timeout = kwargs.pop('timeout', 30)
    current_proxy_index = proxy_index
    
    for attempt in range(max_retries):
        proxy_id = f"proxy_{current_proxy_index}"
        rotator.increment_attempts(proxy_id)
        
        try:
            start_time = time.time()
            
            response = session.request(
                method=method,
                url=url,
                timeout=timeout,
                **kwargs
            )
            
            elapsed = time.time() - start_time
            rotator.record_response_time(proxy_id, elapsed)
            
            # Verificar si fue lento
            if elapsed > rotator.max_response_time:
                logger.warning(
                    f"⚠️ Proxy lento: {elapsed:.2f}s > {rotator.max_response_time}s - proxy_{current_proxy_index}"
                )
                rotator.add_to_blacklist(proxy_id, reason=f"slow ({elapsed:.2f}s)")
                
                # Rotar si quedan reintentos
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Rotando a otro proxy (intento {attempt + 2}/{max_retries})")
                    # Aquí necesitamos que DigiPhone rote el proxy
                    # Por ahora retornamos None para indicar que debe rotar
                    return (None, -1)
            else:
                logger.info(f"✅ Respuesta OK en {elapsed:.2f}s con proxy_{current_proxy_index}")
            
            return (response, current_proxy_index)
            
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Timeout con proxy_{current_proxy_index}")
            rotator.add_to_blacklist(proxy_id, reason="timeout")
            if attempt < max_retries - 1:
                return (None, -1)
                
        except requests.exceptions.ProxyError:
            logger.warning(f"🚫 ProxyError con proxy_{current_proxy_index}")
            rotator.add_to_blacklist(proxy_id, reason="proxy_error")
            if attempt < max_retries - 1:
                return (None, -1)
                
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 ConnectionError con proxy_{current_proxy_index}")
            rotator.add_to_blacklist(proxy_id, reason="connection_error")
            if attempt < max_retries - 1:
                return (None, -1)
                
        except Exception as e:
            logger.error(f"❌ Error con proxy_{current_proxy_index}: {type(e).__name__}")
            rotator.add_to_blacklist(proxy_id, reason="error")
            if attempt < max_retries - 1:
                return (None, -1)
        
        time.sleep(1)
    
    logger.error(f"❌ Fallaron todos los intentos ({max_retries})")
    return (None, -1)
