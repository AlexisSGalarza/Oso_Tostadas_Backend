"""Arma el XML del CFDI 4.0 (comprobante de ingreso) de una venta.

El XML sale sin sello: el sellado con el CSD y el timbre los pone el PAC
(ver pac.py). Los importes se calculan sobre lo que la venta conserva despues
de devoluciones, para no facturar mercancia que ya se devolvio.
"""
from decimal import ROUND_HALF_UP, Decimal
from xml.etree import ElementTree as ET

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .catalogos import FORMAS_PAGO

NS_CFDI = 'http://www.sat.gob.mx/cfd/4'
NS_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
ESQUEMA = 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd'

ET.register_namespace('cfdi', NS_CFDI)
ET.register_namespace('xsi', NS_XSI)


def _d(valor) -> Decimal:
    return Decimal(str(valor))


def _m(valor: Decimal) -> str:
    """Importe a dos decimales, como lo pide el SAT para MXN."""
    return str(valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def conceptos_facturables(venta):
    """Renglones de la venta con las unidades que no se devolvieron."""
    devuelto = dict(
        venta.detalles_devolucion.values('producto_id')
        .annotate(total=Sum('cantidad'))
        .values_list('producto_id', 'total')
    )
    conceptos = []
    for detalle in venta.detalles.select_related('producto').all():
        unidades = detalle.unidades - devuelto.get(detalle.producto_id, 0)
        if unidades <= 0:
            continue
        valor_unitario = _d(detalle.precio_unitario)
        conceptos.append({
            'id_producto': detalle.producto_id,
            'descripcion': detalle.producto.nombre,
            'cantidad': unidades,
            'valor_unitario': valor_unitario,
            'importe': (valor_unitario * unidades).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        })
    return conceptos


def calcular_totales(conceptos):
    tasa = _d(settings.IVA_RATE)
    subtotal = sum((c['importe'] for c in conceptos), Decimal('0'))
    for concepto in conceptos:
        concepto['iva'] = (concepto['importe'] * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    impuesto = sum((c['iva'] for c in conceptos), Decimal('0'))
    return subtotal, impuesto, subtotal + impuesto


def construir_xml(venta, receptor, serie, folio, fecha=None) -> tuple[str, dict]:
    """Devuelve (xml, totales). `receptor` trae rfc, razon_social, codigo_postal, regimen_fiscal y uso_cfdi."""
    conceptos = conceptos_facturables(venta)
    subtotal, impuesto, total = calcular_totales(conceptos)
    tasa = f'{_d(settings.IVA_RATE):.6f}'
    fecha = fecha or timezone.localtime()
    pago = venta.pagos.first()

    comprobante = ET.Element(f'{{{NS_CFDI}}}Comprobante', {
        f'{{{NS_XSI}}}schemaLocation': ESQUEMA,
        'Version': '4.0',
        'Serie': serie,
        'Folio': str(folio),
        'Fecha': fecha.strftime('%Y-%m-%dT%H:%M:%S'),
        'FormaPago': FORMAS_PAGO.get(pago.metodo_pago if pago else '', '99'),
        'SubTotal': _m(subtotal),
        'Moneda': 'MXN',
        'Total': _m(total),
        'TipoDeComprobante': 'I',
        'Exportacion': '01',
        'MetodoPago': 'PUE',
        'LugarExpedicion': settings.CFDI_LUGAR_EXPEDICION,
    })
    ET.SubElement(comprobante, f'{{{NS_CFDI}}}Emisor', {
        'Rfc': settings.CFDI_EMISOR_RFC,
        'Nombre': settings.CFDI_EMISOR_NOMBRE,
        'RegimenFiscal': settings.CFDI_EMISOR_REGIMEN,
    })
    ET.SubElement(comprobante, f'{{{NS_CFDI}}}Receptor', {
        'Rfc': receptor['rfc'],
        'Nombre': receptor['razon_social'],
        'DomicilioFiscalReceptor': receptor['codigo_postal'],
        'RegimenFiscalReceptor': receptor['regimen_fiscal'],
        'UsoCFDI': receptor['uso_cfdi'],
    })

    nodo_conceptos = ET.SubElement(comprobante, f'{{{NS_CFDI}}}Conceptos')
    for concepto in conceptos:
        nodo = ET.SubElement(nodo_conceptos, f'{{{NS_CFDI}}}Concepto', {
            'ClaveProdServ': settings.CFDI_CLAVE_PROD_SERV,
            'NoIdentificacion': str(concepto['id_producto']),
            'Cantidad': str(concepto['cantidad']),
            'ClaveUnidad': settings.CFDI_CLAVE_UNIDAD,
            'Unidad': 'Pieza',
            'Descripcion': concepto['descripcion'],
            'ValorUnitario': _m(concepto['valor_unitario']),
            'Importe': _m(concepto['importe']),
            'ObjetoImp': '02',
        })
        traslados = ET.SubElement(ET.SubElement(nodo, f'{{{NS_CFDI}}}Impuestos'), f'{{{NS_CFDI}}}Traslados')
        ET.SubElement(traslados, f'{{{NS_CFDI}}}Traslado', {
            'Base': _m(concepto['importe']),
            'Impuesto': '002',
            'TipoFactor': 'Tasa',
            'TasaOCuota': tasa,
            'Importe': _m(concepto['iva']),
        })

    impuestos = ET.SubElement(comprobante, f'{{{NS_CFDI}}}Impuestos', {'TotalImpuestosTrasladados': _m(impuesto)})
    traslados = ET.SubElement(impuestos, f'{{{NS_CFDI}}}Traslados')
    ET.SubElement(traslados, f'{{{NS_CFDI}}}Traslado', {
        'Base': _m(subtotal),
        'Impuesto': '002',
        'TipoFactor': 'Tasa',
        'TasaOCuota': tasa,
        'Importe': _m(impuesto),
    })

    xml = ET.tostring(comprobante, encoding='unicode', xml_declaration=True)
    totales = {
        'subtotal': float(subtotal),
        'impuesto': float(impuesto),
        'total': float(total),
        'conceptos': conceptos,
    }
    return xml, totales
