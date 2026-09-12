from django.urls import path

from . import views

urlpatterns = [
    path('sucursales/mia/', views.SucursalMiaView.as_view(), name='sucursal-mia'),
]
