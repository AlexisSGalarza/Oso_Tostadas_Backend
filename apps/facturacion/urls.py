from django.urls import path, re_path

from . import views

urlpatterns = [
    path('publico/tickets/<int:folio>/', views.TicketPublicoView.as_view(), name='publico-ticket'),
    path('publico/tickets/<int:id_venta>/factura/', views.FacturaPublicaView.as_view(), name='publico-factura'),
    re_path(
        r'^publico/facturas/(?P<folio_fiscal>[0-9a-fA-F-]{36})/(?P<formato>pdf|xml)/$',
        views.FacturaArchivoView.as_view(),
        name='publico-factura-archivo',
    ),
    path('facturacion/ventas/', views.VentasPorFacturarView.as_view(), name='facturacion-ventas'),
    path(
        'facturacion/ventas/<int:id_venta>/factura/',
        views.FacturarVentaView.as_view(),
        name='facturacion-venta-factura',
    ),
    path('admin/facturas/', views.FacturasAdminView.as_view(), name='admin-facturas'),
]
