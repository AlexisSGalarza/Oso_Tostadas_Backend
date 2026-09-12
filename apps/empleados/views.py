from datetime import date

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auditoria.models import registrar as registrar_auditoria

from .models import Empleado, Rol
from .permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido
from .serializers import (
    EmpleadoAdminSerializer,
    EmpleadoCreateSerializer,
    EmpleadoHorarioSerializer,
    EmpleadoMeSerializer,
    LoginSerializer,
    RolSerializer,
)

PASSWORD_ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
NUMERO_EMPLEADO_BASE = 800001


def generar_password_temporal():
    return get_random_string(10, allowed_chars=PASSWORD_ALFABETO)


def generar_numero_empleado():
    """Siguiente numero de empleado consecutivo, ej. 800001, 800002, ..."""
    existentes = [
        int(n) for n in Empleado.objects.exclude(numero_empleado__isnull=True).values_list(
            'numero_empleado', flat=True
        ) if n.isdigit()
    ]
    siguiente = max(existentes) + 1 if existentes else NUMERO_EMPLEADO_BASE
    return str(siguiente)


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ {correo, password} -> {access, refresh}."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get(self, request):
        return Response(EmpleadoMeSerializer(request.user.empleado).data)


class RolListView(generics.ListAPIView):
    """GET /api/roles/ - catalogo de roles para asignar a un empleado."""

    serializer_class = RolSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]
    queryset = Rol.objects.all().order_by('nombre_rol')


class EmpleadoListCreateView(generics.ListCreateAPIView):
    """GET /api/empleados/ lista el personal de tu sucursal. POST crea uno nuevo con cuenta de acceso."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_SUPERVISOR),
    ]

    def get_queryset(self):
        sucursal = self.request.user.empleado.sucursal
        return Empleado.objects.filter(sucursal=sucursal).select_related('rol').order_by('nombre')

    def get_serializer_class(self):
        return EmpleadoCreateSerializer if self.request.method == 'POST' else EmpleadoAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password_elegida = serializer.validated_data.pop('password', '') or ''
        empleado = serializer.save(
            sucursal=request.user.empleado.sucursal,
            fecha_ingreso=date.today(),
            numero_empleado=generar_numero_empleado(),
        )

        password = password_elegida or generar_password_temporal()
        User = get_user_model()
        user = User.objects.create_user(username=empleado.correo, email=empleado.correo, password=password)
        empleado.usuario = user
        empleado.save(update_fields=['usuario'])

        registrar_auditoria(
            request.user.empleado, 'empleado.crear',
            f'Creo al empleado {empleado.nombre} (No. {empleado.numero_empleado}, rol {empleado.rol.nombre_rol}).',
        )

        data = EmpleadoAdminSerializer(empleado).data
        # solo se devuelve si el backend la genero; si el admin la eligio, ya la sabe.
        if not password_elegida:
            data['password_temporal'] = password
        return Response(data, status=status.HTTP_201_CREATED)


class EmpleadoEstadoView(APIView):
    """POST /api/empleados/<id>/alternar-estado/ - activa/desactiva el acceso de un empleado de tu sucursal."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_SUPERVISOR),
    ]

    def post(self, request, id_empleado):
        empleado = get_object_or_404(
            Empleado, pk=id_empleado, sucursal=request.user.empleado.sucursal
        )
        empleado.estado = 'inactivo' if empleado.estado == 'activo' else 'activo'
        empleado.save(update_fields=['estado'])
        registrar_auditoria(
            request.user.empleado, 'empleado.alternar_estado',
            f'{"Desactivo" if empleado.estado == "inactivo" else "Reactivo"} a {empleado.nombre} '
            f'(No. {empleado.numero_empleado}).',
        )
        return Response(EmpleadoAdminSerializer(empleado).data)


class EmpleadoResetPasswordView(APIView):
    """POST /api/empleados/<id>/restablecer-password/ - genera y devuelve una contraseña temporal nueva."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_SUPERVISOR),
    ]

    def post(self, request, id_empleado):
        empleado = get_object_or_404(
            Empleado, pk=id_empleado, sucursal=request.user.empleado.sucursal
        )
        if empleado.usuario is None:
            raise ValidationError('Este empleado no tiene una cuenta de acceso todavia.')

        password = generar_password_temporal()
        empleado.usuario.set_password(password)
        empleado.usuario.save(update_fields=['password'])
        registrar_auditoria(
            request.user.empleado, 'empleado.restablecer_password',
            f'Restablecio la contraseña de {empleado.nombre} (No. {empleado.numero_empleado}).',
        )
        return Response({'password_temporal': password})


class EmpleadoHorarioView(APIView):
    """PATCH /api/empleados/<id>/horario/ - asigna el horario de trabajo de un empleado de tu sucursal."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_SUPERVISOR),
    ]

    def patch(self, request, id_empleado):
        empleado = get_object_or_404(
            Empleado, pk=id_empleado, sucursal=request.user.empleado.sucursal
        )
        serializer = EmpleadoHorarioSerializer(empleado, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        registrar_auditoria(
            request.user.empleado, 'empleado.horario',
            f'Actualizo el horario de {empleado.nombre} (No. {empleado.numero_empleado}).',
        )
        return Response(EmpleadoAdminSerializer(empleado).data)
