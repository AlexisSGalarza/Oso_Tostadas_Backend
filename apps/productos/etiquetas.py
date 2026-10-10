from fpdf import FPDF

COLUMNAS = 3
ANCHO, ALTO = 62, 34  # mm por etiqueta; caben 3 x 7 en una hoja carta


def construir_etiquetas_pdf(productos, copias=1) -> bytes:
    """Hoja carta con etiquetas Code 39 (el formato que lee cualquier lector) para pegar en los paquetes."""
    pdf = FPDF(format='Letter')
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 12, 12)
    pdf.add_page()

    etiquetas = [producto for producto in productos for _ in range(copias)]
    por_pagina = COLUMNAS * int((pdf.h - 24) // ALTO)
    for indice, producto in enumerate(etiquetas):
        if indice and indice % por_pagina == 0:
            pdf.add_page()
        posicion = indice % por_pagina
        x = 12 + (posicion % COLUMNAS) * (ANCHO + 2)
        y = 12 + (posicion // COLUMNAS) * ALTO

        pdf.set_draw_color(200, 200, 200)
        pdf.rect(x, y, ANCHO, ALTO - 2)
        pdf.set_xy(x + 2, y + 2)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(ANCHO - 4, 4, producto.nombre[:38], align='C')
        pdf.set_xy(x + 2, y + 6)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(ANCHO - 4, 4, f'${producto.precio:,.2f}', align='C')
        # Code 39 exige mayusculas y va entre asteriscos
        codigo = f'*{producto.codigo_barras.upper()}*'
        # En fpdf2 `w` es la barra ancha y cada caracter ocupa ~5.34 w; se ajusta para llenar la etiqueta.
        barra = min(1.0, (ANCHO - 10) / (5.34 * len(codigo)))
        pdf.code39(codigo, x=x + (ANCHO - 5.34 * len(codigo) * barra) / 2, y=y + 11, w=barra, h=13)
        pdf.set_xy(x + 2, y + 25)
        pdf.set_font('Courier', '', 8)
        pdf.cell(ANCHO - 4, 4, producto.codigo_barras, align='C')

    return bytes(pdf.output())
