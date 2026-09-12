from django.contrib import admin

from .models import (
    Devolucion,
    Empleado,
    Insumo,
    MovimientoCaja,
    Pago,
    Producto,
    Proveedor,
    Rol,
    Sucursal,
    Turno,
    Venta,
)

# Los modelos con clave primaria compuesta (DetalleVenta, ProductoSucursal,
# InsumoSucursal, ProductoInsumo, ProveedorInsumo, DevolucionDetalle) todavia
# no son soportados por el admin de Django (ImproperlyConfigured), por lo que
# se administran via la API/shell en lugar del admin site.

admin.site.register(Sucursal)
admin.site.register(Rol)
admin.site.register(Empleado)
admin.site.register(Turno)
admin.site.register(MovimientoCaja)
admin.site.register(Producto)
admin.site.register(Venta)
admin.site.register(Insumo)
admin.site.register(Proveedor)
admin.site.register(Pago)
admin.site.register(Devolucion)
