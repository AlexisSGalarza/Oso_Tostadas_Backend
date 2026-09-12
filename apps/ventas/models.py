from django.db import models

from apps.productos.models import Producto


class Turno(models.Model):
    id_turno = models.AutoField(primary_key=True)
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, default='abierto')
    monto_inicial = models.FloatField(default=0)
    monto_esperado = models.FloatField(null=True, blank=True)
    monto_contado = models.FloatField(null=True, blank=True)
    diferencia = models.FloatField(null=True, blank=True)
    empleado = models.ForeignKey(
        'empleados.Empleado', on_delete=models.PROTECT, db_column='id_empleado', related_name='turnos'
    )
    sucursal = models.ForeignKey(
        'sucursales.Sucursal', on_delete=models.PROTECT, db_column='id_sucursal', related_name='turnos'
    )

    class Meta:
        db_table = 'turno'

    def __str__(self):
        return f'Turno {self.id_turno} - {self.fecha}'


class MovimientoCaja(models.Model):
    id_movimiento = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=20)
    monto = models.FloatField()
    motivo = models.CharField(max_length=255, blank=True)
    fecha_hora = models.DateTimeField()
    turno = models.ForeignKey(
        Turno, on_delete=models.CASCADE, db_column='id_turno', related_name='movimientos_caja'
    )

    class Meta:
        db_table = 'movimiento_caja'

    def __str__(self):
        return f'{self.tipo} - {self.monto}'


class Venta(models.Model):
    id_venta = models.AutoField(primary_key=True)
    fecha = models.DateField()
    subtotal = models.FloatField()
    impuesto = models.FloatField(default=0)
    total = models.FloatField()
    estado = models.CharField(max_length=20, default='completada')
    turno = models.ForeignKey(
        Turno, on_delete=models.PROTECT, db_column='id_turno', related_name='ventas'
    )

    class Meta:
        db_table = 'venta'

    def __str__(self):
        return f'Venta {self.id_venta}'


class DetalleVenta(models.Model):
    pk = models.CompositePrimaryKey('venta', 'producto')
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='detalles'
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, db_column='id_producto', related_name='detalles_venta'
    )
    unidades = models.IntegerField()
    precio_unitario = models.FloatField()
    subtotal = models.FloatField()

    class Meta:
        db_table = 'detalle_venta'

    def __str__(self):
        return f'{self.venta_id} - {self.producto_id}'


class Pago(models.Model):
    """Registro de pago de una venta.

    Los pagos con tarjeta se procesan y autorizan en una terminal externa
    (fuera de este backend); aqui solo se registra el resultado ya
    autorizado (metodo_pago='tarjeta' y referencia = folio/voucher que
    entrega la terminal). No hay integracion con ninguna pasarela de pago.
    """

    id_pago = models.AutoField(primary_key=True)
    metodo_pago = models.CharField(max_length=30)
    monto = models.FloatField()
    fecha = models.DateField()
    referencia = models.CharField(max_length=100, blank=True)
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='pagos'
    )

    class Meta:
        db_table = 'pago'

    def __str__(self):
        return f'Pago {self.id_pago}'


class Devolucion(models.Model):
    id_devolucion = models.AutoField(primary_key=True)
    fecha = models.DateField()
    monto = models.FloatField()
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='devoluciones'
    )

    class Meta:
        db_table = 'devolucion'

    def __str__(self):
        return f'Devolucion {self.id_devolucion}'


class DevolucionDetalle(models.Model):
    pk = models.CompositePrimaryKey('devolucion', 'venta', 'producto')
    devolucion = models.ForeignKey(
        Devolucion, on_delete=models.CASCADE, db_column='id_devolucion', related_name='detalles'
    )
    venta = models.ForeignKey(
        Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='detalles_devolucion'
    )
    producto = models.ForeignKey(
        Producto, on_delete=models.PROTECT, db_column='id_producto', related_name='detalles_devolucion'
    )
    cantidad = models.IntegerField()

    class Meta:
        db_table = 'devolucion_detalle'

    def __str__(self):
        return f'{self.devolucion_id} - {self.producto_id}'
