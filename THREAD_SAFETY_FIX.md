# Fix de Concurrencia - views.py

## Problema Identificado

**Error**: `KeyError: 'GCCDianaramirez'` en múltiples threads

### Causa Raíz

Race condition en la función `worker()` cuando no hay proxies disponibles:

```python
def worker(q, events, _thread, user, reprocess):
    digiPhone = DigiPhone(user, reprocess)
    if digiPhone._len_proxy > 0:
        # Procesar tareas...
    else:
        del QUEUE_USER[user.username]  # PROBLEMA: Múltiples threads ejecutan esto
```

**Flujo del problema**:
1. Se crean 4 threads en `addUserWithQueue()` (línea 357)
2. Todos ejecutan `worker()` simultáneamente
3. Todos detectan que no hay proxies (`digiPhone._len_proxy == 0`)
4. Todos entran al bloque `else` (línea 340)
5. Todos intentan ejecutar `del QUEUE_USER[user.username]`
6. El primer thread lo ejecuta exitosamente
7. Los otros 3 threads fallan con `KeyError` porque la clave ya fue eliminada

### Escenario

```
Thread-3: verifica no hay proxies → ejecuta del QUEUE_USER['GCCDianaramirez'] ✓
Thread-4: verifica no hay proxies → intenta del QUEUE_USER['GCCDianaramirez'] ✗ KeyError
Thread-5: verifica no hay proxies → intenta del QUEUE_USER['GCCDianaramirez'] ✗ KeyError
```

## Solución Implementada

### 1. Agregar Lock Global

```python
QUEUE_USER = {}
QUEUE_USER_LOCK = threading.Lock()  # Lock para proteger acceso concurrente
```

### 2. Proteger Eliminación de Clave

**Antes (línea 340)**:
```python
else:
    del QUEUE_USER[user.username]  # ✗ No thread-safe
```

**Después (líneas 341-344)**:
```python
else:
    # Thread-safe: usar pop() en lugar de del para evitar KeyError
    with QUEUE_USER_LOCK:
        QUEUE_USER.pop(user.username, None)
```

**Beneficios**:
- `pop(key, None)` no lanza KeyError si la clave no existe
- El lock `QUEUE_USER_LOCK` garantiza que solo un thread accede al diccionario a la vez
- Elimina completamente el race condition

### 3. Proteger Creación de Colas

**Antes (línea 349)**:
```python
def addUserWithQueue(user, reprocess):
    if user.username not in list(QUEUE_USER.keys()):  # ✗ No thread-safe
        QUEUE_USER[user.username] = {...}
```

**Después (líneas 350-360)**:
```python
def addUserWithQueue(user, reprocess):
    with QUEUE_USER_LOCK:
        if user.username not in QUEUE_USER:
            QUEUE_USER[user.username] = {...}
```

**Beneficios**:
- Previene que múltiples requests creen workers duplicados para el mismo usuario
- Garantiza atomicidad en el check-and-create

## Archivos Modificados

- `app/views.py`:
  - Línea 173: Agregado `QUEUE_USER_LOCK = threading.Lock()`
  - Líneas 341-344: Modificado para usar `pop()` con lock
  - Líneas 350-360: Agregado lock en `addUserWithQueue()`

## Testing

### Antes del Fix

```
Exception in thread Thread-3 (worker):
KeyError: 'GCCDianaramirez'

Exception in thread Thread-4 (worker):
KeyError: 'GCCDianaramirez'

Exception in thread Thread-5 (worker):
KeyError: 'GCCDianaramirez'
```

### Después del Fix

- ✓ No más KeyError
- ✓ Solo un thread elimina la clave exitosamente
- ✓ Los otros threads no lanzan excepción (pop retorna None)
- ✓ Thread-safe garantizado por el lock

## Conceptos de Thread Safety

### Race Condition

Una **race condition** ocurre cuando múltiples threads acceden a un recurso compartido simultáneamente, y el resultado depende del orden de ejecución.

### Lock (Mutex)

Un **lock** (o mutex) es un mecanismo de sincronización que garantiza que solo un thread puede acceder a un recurso a la vez.

```python
with QUEUE_USER_LOCK:
    # Solo un thread puede estar aquí a la vez
    QUEUE_USER.pop(user.username, None)
```

### Operaciones Atómicas

`.pop(key, default)` con lock es una operación atómica que:
1. Verifica si la clave existe
2. Elimina la clave si existe
3. Retorna None si no existe (sin lanzar excepción)

## Recomendaciones Futuras

1. **Usar lock en todos los accesos a QUEUE_USER** que modifican el diccionario
2. **Considerar usar `threading.RLock()`** si necesitas locks reentrantes
3. **Agregar logging de thread ID** para debugging:
   ```python
   logging.info(f"Thread {threading.current_thread().name} eliminó usuario {user.username}")
   ```
4. **Considerar usar `collections.defaultdict`** o estructuras thread-safe como `queue.Queue`

## Referencias

- [Threading — Thread-based parallelism (Python Docs)](https://docs.python.org/3/library/threading.html)
- [Thread Synchronization Mechanisms](https://docs.python.org/3/library/threading.html#lock-objects)
