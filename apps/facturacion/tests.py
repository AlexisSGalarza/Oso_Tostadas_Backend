from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado
from apps.productos.models import Producto, ProductoSucursal
from apps.sucursales.models import Sucursal
from apps.ventas.tests import crear_empleado

from .models import Factura
from .pac import ErrorTimbrado, PacFinkok

DATOS = {
    'rfc': 'cacx7605101p8',
    'razon_social': '  Xochilt  Casas Chavez ',
    'correo': 'cliente@demo.com',
    'codigo_postal': '36257',
    'regimen_fiscal': '612',
    'uso_cfdi': 'G03',
}


class FacturacionTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        crear_empleado('vendedor@demo.com', 'Vendedor', self.sucursal)
        crear_empleado('gerente@demo.com', 'Gerente', self.sucursal)
        self.producto = Producto.objects.create(nombre='Paquete 50', precio=60)
        ProductoSucursal.objects.create(producto=self.producto, sucursal=self.sucursal, stock=20)

        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 3}]}, format='json'
        ).data
        self.id_venta = venta['id_venta']
        self.total = venta['total']  # 3 x 60 + 16% = 208.80
        self.client.post(
            f'/api/ventas/{self.id_venta}/pagos/', {'metodo_pago': 'efectivo', 'monto': self.total}, format='json'
        )
        self.client.credentials()  # el cliente factura sin sesion

    def login(self, correo):
        numero = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post('/api/auth/login/', {'numero_empleado': numero, 'password': 'ClaveSegura1!'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def facturar(self, **cambios):
        return self.client.post(
            f'/api/publico/tickets/{self.id_venta}/factura/', {**DATOS, 'total': self.total, **cambios}, format='json'
        )

    def test_buscar_ticket_exige_el_total_correcto(self):
        ok = self.client.get(f'/api/publico/tickets/{self.id_venta}/?total={self.total}')
        self.assertEqual(ok.status_code, 200)
        self.assertFalse(ok.data['facturado'])
        self.assertIsNone(ok.data['motivo_no_facturable'])

        self.assertEqual(self.client.get(f'/api/publico/tickets/{self.id_venta}/?total=1').status_code, 404)
        self.assertEqual(self.client.get(f'/api/publico/tickets/{self.id_venta}/').status_code, 400)

    def test_emite_factura_de_prueba_y_no_permite_duplicarla(self):
        response = self.facturar()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['modo'], 'pruebas')
        self.assertFalse(response.data['correo_enviado'])

        factura = Factura.objects.get(venta_id=self.id_venta)
        self.assertEqual(factura.rfc_receptor, 'CACX7605101P8')
        self.assertEqual(factura.razon_social, 'XOCHILT CASAS CHAVEZ')
        self.assertAlmostEqual(factura.total, 208.80)
        self.assertIn('Version="4.0"', factura.xml)
        self.assertIn('TimbreFiscalDigital', factura.xml)
        self.assertIn('TotalImpuestosTrasladados="28.80"', factura.xml)

        self.assertEqual(self.facturar().status_code, 400)
        ticket = self.client.get(f'/api/publico/tickets/{self.id_venta}/?total={self.total}')
        self.assertTrue(ticket.data['facturado'])

    def test_descarga_publica_de_pdf_y_xml(self):
        folio_fiscal = self.facturar().data['folio_fiscal']
        pdf = self.client.get(f'/api/publico/facturas/{folio_fiscal}/pdf/')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        xml = self.client.get(f'/api/publico/facturas/{folio_fiscal}/xml/')
        self.assertEqual(xml.status_code, 200)
        self.assertIn(b'cfdi:Comprobante', xml.content)

    def test_valida_datos_fiscales(self):
        self.assertEqual(self.facturar(rfc='123').status_code, 400)
        self.assertEqual(self.facturar(codigo_postal='123').status_code, 400)
        # 616 (sin obligaciones) solo admite S01
        self.assertEqual(self.facturar(regimen_fiscal='616', uso_cfdi='G03').status_code, 400)
        self.assertEqual(self.facturar(total=1).status_code, 404)
        self.assertEqual(Factura.objects.count(), 0)

    def test_factura_solo_lo_que_no_se_devolvio(self):
        self.login('vendedor@demo.com')
        self.client.post(
            f'/api/ventas/{self.id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]}, format='json',
        )
        self.client.credentials()
        response = self.facturar()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertAlmostEqual(Factura.objects.get().total, 139.20)  # 2 x 60 + 16%

    def test_admin_lista_facturas_de_su_sucursal(self):
        self.facturar()
        self.assertEqual(self.client.get('/api/admin/facturas/').status_code, 401)
        self.login('gerente@demo.com')
        response = self.client.get('/api/admin/facturas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['configuracion']['modo'], 'pruebas')
        self.assertEqual(len(response.data['facturas']), 1)

    def test_personal_elige_la_compra_de_una_lista_y_la_factura_sin_escribir_el_ticket(self):
        self.assertEqual(self.client.get('/api/facturacion/ventas/').status_code, 401)
        self.login('vendedor@demo.com')
        pendientes = self.client.get('/api/facturacion/ventas/').data
        self.assertEqual([v['id_venta'] for v in pendientes], [self.id_venta])
        self.assertEqual(pendientes[0]['detalles'][0]['producto'], 'Paquete 50')

        response = self.client.post(f'/api/facturacion/ventas/{self.id_venta}/factura/', DATOS, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get('/api/facturacion/ventas/').data, [])
        self.assertEqual(len(self.client.get('/api/admin/facturas/').data['facturas']), 1)

    def test_vendedor_solo_ve_y_factura_sus_propias_ventas(self):
        crear_empleado('otro@demo.com', 'Vendedor', self.sucursal)
        self.login('otro@demo.com')
        self.assertEqual(self.client.get('/api/facturacion/ventas/').data, [])
        ajena = self.client.post(f'/api/facturacion/ventas/{self.id_venta}/factura/', DATOS, format='json')
        self.assertEqual(ajena.status_code, 404)
        self.login('gerente@demo.com')
        self.assertEqual(len(self.client.get('/api/facturacion/ventas/').data), 1)

    @override_settings(CFDI_PAC='finkok', FINKOK_USUARIO='', FINKOK_PASSWORD='')
    def test_finkok_sin_credenciales_responde_error_claro(self):
        response = self.facturar()
        self.assertEqual(response.status_code, 502)
        self.assertIn('FINKOK_USUARIO', response.data['detail'])
        self.assertEqual(Factura.objects.count(), 0)


class PacFinkokRespuestaTestCase(APITestCase):
    """La llamada real a Finkok no se prueba aqui; solo como se interpreta su respuesta."""

    SOBRE = (
        '<senv:Envelope xmlns:senv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:tns="http://facturacion.finkok.com/stamp" xmlns:s0="apps.services.soap.core.views">'
        '<senv:Body><tns:sign_stampResponse><tns:sign_stampResult>{cuerpo}'
        '</tns:sign_stampResult></tns:sign_stampResponse></senv:Body></senv:Envelope>'
    )

    @override_settings(FINKOK_USUARIO='u', FINKOK_PASSWORD='p')
    def test_respuesta_timbrada(self):
        cuerpo = self.SOBRE.format(cuerpo=(
            '<s0:xml>&lt;cfdi:Comprobante/&gt;</s0:xml>'
            '<s0:UUID>6f1e4c2a-0b7d-4e55-9c3f-2a1b7d9e8f00</s0:UUID><s0:CodEstatus>ok</s0:CodEstatus>'
        ))
        timbre = PacFinkok()._leer_respuesta(cuerpo.encode())
        self.assertEqual(timbre.folio_fiscal, '6F1E4C2A-0B7D-4E55-9C3F-2A1B7D9E8F00')
        self.assertEqual(timbre.xml, '<cfdi:Comprobante/>')
        self.assertEqual(timbre.modo, 'pruebas')  # FINKOK_URL por defecto es el ambiente demo

    @override_settings(FINKOK_USUARIO='u', FINKOK_PASSWORD='p')
    def test_respuesta_con_incidencia(self):
        cuerpo = self.SOBRE.format(cuerpo=(
            '<s0:Incidencias><s0:Incidencia><s0:CodigoError>CFDI40147</s0:CodigoError>'
            '<s0:MensajeIncidencia>El nombre del receptor no coincide</s0:MensajeIncidencia>'
            '</s0:Incidencia></s0:Incidencias>'
        ))
        with self.assertRaisesMessage(ErrorTimbrado, 'CFDI40147'):
            PacFinkok()._leer_respuesta(cuerpo.encode())

    @override_settings(FINKOK_USUARIO='u', FINKOK_PASSWORD='p')
    def test_envia_sign_stamp_al_ambiente_configurado(self):
        cuerpo = self.SOBRE.format(cuerpo='<s0:xml>x</s0:xml><s0:UUID>6f1e4c2a-0b7d-4e55-9c3f-2a1b7d9e8f00</s0:UUID>')
        respuesta = mock.MagicMock()
        respuesta.__enter__.return_value.read.return_value = cuerpo.encode()
        with mock.patch('apps.facturacion.pac.request.urlopen', return_value=respuesta) as urlopen:
            PacFinkok().timbrar('<a/>')
        peticion = urlopen.call_args[0][0]
        self.assertEqual(peticion.full_url, 'https://demo-facturacion.finkok.com/servicios/soap/stamp')
        self.assertIn(b'<apps:sign_stamp>', peticion.data)
