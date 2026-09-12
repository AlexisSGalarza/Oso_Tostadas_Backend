from django.contrib.auth import authenticate
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Empleado


class EmpleadoMeSerializer(serializers.ModelSerializer):
    rol = serializers.CharField(source='rol.nombre_rol', read_only=True)
    id_sucursal = serializers.IntegerField(source='sucursal_id', read_only=True)
    sucursal = serializers.CharField(source='sucursal.nombre', read_only=True)

    class Meta:
        model = Empleado
        fields = ['id_empleado', 'nombre', 'correo', 'rol', 'id_sucursal', 'sucursal', 'estado']


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        'no_active_account': 'Correo o contraseña incorrectos.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reemplaza el campo 'username' por defecto con 'correo'.
        self.fields.pop(self.username_field, None)
        self.fields['correo'] = serializers.EmailField()

    def validate(self, attrs):
        correo = attrs['correo'].strip().lower()
        password = attrs['password']
        user = authenticate(
            request=self.context.get('request'),
            username=correo,
            password=password,
        )
        empleado = getattr(user, 'empleado', None) if user else None
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
