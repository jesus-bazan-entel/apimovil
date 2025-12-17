from django.contrib import admin
from .models import *
# Register your models here.
class MovilAdmin(admin.ModelAdmin):
    search_fields = ["id", "number", "operator"]

class ConseAdmin(admin.ModelAdmin):
    search_fields = ["id"]

class ProxyAdmin(admin.ModelAdmin):
    search_fields = ["id", "ip"]

class BlockIpAdmin(admin.ModelAdmin):
    search_fields = ["id"]

admin.site.register(Movil, MovilAdmin)
admin.site.register(Consecutive, ConseAdmin)
admin.site.register(Proxy, ProxyAdmin)
admin.site.register(BlockIp, BlockIpAdmin)