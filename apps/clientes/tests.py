from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado
from apps.facturacion.models import Factura
from apps.productos.models import Producto, ProductoSucursal
from apps.sucursales.models import Sucursal
from apps.ventas.tests import crear_empleado

DATOS = {
    'rfc': 'CACX7605101P8',
    'razon_social': 'Xochilt Casas Chavez',
    'codigo_postal': '36257',
    'regimen_fiscal': '612',
    'uso_cfdi': 'G03',
}


class PortalClienteTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        crear_empleado('vendedor@demo.com', 'Vendedor', sucursal)
        producto = Producto.objects.create(nombre='Paquete 50', precio=60)
        ProductoSucursal.objects.create(producto=producto, sucursal=sucursal, stock=20)

        numero = Empleado.objects.get(correo='vendedor@demo.com').numero_empleado
        login = self.client.post('/api/auth/login/', {'numero_empleado': numero, 'password': 'ClaveSegura1!'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': producto.id_producto, 'unidades': 2}]}, format='json'
        ).data
        self.client.post(f"/api/ventas/{venta['id_venta']}/pagos/", {'metodo_pago': 'efectivo', 'monto': venta['total']}, format='json')
        self.venta = venta
        self.client.credentials()

    def registrar(self, correo='ana@correo.com'):
        r = self.client.post('/api/clientes/registro/', {'nombre': 'Ana', 'correo': correo, 'password': 'Tostada2026!'})
        self.assertEqual(r.status_code, 201, r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r

    def test_registro_login_y_flujo_completo(self):
        self.registrar()
        self.client.credentials()
        malo = self.client.post('/api/clientes/login/', {'correo': 'ana@correo.com', 'password': 'otra'})
        self.assertEqual(malo.status_code, 401)
        bueno = self.client.post('/api/clientes/login/', {'correo': 'ANA@correo.com', 'password': 'Tostada2026!'})
        self.assertEqual(bueno.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {bueno.data['access']}")

        self.assertEqual(self.client.post('/api/clientes/tickets/', {'folio': self.venta['id_venta'], 'total': 1}).status_code, 404)
        agregado = self.client.post('/api/clientes/tickets/', {'folio': self.venta['id_venta'], 'total': self.venta['total']})
        self.assertEqual(agregado.status_code, 201, agregado.data)
        self.assertIsNone(agregado.data['factura'])

        factura = self.client.post(f"/api/clientes/tickets/{self.venta['id_venta']}/factura/", DATOS, format='json')
        self.assertEqual(factura.status_code, 201, factura.data)
        self.assertEqual(Factura.objects.get().correo, 'ana@correo.com')  # sin correo usa el de la cuenta

        me = self.client.get('/api/clientes/me/').data
        self.assertEqual(me['datos_fiscales']['rfc'], 'CACX7605101P8')
        tickets = self.client.get('/api/clientes/tickets/').data
        self.assertEqual(tickets[0]['factura']['serie'], 'A')

    def test_un_ticket_pertenece_a_una_sola_cuenta(self):
        self.registrar('ana@correo.com')
        self.client.post('/api/clientes/tickets/', {'folio': self.venta['id_venta'], 'total': self.venta['total']})
        self.registrar('beto@correo.com')
        ajeno = self.client.post('/api/clientes/tickets/', {'folio': self.venta['id_venta'], 'total': self.venta['total']})
        self.assertEqual(ajeno.status_code, 400)
        no_suyo = self.client.post(f"/api/clientes/tickets/{self.venta['id_venta']}/factura/", DATOS, format='json')
        self.assertEqual(no_suyo.status_code, 404)

    def test_cliente_no_entra_a_pantallas_del_personal_ni_al_reves(self):
        self.registrar()
        for ruta in ('/api/me/', '/api/ventas/', '/api/admin/facturas/', '/api/facturacion/ventas/'):
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)
        self.client.credentials()
        empleado = self.client.post('/api/clientes/login/', {'correo': 'vendedor@demo.com', 'password': 'ClaveSegura1!'})
        self.assertEqual(empleado.status_code, 401)

    def test_correo_repetido_y_contrasena_debil(self):
        self.registrar()
        self.client.credentials()
        repetido = self.client.post('/api/clientes/registro/', {'nombre': 'X', 'correo': 'ana@correo.com', 'password': 'Tostada2026!'})
        self.assertEqual(repetido.status_code, 400)
        debil = self.client.post('/api/clientes/registro/', {'nombre': 'X', 'correo': 'x@correo.com', 'password': '12345678'})
        self.assertEqual(debil.status_code, 400)
