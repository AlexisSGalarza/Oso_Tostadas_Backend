from rest_framework import serializers

from .models import ProductoSucursal


class ProductoSucursalSerializer(serializers.ModelSerializer):
    id_producto = serializers.IntegerField(source='producto_id', read_only=True)
    nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio = serializers.FloatField(source='producto.precio', read_only=True)

    class Meta:
        model = ProductoSucursal
        fields = ['id_producto', 'nombre', 'precio', 'stock']
