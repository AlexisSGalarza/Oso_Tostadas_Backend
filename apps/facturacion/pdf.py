from django.conf import settings
from django.utils import timezone
from fpdf import FPDF

from .catalogos import REGIMENES_FISCALES, USOS_CFDI
from .cfdi import conceptos_facturables

VERDE = (22, 48, 31)
GRIS = (95, 86, 70)


def construir_factura_pdf(factura) -> bytes:
    """Representacion impresa del CFDI. En modo de pruebas lleva la leyenda de que no tiene validez fiscal."""
    venta = factura.venta
    sucursal = venta.turno.sucursal
    es_prueba = factura.modo != 'produccion'

    pdf = FPDF(format='Letter')
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    ancho = pdf.w - 30

    if es_prueba:
        pdf.set_fill_color(178, 58, 46)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(
            0, 7, 'FACTURA DE PRUEBA - SIN VALIDEZ FISCAL (timbrado simulado)',
            align='C', fill=True, new_x='LMARGIN', new_y='NEXT',
        )
        pdf.ln(3)

    pdf.set_text_color(*VERDE)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(ancho * 0.6, 9, settings.CFDI_EMISOR_NOMBRE)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(ancho * 0.4, 9, f'Factura {factura.serie}-{factura.folio}', align='R', new_x='LMARGIN', new_y='NEXT')

    pdf.set_text_color(*GRIS)
    pdf.set_font('Helvetica', '', 9)
    emision = timezone.localtime(factura.fecha_emision).strftime('%d/%m/%Y %H:%M')
    regimen_emisor = REGIMENES_FISCALES.get(settings.CFDI_EMISOR_REGIMEN, '')
    izquierda = [
        f'RFC: {settings.CFDI_EMISOR_RFC}',
        f'Régimen: {settings.CFDI_EMISOR_REGIMEN} {regimen_emisor}',
        f'{sucursal.nombre}, {sucursal.direccion}',
    ]
    derecha = [
        f'Fecha de emisión: {emision}',
        f'Lugar de expedición: {settings.CFDI_LUGAR_EXPEDICION}',
        f'Ticket de venta: #{venta.id_venta}',
    ]
    for texto_izq, texto_der in zip(izquierda, derecha):
        pdf.cell(ancho * 0.6, 5, texto_izq[:70])
        pdf.cell(ancho * 0.4, 5, texto_der, align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)

    def titulo(texto):
        pdf.set_text_color(*VERDE)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, texto, new_x='LMARGIN', new_y='NEXT')
        pdf.set_draw_color(211, 199, 172)
        pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
        pdf.ln(1.5)
        pdf.set_text_color(31, 28, 21)
        pdf.set_font('Helvetica', '', 9)

    titulo('Receptor')
    pdf.cell(0, 5, f'{factura.razon_social}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, f'RFC: {factura.rfc_receptor}    C.P. fiscal: {factura.codigo_postal}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(
        0, 5,
        f'Régimen: {factura.regimen_fiscal} {REGIMENES_FISCALES.get(factura.regimen_fiscal, "")}',
        new_x='LMARGIN', new_y='NEXT',
    )
    pdf.cell(
        0, 5, f'Uso del CFDI: {factura.uso_cfdi} {USOS_CFDI.get(factura.uso_cfdi, "")}',
        new_x='LMARGIN', new_y='NEXT',
    )
    pdf.ln(4)

    titulo('Conceptos')
    columnas = [(ancho * 0.12, 'Cantidad', 'R'), (ancho * 0.52, 'Descripción', 'L'),
                (ancho * 0.18, 'Valor unitario', 'R'), (ancho * 0.18, 'Importe', 'R')]
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*GRIS)
    for i, (w, texto, alineacion) in enumerate(columnas):
        ultimo = i == len(columnas) - 1
        pdf.cell(w, 5, texto, align=alineacion, **({'new_x': 'LMARGIN', 'new_y': 'NEXT'} if ultimo else {}))
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(31, 28, 21)
    for concepto in conceptos_facturables(venta):
        pdf.cell(columnas[0][0], 6, str(concepto['cantidad']), align='R')
        pdf.cell(columnas[1][0], 6, f"  {concepto['descripcion'][:60]}")
        pdf.cell(columnas[2][0], 6, f"${concepto['valor_unitario']:,.2f}", align='R')
        pdf.cell(columnas[3][0], 6, f"${concepto['importe']:,.2f}", align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)
    pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
    pdf.ln(2)

    for etiqueta, valor, negrita in (
        ('Subtotal', factura.subtotal, False),
        (f'IVA {settings.IVA_RATE * 100:.0f}%', factura.impuesto, False),
        ('Total', factura.total, True),
    ):
        pdf.set_font('Helvetica', 'B' if negrita else '', 11 if negrita else 9)
        pdf.cell(ancho * 0.82, 6, etiqueta, align='R')
        pdf.cell(ancho * 0.18, 6, f'${valor:,.2f}', align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    titulo('Datos fiscales')
    pdf.set_font('Helvetica', '', 8)
    pago = venta.pagos.first()
    forma = 'Tarjeta' if pago and pago.metodo_pago == 'tarjeta' else 'Efectivo'
    pdf.cell(0, 4.5, f'Folio fiscal (UUID): {factura.folio_fiscal}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(
        0, 4.5, f'Tipo de comprobante: I - Ingreso    Método de pago: PUE    Forma de pago: {forma}    Moneda: MXN',
        new_x='LMARGIN', new_y='NEXT',
    )
    pdf.ln(3)
    pdf.set_text_color(*GRIS)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.multi_cell(
        0, 4,
        'Documento generado en modo de pruebas con un timbre simulado. No es un comprobante fiscal válido ante el SAT.'
        if es_prueba else 'Este documento es una representación impresa de un CFDI versión 4.0.',
        new_x='LMARGIN', new_y='NEXT',
    )

    return bytes(pdf.output())
