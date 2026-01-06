# PRD - API Móvil: Sistema de Consulta de Operadores Telefónicos

## 📋 Documento de Requerimientos del Producto

**Versión:** 2.0  
**Fecha:** Enero 2026  
**Propietario:** jesus-bazan-entel  

---

## 1. Resumen Ejecutivo

### 1.1 Descripción del Producto
**API Móvil** es un sistema de backend que permite consultar y almacenar información sobre operadores telefónicos de números móviles españoles. El sistema realiza scraping automatizado del portal de Digimobil para obtener el operador actual de cada número telefónico.

### 1.2 Propósito
Permitir a usuarios procesar archivos masivos de números telefónicos para identificar el operador de cada línea, facilitando campañas de portabilidad y análisis de mercado.

### 1.3 Stack Tecnológico
| Componente | Tecnología |
|------------|------------|
| Backend | Django 4.x + Django REST Framework |
| Cola de Tareas | Celery 5.x + Redis |
| Base de Datos | PostgreSQL |
| Caché | Redis |
| Proxies | LunaProxy (SOCKS5) |
| Servidor Web | Daphne (ASGI) |
| Process Manager | Supervisor |
| Contenedores | Docker (opcional) |

---

## 2. Arquitectura del Sistema

### 2.1 Diagrama de Componentes
```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│                    (Aplicación Web/Móvil)                           │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API REST (Django)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  /process/  │  │  /consult/  │  │/filter_data/│  │  /pause/   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│   Redis Cache     │ │   PostgreSQL    │ │      Celery Workers     │
│  (phone:number)   │ │   (Movil, etc)  │ │   (8 workers paralelos) │
└───────────────────┘ └─────────────────┘ └─────────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │   DigiPhone Class   │
                                          │  (Web Scraping)     │
                                          └─────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │   LunaProxy Pool    │
                                          │   (SOCKS5 Proxies)  │
                                          └─────────────────────┘
                                                    │
                                                    ▼
                                          ┌─────────────────────┐
                                          │ store-backend       │
                                          │ .digimobil.es       │
                                          └─────────────────────┘
```

### 2.2 Sistema de Colas por Usuario
```
┌─────────────────────────────────────────────────────────────────────┐
│                     CELERY QUEUE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Usuario A ──► user_queue_187 ──┐                                  │
│                                   │                                  │
│   Usuario B ──► user_queue_243 ──┼──► Celery Workers (round-robin)  │
│                                   │     (8 procesos paralelos)       │
│   Usuario C ──► user_queue_260 ──┘                                  │
│                                                                      │
│   Tareas auxiliares ──► celery (cola default)                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Modelos de Datos

### 3.1 Consecutive (Progreso de Archivos)
```python
class Consecutive:
    id: int (PK)
    active: bool           # Si el archivo está siendo procesado
    finish: datetime       # Fecha/hora de finalización
    file: str(150)         # Nombre del archivo
    total: int             # Total de números a procesar
    progres: int           # Números ya procesados
    created: datetime      # Fecha de creación
    num: str(50)           # Identificador consecutivo
    user: FK(User)         # Usuario propietario
    
    # Propiedades calculadas:
    @property status       # 'completed', 'processing', 'paused', 'pending'
    @property progress_percentage  # Porcentaje de avance
```

### 3.2 Movil (Registros de Números)
```python
class Movil:
    id: int (PK)
    file: str(100)         # Nombre del archivo origen
    number: str(50)        # Número telefónico (indexado)
    operator: str(150)     # Operador identificado
    user: FK(User)         # Usuario que procesó
    ip: str(150)           # Fuente: 'cache', 'database', 'scraping'
    fecha_hora: datetime   # Fecha/hora de registro (indexado)
```

### 3.3 Proxy (Configuración de Proxies)
```python
class Proxy:
    id: int (PK)
    ip: str(150)           # IP del servidor proxy
    port_min: str(10)      # Puerto mínimo
    port_max: str(10)      # Puerto máximo
    username: TextField    # Usuarios (múltiples líneas)
    password: str(100)     # Contraseña
    used: bool             # Si está en uso
    user: FK(User)         # Usuario asignado
