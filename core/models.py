from django.db import models


class Sucursal(models.Model):
    id_sucursal = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=20, default='activo')

    class Meta:
        db_table = 'sucursal'

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=100)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre_rol


class Empleado(models.Model):
    id_empleado = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    correo = models.CharField(max_length=150, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_ingreso = models.DateField()
    estado = models.CharField(max_length=20, default='activo')
    rol = models.ForeignKey(
        Rol, on_delete=models.PROTECT, db_column='id_rol', related_name='empleados'
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, db_column='id_sucursal', related_name='empleados'
    )

    class Meta:
        db_table = 'empleado'

    def __str__(self):
        return self.nombre


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
        Empleado, on_delete=models.PROTECT, db_column='id_empleado', related_name='turnos'
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, db_column='id_sucursal', related_name='turnos'
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


class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=255, blank=True)
    precio = models.FloatField()
    estado = models.CharField(max_length=20, default='activo')

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return self.nombre


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


class ProductoSucursal(models.Model):
    pk = models.CompositePrimaryKey('producto', 'sucursal')
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column='id_producto', related_name='stock_sucursales'
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column='id_sucursal', related_name='stock_productos'
    )
    stock = models.IntegerField(default=0)

    class Meta:
        db_table = 'producto_sucursal'

    def __str__(self):
        return f'{self.producto_id} @ {self.sucursal_id}'


class Insumo(models.Model):
    id_insumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    unidad_medida = models.CharField(max_length=20)
    estado = models.CharField(max_length=20, default='activo')

    class Meta:
        db_table = 'insumo'

    def __str__(self):
        return self.nombre


class InsumoSucursal(models.Model):
    pk = models.CompositePrimaryKey('insumo', 'sucursal')
    insumo = models.ForeignKey(
        Insumo, on_delete=models.CASCADE, db_column='id_insumo', related_name='stock_sucursales'
    )
    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column='id_sucursal', related_name='stock_insumos'
    )
    stock = models.FloatField(default=0)

    class Meta:
        db_table = 'insumo_sucursal'

    def __str__(self):
        return f'{self.insumo_id} @ {self.sucursal_id}'


class ProductoInsumo(models.Model):
    pk = models.CompositePrimaryKey('producto', 'insumo')
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column='id_producto', related_name='insumos'
    )
    insumo = models.ForeignKey(
        Insumo, on_delete=models.CASCADE, db_column='id_insumo', related_name='productos'
    )
    cantidad_requerida = models.FloatField()

    class Meta:
        db_table = 'producto_insumo'

    def __str__(self):
        return f'{self.producto_id} - {self.insumo_id}'


class Proveedor(models.Model):
    id_proveedor = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, blank=True)
    correo = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=20, default='activo')

    class Meta:
        db_table = 'proveedor'

    def __str__(self):
        return self.nombre


class ProveedorInsumo(models.Model):
    pk = models.CompositePrimaryKey('proveedor', 'insumo')
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.CASCADE, db_column='id_proveedor', related_name='insumos'
    )
    insumo = models.ForeignKey(
        Insumo, on_delete=models.CASCADE, db_column='id_insumo', related_name='proveedores'
    )
    costo = models.FloatField()

    class Meta:
        db_table = 'proveedor_insumo'

    def __str__(self):
        return f'{self.proveedor_id} - {self.insumo_id}'


class Pago(models.Model):
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
