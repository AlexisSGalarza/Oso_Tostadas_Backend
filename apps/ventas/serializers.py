from rest_framework import serializers

from .models import DetalleVenta, Pago, Turno, Venta


class TurnoAbrirSerializer(serializers.Serializer):
    monto_inicial = serializers.FloatField(min_value=0)


class TurnoCerrarSerializer(serializers.Serializer):
    monto_contado = serializers.FloatField(min_value=0)


class TurnoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turno
        fields = [
            'id_turno', 'fecha', 'hora_inicio', 'hora_fin', 'estado',
            'monto_inicial', 'monto_esperado', 'monto_contado', 'diferencia',
            'empleado', 'sucursal',
        ]
        read_only_fields = fields


class DetalleVentaInputSerializer(serializers.Serializer):
    id_producto = serializers.IntegerField()
    unidades = serializers.IntegerField(min_value=1)


class VentaCreateSerializer(serializers.Serializer):
    detalles = DetalleVentaInputSerializer(many=True, allow_empty=False)


class DetalleVentaSerializer(serializers.ModelSerializer):
    id_producto = serializers.IntegerField(source='producto_id', read_only=True)
    producto = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = DetalleVenta
        fields = ['id_producto', 'producto', 'unidades', 'precio_unitario', 'subtotal']


class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True, read_only=True)

    class Meta:
        model = Venta
        fields = ['id_venta', 'fecha', 'subtotal', 'impuesto', 'total', 'estado', 'turno', 'detalles']
        read_only_fields = fields


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ['id_pago', 'metodo_pago', 'monto', 'fecha', 'referencia', 'venta']
        read_only_fields = ['id_pago', 'fecha', 'venta']
