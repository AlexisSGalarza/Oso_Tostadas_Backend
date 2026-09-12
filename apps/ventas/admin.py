from django.contrib import admin

from .models import Devolucion, MovimientoCaja, Pago, Turno, Venta

# Los modelos con clave primaria compuesta (DetalleVenta, DevolucionDetalle)
# todavia no son soportados por el admin de Django (ImproperlyConfigured),
# por lo que se administran via la API/shell en lugar del admin site.

admin.site.register(Turno)
admin.site.register(MovimientoCaja)
admin.site.register(Venta)
admin.site.register(Pago)
admin.site.register(Devolucion)
