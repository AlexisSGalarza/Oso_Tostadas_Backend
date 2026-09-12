from rest_framework import generics, permissions

from apps.empleados.permissions import TieneEmpleadoActivo

from .models import ProductoSucursal
from .serializers import ProductoSucursalSerializer


class ProductosDisponiblesView(generics.ListAPIView):
    """GET /api/productos/ - catalogo con stock de la sucursal del empleado autenticado."""

    serializer_class = ProductoSucursalSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get_queryset(self):
        empleado = self.request.user.empleado
        return (
            ProductoSucursal.objects.select_related('producto')
            .filter(sucursal=empleado.sucursal, producto__estado='activo')
            .order_by('producto__nombre')
        )
