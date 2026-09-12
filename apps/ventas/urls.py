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
    path('ventas/<int:id_venta>/recibo/', views.ReciboVentaView.as_view(), name='venta-recibo'),
    path('reportes/semana/', views.ReporteSemanaView.as_view(), name='reporte-semana'),
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/turnos/<int:id_turno>/', views.AdminTurnoDetalleView.as_view(), name='admin-turno-detalle'),
]
