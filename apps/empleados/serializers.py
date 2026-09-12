from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Empleado, Rol


class EmpleadoMeSerializer(serializers.ModelSerializer):
    rol = serializers.CharField(source='rol.nombre_rol', read_only=True)
    id_sucursal = serializers.IntegerField(source='sucursal_id', read_only=True)
    sucursal = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Empleado
        fields = [
            'id_empleado', 'numero_empleado', 'nombre', 'correo', 'rol',
            'id_sucursal', 'sucursal', 'estado',
        ]


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id_rol', 'nombre_rol']


class EmpleadoAdminSerializer(serializers.ModelSerializer):
    rol = serializers.CharField(source='rol.nombre_rol', read_only=True)
    id_rol = serializers.IntegerField(source='rol_id', read_only=True)

    class Meta:
        model = Empleado
        fields = [
            'id_empleado', 'numero_empleado', 'nombre', 'correo', 'telefono', 'fecha_ingreso',
            'estado', 'rol', 'id_rol', 'horario_dias', 'horario_hora_inicio', 'horario_hora_fin',
        ]
        read_only_fields = fields


class EmpleadoHorarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empleado
        fields = ['horario_dias', 'horario_hora_inicio', 'horario_hora_fin']


class EmpleadoCreateSerializer(serializers.ModelSerializer):
    id_rol = serializers.PrimaryKeyRelatedField(source='rol', queryset=Rol.objects.all())
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Empleado
        fields = ['nombre', 'correo', 'telefono', 'id_rol', 'password']

    def validate_correo(self, value):
        correo = value.strip().lower()
        if Empleado.objects.filter(correo=correo).exists():
            raise serializers.ValidationError('Ya existe un empleado con ese correo.')
        return correo

    def validate_password(self, value):
        if not value:
            return value
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        'no_active_account': 'Número de empleado o contraseña incorrectos.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reemplaza el campo 'username' por defecto con 'numero_empleado'.
        self.fields.pop(self.username_field, None)
        self.fields['numero_empleado'] = serializers.CharField()

    def validate(self, attrs):
        numero_empleado = attrs['numero_empleado'].strip()
        password = attrs['password']

        empleado = Empleado.objects.select_related('usuario').filter(numero_empleado=numero_empleado).first()
        user = None
        if empleado is not None and empleado.usuario is not None:
            user = authenticate(
                request=self.context.get('request'),
                username=empleado.usuario.username,
                password=password,
            )
        if user is None or empleado is None or empleado.estado != 'activo':
            raise exceptions.AuthenticationFailed(
                self.error_messages['no_active_account'], 'no_active_account'
            )

        self.user = user
        refresh = self.get_token(self.user)
        return {'refresh': str(refresh), 'access': str(refresh.access_token)}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        empleado = user.empleado
        token['id_empleado'] = empleado.id_empleado
        token['nombre'] = empleado.nombre
        token['rol'] = empleado.rol.nombre_rol
        token['id_sucursal'] = empleado.sucursal_id
        return token
