from rest_framework import generics, permissions

from apps.empleados.permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido

from .models import RegistroAuditoria
from .serializers import RegistroAuditoriaSerializer


class RegistroAuditoriaListView(generics.ListAPIView):
    """GET /api/auditoria/ - ultimas acciones administrativas de tu sucursal."""

    serializer_class = RegistroAuditoriaSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo, rol_requerido(*ROLES_SUPERVISOR)]

    def get_queryset(self):
        sucursal = self.request.user.empleado.sucursal
        return (
            RegistroAuditoria.objects.select_related('actor')
            .filter(actor__sucursal=sucursal)
            .order_by('-creado_en')[:200]
        )
