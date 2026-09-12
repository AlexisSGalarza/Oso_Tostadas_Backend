from django.db import models


class Sucursal(models.Model):
    id_sucursal = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, blank=True)
    estado = models.CharField(max_length=20, default='activo')
    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)
    fondo_caja_default = models.FloatField(default=500)

    class Meta:
        db_table = 'sucursal'

    def __str__(self):
        return self.nombre
