from rest_framework.permissions import BasePermission


class TieneEmpleadoActivo(BasePermission):
    message = 'Tu cuenta de empleado no existe o esta inactiva.'

    def has_permission(self, request, view):
        empleado = getattr(request.user, 'empleado', None)
        return empleado is not None and empleado.estado == 'activo'


def rol_requerido(*roles_permitidos):
    """Fabrica una clase de permiso que exige que el empleado tenga uno de los roles dados."""
    roles_lower = {r.lower() for r in roles_permitidos}

    class _RolRequerido(BasePermission):
        message = f"Se requiere uno de estos roles: {', '.join(roles_permitidos)}."

        def has_permission(self, request, view):
            empleado = getattr(request.user, 'empleado', None)
            return bool(empleado) and empleado.rol.nombre_rol.lower() in roles_lower

    return _RolRequerido
