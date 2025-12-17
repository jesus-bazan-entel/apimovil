# Usa una imagen base de Python
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /opt/apimovil

# Copia los archivos de requisitos de tu aplicación
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación
COPY . .

# Expone el puerto 8800, donde correrá el servidor de desarrollo de Django
EXPOSE 8800

# Comando para iniciar el servidor de desarrollo de Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8800"]

