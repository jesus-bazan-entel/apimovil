from django.db import models
from django.contrib.auth.models import User
# Create your models here.
from django.utils import timezone 

class Consecutive(models.Model):
    active = models.BooleanField(default=True)
    finish = models.DateTimeField(null=True, blank=True)
    file = models.CharField(max_length=150, null=True, blank=True)
    total = models.IntegerField(default=0)
    progres = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    num = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return str(self.file)+" | "+str(self.user)

    @property
    def status(self):
        """Retorna el estado real del proceso"""
        if self.progres >= self.total:
            return 'completed'
        elif self.active:
            return 'processing'
        elif self.progres > 0:
            return 'paused'
        else:
            return 'pending'
    
    @property
    def status_display(self):
        """Retorna el texto para mostrar en el frontend"""
        status_map = {
            'completed': 'Completado',
            'processing': 'Procesando',
            'paused': 'Pausado',
            'pending': 'Pendiente'
        }
        return status_map.get(self.status, 'Desconocido')
    
    @property
    def progress_percentage(self):
        """Retorna el porcentaje de progreso"""
        if self.total == 0:
            return 0
        return round((self.progres / self.total) * 100, 2)
    
    class Meta:
        db_table = 'app_consecutive'


class Movil(models.Model):
    file = models.CharField(max_length=100)
    number = models.CharField(max_length=50, db_index=True)
    operator = models.CharField(max_length=150)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip = models.CharField(max_length=150, null=True, blank=True)
    fecha_hora = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['number']),  # Solo índice en 'number'
        ]

    def __str__(self) -> str:
        return "File: "+str(self.file)+" | Phone: "+str(self.number) + " | Operator: "+str(self.operator) +" | IP: "+str(self.ip) + " | Fecha: " + str(self.fecha_hora)

class Proxy(models.Model):
    ip = models.CharField(max_length=150)
    port_min = models.CharField(max_length=10)
    port_max = models.CharField(max_length=10)
    username = models.TextField()
    password = models.CharField(max_length=100)
    used = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return str(self.username)+" - "+str(self.ip)+" - "+str(self.password)+" - "+str(self.user.username if self.user else "")+" - "+str(self.port_min)+" - "+str(self.port_max)

class BlockIp(models.Model):
    ip_block = models.CharField(max_length=150)
    proxy_ip = models.ForeignKey(Proxy, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reintent = models.IntegerField(default=1)

    def __str__(self):
        return str(self.ip_block)+" - "+str(self.proxy_ip.password if self.proxy_ip else "")+" - "+str(self.user.username if self.user else "")
