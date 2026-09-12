from django.conf import settings
from django.db import models


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
        'sucursales.Sucursal', on_delete=models.PROTECT, db_column='id_sucursal', related_name='empleados'
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='empleado',
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'empleado'

    def __str__(self):
        return self.nombre
