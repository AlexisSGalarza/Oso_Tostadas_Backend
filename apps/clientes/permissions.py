from rest_framework.permissions import BasePermission


class EsCliente(BasePermission):
    message = 'Esta sección es solo para cuentas de cliente.'

    def has_permission(self, request, view):
        return getattr(request.user, 'cliente', None) is not None
