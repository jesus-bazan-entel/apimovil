import threading
import queue
import time

# Definimos una función que represente el trabajo que cada hilo realizará
def worker(q):
    while True:
        # Obtenemos una tarea de la cola
        task = q.get()
        if task is None:
            # Si la tarea es None, salimos del bucle
            break
        print(f"Processing task: {task}")
        time.sleep(3)  # Simulamos un trabajo que tarda 1 segundo
        print(f"Completed task: {task}")
        q.task_done()  # Marcamos la tarea como completada

# Creamos una cola
task_queue = queue.Queue()

# Creamos una lista para mantener los hilos
threads = []
num_worker_threads = 100

# Iniciamos los hilos
for i in range(num_worker_threads):
    thread = threading.Thread(target=worker, args=(task_queue,))
    thread.start()
    threads.append(thread)

# Añadimos tareas a la cola
for task in range(100):
    task_queue.put(task)

# Esperamos a que todas las tareas se completen
task_queue.join()

# Paramos los hilos
for i in range(num_worker_threads):
    task_queue.put(None)

# Esperamos a que todos los hilos terminen
for thread in threads:
    thread.join()

print("All tasks completed.")