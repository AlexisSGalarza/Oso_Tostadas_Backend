from django.db import models


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


class ProductoSucursal(models.Model):
    pk = models.CompositePrimaryKey('producto', 'sucursal')
    producto = models.ForeignKey(
        Producto, on_delete=models.CASCADE, db_column='id_producto', related_name='stock_sucursales'
    )
    sucursal = models.ForeignKey(
        'sucursales.Sucursal', on_delete=models.CASCADE, db_column='id_sucursal', related_name='stock_productos'
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
        'sucursales.Sucursal', on_delete=models.CASCADE, db_column='id_sucursal', related_name='stock_insumos'
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