```

### 3.4 BlockIp (IPs Bloqueadas)
```python
class BlockIp:
    id: int (PK)
    ip_block: str(150)     # IP bloqueada
    proxy_ip: FK(Proxy)    # Proxy asociado
    user: FK(User)         # Usuario afectado
    reintent: int          # Contador de reintentos
```

---

## 4. API Endpoints

### 4.1 POST /process/
**Descripción:** Inicia el procesamiento de un archivo de números telefónicos.

**Request Body:**
```json
{
    "user": "nombre_usuario",
    "file": "archivo.xlsx",
    "number": ["600123456", "600123457", ...],
    "reprocess": false
}
```

**Response:**
```json
{
    "code": 200,
    "status": "OK",
    "message": "Proceso activado."
}
```

**Flujo:**
1. Valida usuario (crea si no existe)
2. Verifica procesos activos del usuario
3. Crea/reanuda registro Consecutive
4. Identifica números pendientes (no procesados)
5. Encola tareas en cola del usuario (`user_queue_{user_id}`)
6. Retorna confirmación

---

### 4.2 POST /consult/
**Descripción:** Obtiene el detalle y resultados de un archivo procesado.

**Request Body:**
```json
{
    "user": "nombre_usuario",
    "id": 123
}
```

**Response:**
```json
{
    "code": 200,
    "status": "OK",
    "message": "Proceso pausado",
    "nameFile": "archivo.xlsx",
    "data": {
        "total": 5000,
        "proces": 2500,
        "subido": 3000,
        "list": [
            {"number": "600123456", "operator": "Movistar"},
            {"number": "600123457", "operator": "Vodafone"}
        ]
    }
}
```

---

### 4.3 POST /filter_data/
**Descripción:** Lista todos los archivos/procesos de un usuario con su estado.

**Request Body:**
```json
{
    "user": "nombre_usuario"
}
```

**Response:**
```json
{
    "data": [
        {
            "id": 123,
            "file": "archivo.xlsx",
            "total": 3000,
            "progres": 2500,
            "conse": "001",
            "created": "2026-01-06T10:30:00Z",
            "finish": null,
            "active": true,
            "status": "processing",
            "status_display": "Procesando",
            "progress_percentage": 83.33
        }
    ]
}
```

---

### 4.4 POST /pause/
**Descripción:** Pausa el procesamiento de un archivo.

**Request Body:**
```json
{
    "user": "nombre_usuario",
    "file": "archivo.xlsx"
}
```

**Response:**
```json
{
    "code": 200,
    "status": "OK",
    "message": "Proceso pausado"
}
```

---

### 4.5 POST /remove/
**Descripción:** Elimina un proceso/archivo del sistema.

**Request Body:**
```json
{
    "user": "nombre_usuario",
    "id": 123
}
```

**Response:**
```json
{
    "code": 200,
    "status": "OK",
    "message": "Base eliminada correctamente"
}
```

---

### 4.6 POST /phone/consult/
**Descripción:** Consulta individual de un número telefónico.

**Request Body:**
```json
{
    "user": "nombre_usuario",
    "phone": "600123456"
}
```

**Response:**
```json
{
    "data": [200, {
        "name": "Movistar",
        "tradeName": "Movistar",
        "operatorId": "12"
    }]
}
```

---

## 5. Tareas Celery

### 5.1 scrape_and_save_phone_task
**Tipo:** Tarea principal de scraping  
**Cola:** `user_queue_{user_id}`  
**Reintentos:** 3 con backoff exponencial

**Flujo:**
1. Verifica caché Redis (`phone:{number}`)
2. Verifica BD PostgreSQL (últimos 30 días)
3. Si no existe → Scraping con DigiPhone
4. Hasta 3 intentos con diferentes proxies
5. Guarda en BD y actualiza caché
6. Actualiza progreso del archivo

**Operadores válidos:**
- Movistar, Vodafone, Orange, Mas Movil, Yoigo
- DIGI SPAIN TELECOM, S.L. (cuando 404 "Operator not found")

**Operadores inválidos (NO se guardan):**
- `No existe`, `Desconocido`, `ERROR_SCRAPING`, `""`

---

### 5.2 process_file_in_batches
**Tipo:** Procesamiento en lotes  
**Cola:** `user_queue_{user_id}`

Procesa un archivo en lotes de 100 números, encolando cada número como tarea individual.

---

### 5.3 sync_progress_with_movil
**Tipo:** Tarea periódica (beat)  
**Frecuencia:** Cada 30 segundos

Sincroniza `Consecutive.progres` con el conteo real de `Movil` para mantener consistencia.

---

### 5.4 check_and_requeue_orphan_files
**Tipo:** Tarea periódica (beat)  
**Frecuencia:** Cada 60 segundos

Detecta archivos "huérfanos" (activos sin tareas en cola) y los re-encola automáticamente.

---

### 5.5 update_progress_directly
**Tipo:** Función síncrona (no tarea)

Actualiza el progreso directamente en BD sin usar cola de tareas para actualizaciones en tiempo real.

---

## 6. Sistema de Scraping (DigiPhone)

### 6.1 Flujo de Autenticación
```
1. GET www.digimobil.es/ → Obtener cookies de sesión
2. POST store-backend.digimobil.es/v2/login/online → Obtener store_access_token
3. GET store-backend.digimobil.es/v2/operators/by-line-code/{phone}
```

### 6.2 Circuit Breaker de Proxies
- **Errores SSL máximos por proxy:** 5
- **Errores de conexión máximos:** 5
- **Cooldown:** 300 segundos (5 minutos)
- **Rotación automática** cuando se detectan errores consecutivos

### 6.3 Configuración de Proxies
```
Proveedor: LunaProxy
Protocolo: SOCKS5
Host: eu.5j81o23u.lunaproxy.net
Puerto: 12233
Formato usuario: user-{id}-region-es-sessid-{session}-sesstime-10
```

---

## 7. Sistema de Caché

### 7.1 Estructura de Caché Redis
```
Clave: phone:{numero}
Valor: {operador}
TTL: 30 días (2592000 segundos)
```

### 7.2 Flujo de Consulta Optimizado
```
1. Buscar en caché Redis (~1ms) ⚡
   └─ HIT → Retornar operador
   └─ MISS → Continuar

