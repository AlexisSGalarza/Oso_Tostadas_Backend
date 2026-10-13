"""Etiquetas de codigo de barras para pegar en los paquetes.

Los codigos de 13 digitos se imprimen como EAN-13 y el resto como Code 128.
Ambos usan barras anchas y altas a proposito: una camara de telefono o de
laptop los lee aunque la etiqueta salga algo inclinada o desenfocada, cosa que
no pasaba con las barras delgadas de Code 39.
"""
from fpdf import FPDF

COLUMNAS = 3
FILAS = 6
ANCHO, ALTO = 62, 42  # mm por etiqueta; caben 3 x 6 en una hoja carta
ALTO_BARRAS = 20
ZONA_QUIETA = 10  # modulos en blanco a cada lado; sin ellos los lectores no encuentran el codigo

EAN_L = ('0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011')
EAN_G = ('0100111', '0110011', '0011011', '0100001', '0011101', '0111001', '0000101', '0010001', '0001001', '0010111')
EAN_R = ('1110010', '1100110', '1101100', '1000010', '1011100', '1001110', '1010000', '1000100', '1001000', '1110100')
EAN_PARIDAD = ('LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL')

# Anchos de barra/espacio de cada simbolo de Code 128 (valores 0-105) y el de alto.
CODE128 = (
    '212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 '
    '113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 '
    '212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 '
    '113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 '
    '314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 '
    '241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 '
    '214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 '
    '211232'
).split()
CODE128_ALTO = '2331112'
CODE128_INICIO_B = 104


def digito_verificador_ean13(doce_digitos: str) -> str:
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(doce_digitos))
    return str((10 - suma % 10) % 10)


def es_ean13(codigo: str) -> bool:
    return len(codigo) == 13 and codigo.isdigit() and digito_verificador_ean13(codigo[:12]) == codigo[12]


def modulos_ean13(codigo: str) -> str:
    """Cadena de 95 modulos ('1' = barra) de un EAN-13 valido."""
    paridad = EAN_PARIDAD[int(codigo[0])]
    izquierda = ''.join((EAN_L if p == 'L' else EAN_G)[int(d)] for p, d in zip(paridad, codigo[1:7]))
    derecha = ''.join(EAN_R[int(d)] for d in codigo[7:])
    return f'101{izquierda}01010{derecha}101'


def modulos_code128(texto: str) -> str:
    """Modulos de Code 128 (juego B: letras, numeros y simbolos ASCII)."""
    valores = [ord(c) - 32 for c in texto]
    if any(not 0 <= v <= 95 for v in valores):
        raise ValueError(f'El código "{texto}" tiene caracteres que no se pueden imprimir en Code 128.')
    verificador = (CODE128_INICIO_B + sum((i + 1) * v for i, v in enumerate(valores))) % 103
    anchos = ''.join(CODE128[v] for v in [CODE128_INICIO_B, *valores, verificador]) + CODE128_ALTO
    return ''.join(('1' if i % 2 == 0 else '0') * int(ancho) for i, ancho in enumerate(anchos))


def modulos_de(codigo: str) -> str:
    return modulos_ean13(codigo) if es_ean13(codigo) else modulos_code128(codigo)


def _dibujar_barras(pdf, modulos: str, x: float, y: float, ancho_disponible: float):
    """Centra el codigo en el ancho disponible usando el modulo mas grande que quepa (maximo 0.5 mm)."""
    modulo = min(0.5, ancho_disponible / (len(modulos) + 2 * ZONA_QUIETA))
    inicio = x + (ancho_disponible - len(modulos) * modulo) / 2
    pdf.set_fill_color(0, 0, 0)
    i = 0
    while i < len(modulos):
        if modulos[i] == '1':
            j = i
            while j < len(modulos) and modulos[j] == '1':
                j += 1
            pdf.rect(inicio + i * modulo, y, (j - i) * modulo, ALTO_BARRAS, style='F')
            i = j
        else:
            i += 1


def construir_etiquetas_pdf(productos, copias=1) -> bytes:
    pdf = FPDF(format='Letter')
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 12, 12)
    pdf.add_page()

    etiquetas = [producto for producto in productos for _ in range(copias)]
    por_pagina = COLUMNAS * FILAS
    for indice, producto in enumerate(etiquetas):
        if indice and indice % por_pagina == 0:
            pdf.add_page()
        posicion = indice % por_pagina
        x = 12 + (posicion % COLUMNAS) * (ANCHO + 2)
        y = 12 + (posicion // COLUMNAS) * ALTO

        pdf.set_draw_color(200, 200, 200)
        pdf.rect(x, y, ANCHO, ALTO - 2)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(x + 2, y + 2)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(ANCHO - 4, 4, producto.nombre[:38], align='C')
        pdf.set_xy(x + 2, y + 6)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(ANCHO - 4, 4, f'${producto.precio:,.2f}', align='C')
        _dibujar_barras(pdf, modulos_de(producto.codigo_barras), x, y + 11.5, ANCHO)
        pdf.set_xy(x + 2, y + 32.5)
        pdf.set_font('Courier', 'B', 10)
        pdf.cell(ANCHO - 4, 4, producto.codigo_barras, align='C')

    return bytes(pdf.output())
