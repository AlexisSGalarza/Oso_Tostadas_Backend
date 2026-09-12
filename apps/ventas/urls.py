from django.urls import path

from . import views

urlpatterns = [
    path('turnos/actual/', views.TurnoActualView.as_view(), name='turno-actual'),
    path('turnos/abrir/', views.AbrirTurnoView.as_view(), name='turno-abrir'),
    path('turnos/cerrar/', views.CerrarTurnoView.as_view(), name='turno-cerrar'),
    path('ventas/', views.VentaCreateView.as_view(), name='venta-crear'),
    path('ventas/<int:pk>/', views.VentaDetailView.as_view(), name='venta-detalle'),
    path('ventas/<int:id_venta>/pagos/', views.PagoCreateView.as_view(), name='venta-pago'),
    path('ventas/<int:id_venta>/devoluciones/', views.DevolucionCreateView.as_view(), name='venta-devolucion'),
]
