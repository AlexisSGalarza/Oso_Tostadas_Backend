from rest_framework import serializers

from .models import DetalleVenta, Devolucion, DevolucionDetalle, Pago, Turno, Venta


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


class TurnoDetalleSerializer(TurnoSerializer):
    empleado_nombre = serializers.CharField(source='empleado.nombre', read_only=True)
    ventas = serializers.SerializerMethodField()

    class Meta(TurnoSerializer.Meta):
        fields = TurnoSerializer.Meta.fields + ['empleado_nombre', 'ventas']

    def get_ventas(self, turno):
        ventas = (
            turno.ventas.exclude(estado='cancelada')
            .prefetch_related('detalles__producto', 'pagos', 'devoluciones__detalles__producto')
            .order_by('creado_en', 'id_venta')
        )
        return VentaSerializer(ventas, many=True).data


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


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ['id_pago', 'metodo_pago', 'monto', 'fecha', 'referencia', 'venta']
        read_only_fields = ['id_pago', 'fecha', 'venta']


class DevolucionDetalleSerializer(serializers.ModelSerializer):
    id_producto = serializers.IntegerField(source='producto_id', read_only=True)
    producto = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = DevolucionDetalle
        fields = ['id_producto', 'producto', 'cantidad']


class DevolucionSerializer(serializers.ModelSerializer):
    detalles = DevolucionDetalleSerializer(many=True, read_only=True)

    class Meta:
        model = Devolucion
        fields = ['id_devolucion', 'fecha', 'creado_en', 'monto', 'venta', 'detalles']
        read_only_fields = fields


class DevolucionDetalleInputSerializer(serializers.Serializer):
    id_producto = serializers.IntegerField()
    cantidad = serializers.IntegerField(min_value=1)


class DevolucionCreateSerializer(serializers.Serializer):
    detalles = DevolucionDetalleInputSerializer(many=True, allow_empty=False)


class VentaSerializer(serializers.ModelSerializer):
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    pagos = PagoSerializer(many=True, read_only=True)
    devoluciones = DevolucionSerializer(many=True, read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id_venta', 'fecha', 'creado_en', 'subtotal', 'impuesto', 'total',
            'estado', 'turno', 'detalles', 'pagos', 'devoluciones',
        ]
        read_only_fields = fields
