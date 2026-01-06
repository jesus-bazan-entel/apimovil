from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        """
        Se ejecuta cuando Django carga la aplicación.
        Importa las señales y carga el caché inicial.
        """
        # Importar la función de carga de caché
        from app.signals import load_phone_cache_on_startup
        
        # Cargar el caché al iniciar (tanto Gunicorn como Daphne)
        load_phone_cache_on_startup()
