import re

from rest_framework import serializers

from .catalogos import REGIMENES_FISCALES, REGIMENES_SOLO_S01, RFC_PUBLICO_GENERAL, USOS_CFDI
from .models import Factura

RFC_REGEX = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')


class DatosFiscalesSerializer(serializers.Serializer):
    rfc = serializers.CharField(max_length=13)
    razon_social = serializers.CharField(max_length=255)
    # Opcional: sin correo la factura solo se descarga (por ejemplo, publico en general).
    correo = serializers.EmailField(max_length=150, required=False, allow_blank=True, default='')
    codigo_postal = serializers.RegexField(r'^\d{5}$', error_messages={'invalid': 'El código postal debe tener 5 dígitos.'})
    regimen_fiscal = serializers.ChoiceField(choices=list(REGIMENES_FISCALES))
    uso_cfdi = serializers.ChoiceField(choices=list(USOS_CFDI))

    def validate_rfc(self, valor):
        valor = valor.strip().upper()
        if not RFC_REGEX.match(valor):
            raise serializers.ValidationError('El RFC no tiene un formato válido.')
        return valor

    def validate_razon_social(self, valor):
        # El SAT compara el nombre tal cual esta en la constancia: mayusculas y sin espacios de mas.
        return ' '.join(valor.split()).upper()

    def validate(self, datos):
        if datos['rfc'] == RFC_PUBLICO_GENERAL and (datos['regimen_fiscal'] != '616' or datos['uso_cfdi'] != 'S01'):
            raise serializers.ValidationError(
                'Con el RFC genérico la factura debe ir con régimen 616 y uso S01 (sin efectos fiscales).'
            )
        if datos['regimen_fiscal'] in REGIMENES_SOLO_S01 and datos['uso_cfdi'] != 'S01':
            raise serializers.ValidationError(
                f'El régimen {datos["regimen_fiscal"]} solo admite el uso S01 (sin efectos fiscales).'
            )
        return datos


class DatosFiscalesPublicosSerializer(DatosFiscalesSerializer):
    # Lo que el cliente ve impreso en su ticket; evita facturar tickets ajenos adivinando el numero.
    total = serializers.FloatField(min_value=0)


class FacturaAdminSerializer(serializers.ModelSerializer):
    id_venta = serializers.IntegerField(source='venta_id', read_only=True)

    class Meta:
        model = Factura
        fields = [
            'id_factura', 'serie', 'folio', 'folio_fiscal', 'id_venta', 'razon_social', 'rfc_receptor',
            'correo', 'uso_cfdi', 'subtotal', 'impuesto', 'total', 'estado', 'modo', 'fecha_emision',
            'correo_enviado',
        ]
        read_only_fields = fields
