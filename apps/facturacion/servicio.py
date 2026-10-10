import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ventas.models import Venta

from .cfdi import conceptos_facturables, construir_xml
from .models import Factura
from .pac import obtener_pac
from .pdf import construir_factura_pdf

logger = logging.getLogger(__name__)

SERIE = 'A'
BACKENDS_SIN_ENVIO = ('console', 'dummy', 'locmem', 'filebased')


def motivo_no_facturable(venta) -> str | None:
    """Por que una venta no se puede facturar, o None si si se puede."""
    if hasattr(venta, 'factura'):
        return 'Este ticket ya tiene una factura.'
    if venta.estado != 'completada':
        return 'Este ticket no se puede facturar.'
    pagado = venta.pagos.aggregate(t=Sum('monto'))['t'] or 0
    if pagado + 0.01 < venta.total:
        return 'Este ticket todavía no está pagado.'
    limite = venta.fecha + timedelta(days=settings.CFDI_DIAS_PARA_FACTURAR)
    if timezone.localdate() > limite:
        return f'El plazo para facturar este ticket venció el {limite.strftime("%d/%m/%Y")}.'
    if not conceptos_facturables(venta):
        return 'Todos los productos de este ticket se devolvieron; no queda nada por facturar.'
    return None


def emitir_factura(id_venta: int, datos: dict) -> Factura:
    """Timbra y guarda la factura de una venta. Lanza ValidationError o ErrorTimbrado."""
    with transaction.atomic():
        venta = Venta.objects.select_for_update().get(pk=id_venta)
        motivo = motivo_no_facturable(venta)
        if motivo:
            raise ValidationError(motivo)

        folio = (Factura.objects.filter(serie=SERIE).aggregate(m=Max('folio'))['m'] or 0) + 1
        fecha = timezone.localtime()
        xml, totales = construir_xml(venta, datos, SERIE, folio, fecha)
        timbre = obtener_pac().timbrar(xml)

        factura = Factura.objects.create(
            venta=venta,
            folio_fiscal=timbre.folio_fiscal,
            serie=SERIE,
            folio=folio,
            rfc_receptor=datos['rfc'],
            razon_social=datos['razon_social'],
            correo=datos['correo'],
            codigo_postal=datos['codigo_postal'],
            regimen_fiscal=datos['regimen_fiscal'],
            uso_cfdi=datos['uso_cfdi'],
            subtotal=totales['subtotal'],
            impuesto=totales['impuesto'],
            total=totales['total'],
            modo=timbre.modo,
            xml=timbre.xml,
            fecha_emision=fecha,
        )

    if enviar_por_correo(factura):
        factura.correo_enviado = True
        factura.save(update_fields=['correo_enviado'])
    return factura


def enviar_por_correo(factura) -> bool:
    """Manda PDF y XML al receptor. Devuelve False si no hay un servidor de correo real configurado."""
    if any(nombre in settings.EMAIL_BACKEND for nombre in BACKENDS_SIN_ENVIO):
        return False
    try:
        mensaje = EmailMessage(
            subject=f'Tu factura {factura.serie}-{factura.folio} de {settings.CFDI_EMISOR_NOMBRE}',
            body=(
                f'Hola,\n\nAdjuntamos la factura de tu compra (ticket #{factura.venta_id}) '
                f'por ${factura.total:,.2f}.\nFolio fiscal: {factura.folio_fiscal}\n\nGracias por tu compra.'
            ),
            to=[factura.correo],
        )
        mensaje.attach(f'factura-{factura.serie}{factura.folio}.pdf', construir_factura_pdf(factura), 'application/pdf')
        mensaje.attach(f'factura-{factura.serie}{factura.folio}.xml', factura.xml, 'application/xml')
        mensaje.send()
        return True
    except Exception:
        logger.exception('No se pudo enviar por correo la factura %s', factura.folio_fiscal)
        return False
