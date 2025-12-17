from django.db import models
from django.contrib.auth.models import User
# Create your models here.
from django.utils import timezone 

class Consecutive(models.Model):
    active = models.BooleanField(default=True)
    finish = models.BooleanField(default=False)
    file = models.CharField(max_length=150, null=True, blank=True)
    total = models.IntegerField(default=0)
    progres = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    num = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return str(self.file)+" | "+str(self.user)

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
