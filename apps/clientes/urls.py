from django.urls import path

from . import views

urlpatterns = [
    path('clientes/registro/', views.RegistroClienteView.as_view(), name='cliente-registro'),
    path('clientes/login/', views.LoginClienteView.as_view(), name='cliente-login'),
    path('clientes/me/', views.ClienteMeView.as_view(), name='cliente-me'),
    path('clientes/tickets/', views.TicketsClienteView.as_view(), name='cliente-tickets'),
    path(
        'clientes/tickets/<int:id_venta>/factura/',
        views.FacturarTicketClienteView.as_view(),
        name='cliente-ticket-factura',
    ),
]
