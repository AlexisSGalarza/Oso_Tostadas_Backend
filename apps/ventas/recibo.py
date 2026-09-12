from django.utils import timezone
from fpdf import FPDF


def construir_recibo_pdf(venta) -> bytes:
    """Arma un recibo de compra simple en PDF (NO es un CFDI/factura fiscal)."""
    sucursal = venta.turno.sucursal
    pago = venta.pagos.first()

    pdf = FPDF(format=(80, 200))  # tamano tipo ticket termico, se ajusta al contenido
    pdf.set_margins(5, 5, 5)
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 12)
    pdf.multi_cell(0, 5, sucursal.nombre, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 8)
    pdf.multi_cell(0, 4, sucursal.direccion, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 5, 'RECIBO DE COMPRA', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(1)

    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 4, f'Ticket: #{venta.id_venta}', new_x='LMARGIN', new_y='NEXT')
    hora = timezone.localtime(venta.creado_en).strftime('%H:%M') if venta.creado_en else ''
    pdf.cell(0, 4, f'Fecha: {venta.fecha} {hora}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 4, f'Método de pago: {pago.metodo_pago.capitalize() if pago else "Sin registrar"}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(38, 4, 'Producto')
    pdf.cell(10, 4, 'Cant.', align='R')
    pdf.cell(12, 4, 'P.U.', align='R')
    pdf.cell(10, 4, 'Total', align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 8)
    for detalle in venta.detalles.all():
        pdf.cell(38, 4, detalle.producto.nombre[:30])
        pdf.cell(10, 4, str(detalle.unidades), align='R')
        pdf.cell(12, 4, f'{detalle.precio_unitario:.2f}', align='R')
        pdf.cell(10, 4, f'{detalle.subtotal:.2f}', align='R', new_x='LMARGIN', new_y='NEXT')

    pdf.ln(2)
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(50, 4, 'Subtotal', align='R')
    pdf.cell(20, 4, f'${venta.subtotal:.2f}', align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(50, 4, 'IVA', align='R')
    pdf.cell(20, 4, f'${venta.impuesto:.2f}', align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(50, 5, 'TOTAL', align='R')
    pdf.cell(20, 5, f'${venta.total:.2f}', align='R', new_x='LMARGIN', new_y='NEXT')

    if pago and pago.referencia:
        pdf.set_font('Helvetica', '', 7)
        pdf.ln(1)
        pdf.cell(0, 4, f'Referencia: {pago.referencia}', new_x='LMARGIN', new_y='NEXT')

    pdf.ln(3)
    pdf.set_font('Helvetica', 'I', 6)
    pdf.multi_cell(
        0, 3, 'Este documento es un comprobante de compra y no tiene validez fiscal (no es un CFDI).',
        align='C', new_x='LMARGIN', new_y='NEXT',
    )

    return bytes(pdf.output())
