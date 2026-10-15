from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """Cuenta de un cliente: solo sirve para facturar sus compras."""

    id_cliente = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='id_usuario', related_name='cliente'
    )
    nombre = models.CharField(max_length=150)
    correo = models.CharField(max_length=150, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    # Datos fiscales guardados para no capturarlos en cada factura (vacios hasta que los guarde).
    rfc = models.CharField(max_length=13, blank=True)
    razon_social = models.CharField(max_length=255, blank=True)
    codigo_postal = models.CharField(max_length=5, blank=True)
    regimen_fiscal = models.CharField(max_length=3, blank=True)
    uso_cfdi = models.CharField(max_length=4, blank=True)

    class Meta:
        db_table = 'cliente'

    def __str__(self):
        return f'{self.nombre} <{self.correo}>'

    @property
    def datos_fiscales(self):
        if not self.rfc:
            return None
        return {
            'rfc': self.rfc,
            'razon_social': self.razon_social,
            'codigo_postal': self.codigo_postal,
            'regimen_fiscal': self.regimen_fiscal,
            'uso_cfdi': self.uso_cfdi,
            'correo': self.correo,
        }


class TicketCliente(models.Model):
    """Ticket que el cliente agrego a su cuenta (comprobo tenerlo con su numero y total)."""

    id_ticket_cliente = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, db_column='id_cliente', related_name='tickets')
    # Un ticket pertenece a una sola cuenta: el primero que lo registra.
    venta = models.OneToOneField(
        'ventas.Venta', on_delete=models.CASCADE, db_column='id_venta', related_name='ticket_cliente'
    )
    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ticket_cliente'
        ordering = ['-agregado_en']

    def __str__(self):
        return f'Ticket {self.venta_id} de {self.cliente_id}'
