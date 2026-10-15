from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.facturacion.serializers import DatosFiscalesSerializer

from .models import Cliente


class RegistroClienteSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    correo = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_correo(self, valor):
        valor = valor.strip().lower()
        if Cliente.objects.filter(correo=valor).exists() or get_user_model().objects.filter(username=valor).exists():
            raise serializers.ValidationError('Ya hay una cuenta con ese correo. Inicia sesión.')
        return valor

    def validate_password(self, valor):
        validate_password(valor)
        return valor


class LoginClienteSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ClienteSerializer(serializers.ModelSerializer):
    datos_fiscales = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = ['id_cliente', 'nombre', 'correo', 'datos_fiscales']

    def get_datos_fiscales(self, cliente):
        return cliente.datos_fiscales


class AgregarTicketSerializer(serializers.Serializer):
    folio = serializers.IntegerField(min_value=1)
    total = serializers.FloatField(min_value=0)


class FacturarTicketSerializer(DatosFiscalesSerializer):
    # Si viene en true, los datos quedan guardados para la siguiente factura.
    guardar = serializers.BooleanField(required=False, default=True)
