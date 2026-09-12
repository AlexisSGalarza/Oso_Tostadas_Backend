from rest_framework import serializers

from .models import Sucursal


class SucursalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sucursal
        fields = [
            'id_sucursal', 'nombre', 'direccion', 'telefono', 'estado',
            'hora_apertura', 'hora_cierre', 'fondo_caja_default',
        ]
        read_only_fields = ['id_sucursal', 'estado']
