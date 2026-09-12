from rest_framework import serializers

from .models import RegistroAuditoria


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source='actor.nombre', read_only=True, default='(empleado eliminado)')

    class Meta:
        model = RegistroAuditoria
        fields = ['id_registro', 'actor', 'accion', 'detalle', 'creado_en']
        read_only_fields = fields
