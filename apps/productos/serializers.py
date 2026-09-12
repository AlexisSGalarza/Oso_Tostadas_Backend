from django.db.models import F
from rest_framework import serializers

from .models import Insumo, InsumoSucursal, ProductoSucursal, Proveedor


class ProductoSucursalSerializer(serializers.ModelSerializer):
    id_producto = serializers.IntegerField(source='producto_id', read_only=True)
    nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio = serializers.FloatField(source='producto.precio', read_only=True)

    class Meta:
        model = ProductoSucursal
        fields = ['id_producto', 'nombre', 'precio', 'stock']


class ProductoAdminSerializer(serializers.ModelSerializer):
    id_producto = serializers.IntegerField(source='producto_id', read_only=True)
    nombre = serializers.CharField(source='producto.nombre', read_only=True)
    precio = serializers.FloatField(source='producto.precio', read_only=True)
    estado = serializers.CharField(source='producto.estado', read_only=True)

    class Meta:
        model = ProductoSucursal
        fields = ['id_producto', 'nombre', 'precio', 'estado', 'stock', 'stock_minimo']
        read_only_fields = fields


class ProduccionSerializer(serializers.Serializer):
    cantidad = serializers.IntegerField(min_value=1)


class InsumoAdminSerializer(serializers.ModelSerializer):
    id_insumo = serializers.IntegerField(source='insumo_id', read_only=True)
    nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    unidad_medida = serializers.CharField(source='insumo.unidad_medida', read_only=True)
    estado = serializers.CharField(source='insumo.estado', read_only=True)
    id_proveedor = serializers.IntegerField(source='insumo.proveedor_principal_id', read_only=True)
    proveedor = serializers.CharField(source='insumo.proveedor_principal.nombre', read_only=True, default=None)

    class Meta:
        model = InsumoSucursal
        fields = [
            'id_insumo', 'nombre', 'unidad_medida', 'estado',
            'stock', 'stock_minimo', 'id_proveedor', 'proveedor',
        ]
        read_only_fields = fields


class EntradaInsumoSerializer(serializers.Serializer):
    cantidad = serializers.FloatField(min_value=0.01)
    id_proveedor = serializers.PrimaryKeyRelatedField(
        source='proveedor', queryset=Proveedor.objects.all(), required=False, allow_null=True
    )


class InsumoCreateSerializer(serializers.ModelSerializer):
    id_proveedor = serializers.PrimaryKeyRelatedField(
        source='proveedor_principal', queryset=Proveedor.objects.all(), required=False, allow_null=True
    )
    stock_minimo = serializers.FloatField(write_only=True, required=False, min_value=0, default=0)
    stock_inicial = serializers.FloatField(write_only=True, required=False, min_value=0, default=0)

    class Meta:
        model = Insumo
        fields = ['nombre', 'unidad_medida', 'id_proveedor', 'stock_minimo', 'stock_inicial']


class ProveedorSerializer(serializers.ModelSerializer):
    urgente = serializers.SerializerMethodField()

    class Meta:
        model = Proveedor
        fields = [
            'id_proveedor', 'nombre', 'insumo_principal', 'direccion', 'correo',
            'telefono', 'proxima_entrega', 'urgente', 'estado',
        ]
        read_only_fields = ['id_proveedor', 'estado', 'urgente']

    def get_urgente(self, proveedor):
        """True si algun insumo que surte esta por debajo de su minimo en tu sucursal."""
        sucursal = self.context.get('sucursal')
        if sucursal is None:
            return False
        return InsumoSucursal.objects.filter(
            insumo__proveedor_principal=proveedor, sucursal=sucursal, stock__lt=F('stock_minimo')
        ).exists()


class ProveedorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'insumo_principal', 'direccion', 'correo', 'telefono']
