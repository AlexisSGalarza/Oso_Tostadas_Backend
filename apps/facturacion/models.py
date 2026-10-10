from django.db import models


class Factura(models.Model):
    """CFDI 4.0 de ingreso emitido sobre una venta (una factura vigente por venta)."""

    id_factura = models.AutoField(primary_key=True)
    venta = models.OneToOneField(
        'ventas.Venta', on_delete=models.PROTECT, db_column='id_venta', related_name='factura'
    )
    # UUID que asigna el PAC al timbrar; tambien sirve de llave para la descarga publica.
    folio_fiscal = models.CharField(max_length=36, unique=True)
    serie = models.CharField(max_length=10, default='A')
    folio = models.IntegerField()

    rfc_receptor = models.CharField(max_length=13)
    razon_social = models.CharField(max_length=255)
    correo = models.CharField(max_length=150)
    codigo_postal = models.CharField(max_length=5)
    regimen_fiscal = models.CharField(max_length=3)
    uso_cfdi = models.CharField(max_length=4)

    subtotal = models.FloatField()
    impuesto = models.FloatField()
    total = models.FloatField()

    estado = models.CharField(max_length=20, default='timbrada')
    # 'pruebas' = timbre simulado, sin validez fiscal. 'produccion' = timbrada por el PAC.
    modo = models.CharField(max_length=20, default='pruebas')
    xml = models.TextField()
    fecha_emision = models.DateTimeField()
    correo_enviado = models.BooleanField(default=False)

    class Meta:
        db_table = 'factura'
        ordering = ['-fecha_emision']

    def __str__(self):
        return f'Factura {self.serie}{self.folio} - {self.folio_fiscal}'
