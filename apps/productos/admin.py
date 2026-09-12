from django.contrib import admin

from .models import Insumo, Producto, Proveedor

# Los modelos con clave primaria compuesta (ProductoSucursal, InsumoSucursal,
# ProductoInsumo, ProveedorInsumo) todavia no son soportados por el admin de
# Django (ImproperlyConfigured), por lo que se administran via la API/shell
# en lugar del admin site.

admin.site.register(Producto)
admin.site.register(Insumo)
admin.site.register(Proveedor)
