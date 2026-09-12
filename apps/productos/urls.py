from django.urls import path

from . import views

urlpatterns = [
    path('productos/', views.ProductosDisponiblesView.as_view(), name='productos-disponibles'),
    path('admin/productos/', views.ProductoAdminListView.as_view(), name='admin-productos'),
    path(
        'admin/productos/<int:id_producto>/produccion/',
        views.ProductoProduccionView.as_view(),
        name='admin-producto-produccion',
    ),
    path('admin/insumos/', views.InsumoAdminListView.as_view(), name='admin-insumos'),
    path('admin/insumos/<int:id_insumo>/entrada/', views.InsumoEntradaView.as_view(), name='admin-insumo-entrada'),
    path('proveedores/', views.ProveedorListCreateView.as_view(), name='proveedores'),
    path(
        'proveedores/<int:id_proveedor>/alternar-estado/',
        views.ProveedorEstadoView.as_view(),
        name='proveedor-alternar-estado',
    ),
]