2. Buscar en PostgreSQL (~10ms)
   └─ HIT → Agregar a caché + Retornar
   └─ MISS → Continuar

3. Scraping con DigiPhone (~3-15s)
   └─ Éxito → Guardar en BD + Caché + Retornar
   └─ Fallo → Marcar progreso + Continuar siguiente
```

---

## 8. Configuración de Workers

### 8.1 Supervisor - Celery Worker
```ini
[program:celery_worker]
command=/opt/apimovil/venv/bin/celery -A apimovil worker 
        -l info 
        --concurrency=8 
        -Q celery,user_queue_1,user_queue_2,...,user_queue_300
numprocs=1
autostart=true
autorestart=true
```

### 8.2 Supervisor - Celery Beat
```ini
[program:celery_beat]
command=/opt/apimovil/venv/bin/celery -A apimovil beat -l info
numprocs=1
autostart=true
autorestart=true
```

### 8.3 Supervisor - Daphne (ASGI)
```ini
[program:daphne]
command=/opt/apimovil/venv/bin/daphne -b 0.0.0.0 -p 8800 apimovil.asgi:application
numprocs=1
autostart=true
autorestart=true
```

---

## 9. Funcionalidades Clave

### 9.1 ✅ Implementadas

| Funcionalidad | Descripción |
|---------------|-------------|
| **Procesamiento Paralelo por Usuario** | Cada usuario tiene su propia cola, permitiendo procesamiento simultáneo |
| **Caché Redis de 30 días** | Números consultados se cachean para evitar scraping repetido |
| **Rotación Automática de Proxies** | Cambio de proxy después de errores SSL/conexión |
| **Circuit Breaker** | Desactiva proxies con muchos errores por 5 minutos |
| **Actualización de Progreso en Tiempo Real** | Progreso se actualiza directamente sin cola |
| **Auto-recuperación de Archivos Huérfanos** | Tareas periódicas re-encolan archivos estancados |
| **Sincronización de Progreso** | Cada 30s se sincroniza progreso con BD |
| **Reintentos con Backoff Exponencial** | Tareas fallidas se reintentan automáticamente |
| **No Guardar Operadores Inválidos** | Solo se guardan resultados válidos |

### 9.2 🔄 Estados de Archivo
| Estado | Condición | Descripción |
|--------|-----------|-------------|
| `pending` | progres=0, active=false | Archivo cargado, sin procesar |
| `processing` | active=true | En procesamiento activo |
| `paused` | progres>0, active=false | Pausado manualmente |
| `completed` | progres>=total | Procesamiento terminado |

---

## 10. Métricas y Monitoreo

### 10.1 Logs
- **Ubicación:** `/var/log/celery/` (Supervisor)
- **Formato:** `%(asctime)s [%(levelname)s] %(message)s`
- **Rotación:** 10 archivos de backup

### 10.2 Indicadores Clave
```python
# Tareas en cola
redis-cli LLEN user_queue_{user_id}
redis-cli LLEN celery

