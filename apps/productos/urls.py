from django.urls import path

from . import views

urlpatterns = [
    path('productos/', views.ProductosDisponiblesView.as_view(), name='productos-disponibles'),
]
