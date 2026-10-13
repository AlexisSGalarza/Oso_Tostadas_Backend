"""Subconjunto de los catalogos del SAT (CFDI 4.0) que usa el punto de venta."""

REGIMENES_FISCALES = {
    '601': 'General de Ley Personas Morales',
    '603': 'Personas Morales con Fines no Lucrativos',
    '605': 'Sueldos y Salarios e Ingresos Asimilados a Salarios',
    '606': 'Arrendamiento',
    '612': 'Personas Físicas con Actividades Empresariales y Profesionales',
    '616': 'Sin obligaciones fiscales',
    '621': 'Incorporación Fiscal',
    '625': 'Actividades con ingresos a través de Plataformas Tecnológicas',
    '626': 'Régimen Simplificado de Confianza',
}

USOS_CFDI = {
    'G01': 'Adquisición de mercancías',
    'G03': 'Gastos en general',
    'S01': 'Sin efectos fiscales',
}

# Regimenes que, segun el catalogo del SAT, solo admiten el uso S01 de los que ofrecemos.
REGIMENES_SOLO_S01 = {'605', '616'}

RFC_PUBLICO_GENERAL = 'XAXX010101000'

# Forma de pago del SAT segun el metodo registrado en caja.
FORMAS_PAGO = {'efectivo': '01', 'tarjeta': '04'}
