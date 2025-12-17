from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .views import *

urlpatterns = [
    #path('apimovil/process/', process, name="process"),
    #path('apimovil/consult/', consult, name="consult"),
    #path('apimovil/filter_data/', filter_data, name="filter_data"),
    #path('apimovil/pause/', pause, name="pause"),
    #path('apimovil/remove/', remove, name="remove"),
    path('process/', process, name="process"),
    path('consult/', consult, name="consult"),
    path('filter_data/', filter_data, name="filter_data"),
    path('pause/', pause, name="pause"),
    path('remove/', remove, name="remove"),
    path('phone/consult/', phone_consult, name="phone_consult"),
]