from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.empleados.permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido
from apps.ventas.models import Venta
from apps.ventas.serializers import DetalleVentaSerializer

from .models import Factura
from .pac import ErrorTimbrado, modo_actual
from .pdf import construir_factura_pdf
from .serializers import DatosFiscalesSerializer, FacturaAdminSerializer
from .servicio import emitir_factura, motivo_no_facturable

TICKET_NO_ENCONTRADO = 'No encontramos un ticket con ese número y ese total.'


class VistaPublica(APIView):
    """Base de lo que usa el cliente desde /factura: sin login y con limite de peticiones."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'facturacion_publica'


def _ticket_del_cliente(folio, total):
    """El ticket solo se muestra si el total coincide con el impreso; si no, es como si no existiera."""
    try:
        total = float(total)
    except (TypeError, ValueError):
        raise ValidationError('Escribe el total de tu compra tal como aparece en el ticket.')
    venta = (
        Venta.objects.filter(pk=folio)
        .exclude(estado='cancelada')
        .select_related('turno__sucursal')
        .prefetch_related('detalles__producto', 'pagos')
        .first()
    )
    if venta is None or abs(venta.total - total) > 0.005:
        raise NotFound(TICKET_NO_ENCONTRADO)
    return venta


class TicketPublicoView(VistaPublica):
    """GET /api/publico/tickets/<folio>/?total=34.80 - resumen del ticket para confirmar antes de facturar."""

    def get(self, request, folio):
        venta = _ticket_del_cliente(folio, request.query_params.get('total'))
        facturado = hasattr(venta, 'factura')
        return Response({
            'id_venta': venta.id_venta,
            'folio': venta.id_venta,
            'fecha': venta.fecha,
            'creado_en': venta.creado_en,
            'subtotal': venta.subtotal,
            'impuesto': venta.impuesto,
            'total': venta.total,
            'detalles': DetalleVentaSerializer(venta.detalles.all(), many=True).data,
            'facturado': facturado,
            'motivo_no_facturable': None if facturado else motivo_no_facturable(venta),
        })


class FacturaPublicaView(VistaPublica):
    """POST /api/publico/tickets/<id_venta>/factura/ - timbra la factura con los datos fiscales del cliente."""

    def post(self, request, id_venta):
        serializer = DatosFiscalesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        _ticket_del_cliente(id_venta, datos['total'])

        try:
            factura = emitir_factura(id_venta, datos)
        except ErrorTimbrado as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                'folio_fiscal': factura.folio_fiscal,
                'serie': factura.serie,
                'folio': factura.folio,
                'correo': factura.correo,
                'correo_enviado': factura.correo_enviado,
                'fecha_emision': factura.fecha_emision,
                'modo': factura.modo,
                'url_pdf': f'/publico/facturas/{factura.folio_fiscal}/pdf/',
                'url_xml': f'/publico/facturas/{factura.folio_fiscal}/xml/',
            },
            status=status.HTTP_201_CREATED,
        )


class FacturaArchivoView(VistaPublica):
    """GET /api/publico/facturas/<folio_fiscal>/<pdf|xml>/ - el folio fiscal (UUID) hace de llave."""

    def get(self, request, folio_fiscal, formato):
        factura = get_object_or_404(
            Factura.objects.select_related('venta__turno__sucursal'), folio_fiscal=folio_fiscal.upper()
        )
        nombre = f'factura-{factura.serie}{factura.folio}'
        if formato == 'xml':
            response = HttpResponse(factura.xml, content_type='application/xml')
        else:
            response = HttpResponse(construir_factura_pdf(factura), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nombre}.{formato}"'
        return response


class FacturasAdminView(APIView):
    """GET /api/admin/facturas/ - facturas emitidas en tu sucursal y como esta configurado el timbrado."""

    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo, rol_requerido(*ROLES_SUPERVISOR)]

    def get(self, request):
        sucursal = request.user.empleado.sucursal
        facturas = Factura.objects.filter(venta__turno__sucursal=sucursal)
        return Response({
            'configuracion': {
                'pac': settings.CFDI_PAC,
                'modo': modo_actual(),
                'emisor_rfc': settings.CFDI_EMISOR_RFC,
                'emisor_nombre': settings.CFDI_EMISOR_NOMBRE,
                'dias_para_facturar': settings.CFDI_DIAS_PARA_FACTURAR,
            },
            'facturas': FacturaAdminSerializer(facturas, many=True).data,
        })
