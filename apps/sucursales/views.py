from rest_framework import generics, permissions

from apps.empleados.permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido

from .serializers import SucursalSerializer


class SucursalMiaView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/sucursales/mia/ - la sucursal del empleado autenticado.

    Cualquier empleado activo puede leerla (ej. para tomar el fondo de caja
    por defecto al abrir turno); solo Gerente/Admin pueden modificarla.
    """

    serializer_class = SucursalSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get_permissions(self):
        if self.request.method not in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated(), TieneEmpleadoActivo(), rol_requerido(*ROLES_SUPERVISOR)()]
        return super().get_permissions()

    def get_object(self):
        return self.request.user.empleado.sucursal