# Progreso de archivo
Consecutive.objects.get(id=X).progres / Consecutive.objects.get(id=X).total

# Hit rate de caché
(cache_hits / total_queries) * 100
```

---

## 11. Seguridad

### 11.1 Consideraciones
- Usuarios se crean automáticamente (sin autenticación explícita)
- Proxies asignados por usuario
- Sin rate limiting implementado
- Conexiones SOCKS5 encriptadas

### 11.2 Recomendaciones Futuras
- [ ] Implementar autenticación JWT
- [ ] Rate limiting por usuario/IP
- [ ] Encriptación de credenciales de proxy
- [ ] Auditoría de accesos

---

## 12. Deployment

### 12.1 Requisitos del Sistema
- **OS:** Ubuntu 20.04+
- **Python:** 3.11+
- **RAM:** 4GB mínimo (8GB recomendado)
- **CPU:** 4 cores mínimo
- **Almacenamiento:** 50GB SSD

### 12.2 Servicios Requeridos
```bash
# PostgreSQL
sudo systemctl status postgresql

# Redis
sudo systemctl status redis

# Supervisor (Celery + Daphne)
sudo supervisorctl status all
```

### 12.3 Comandos Útiles
```bash
# Reiniciar workers
sudo supervisorctl restart celery_worker celery_beat

# Ver logs en tiempo real
sudo supervisorctl tail -f celery_worker stderr

# Verificar colas
redis-cli LLEN celery
redis-cli KEYS "user_queue_*" | head -20

# Estado de archivos activos
python manage.py shell -c "
from app.models import Consecutive
for c in Consecutive.objects.filter(active=True):
    print(f'{c.file}: {c.progres}/{c.total}')
"
```

---

## 13. Roadmap Futuro

### 13.1 Próximas Mejoras
- [ ] Dashboard de monitoreo en tiempo real
- [ ] WebSocket para actualizaciones push al frontend
- [ ] API para gestión de proxies
- [ ] Exportación de resultados a CSV/Excel
- [ ] Integración con otros proveedores de portabilidad
- [ ] Balanceador de carga para múltiples workers

### 13.2 Optimizaciones Pendientes
- [ ] Compresión de caché para números similares
- [ ] Batch inserts para mejor rendimiento de BD
- [ ] Connection pooling avanzado
- [ ] Métricas con Prometheus/Grafana

---

## 14. Contacto y Soporte

**Repositorio:** https://github.com/jesus-bazan-entel/apimovil  
**Rama Principal:** main  

---

*Documento generado automáticamente - Enero 2026*
