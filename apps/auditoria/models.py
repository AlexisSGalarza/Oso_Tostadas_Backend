from django.db import models


class RegistroAuditoria(models.Model):
    id_registro = models.AutoField(primary_key=True)
    actor = models.ForeignKey(
        'empleados.Empleado', on_delete=models.SET_NULL, null=True,
        db_column='id_actor', related_name='acciones_auditadas',
    )
    accion = models.CharField(max_length=50)
    detalle = models.CharField(max_length=255)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'registro_auditoria'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.accion} - {self.detalle}'


def registrar(actor, accion, detalle):
    """Guarda una entrada de auditoria; nunca debe tumbar la operacion que la origina."""
    try:
        RegistroAuditoria.objects.create(actor=actor, accion=accion, detalle=detalle)
    except Exception:
        pass
