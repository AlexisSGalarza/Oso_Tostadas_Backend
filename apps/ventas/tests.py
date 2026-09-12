from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol
from apps.productos.models import Producto, ProductoSucursal
from apps.sucursales.models import Sucursal

from .models import Pago, Turno, Venta


def crear_empleado(correo, rol_nombre, sucursal, password='ClaveSegura1!'):
    rol, _ = Rol.objects.get_or_create(nombre_rol=rol_nombre)
    User = get_user_model()
    user = User.objects.create_user(username=correo, password=password)
    return Empleado.objects.create(
        nombre=correo.split('@')[0],
        correo=correo,
        fecha_ingreso=date.today(),
        rol=rol,
        sucursal=sucursal,
        usuario=user,
    )


class VentasFlowTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # el throttle de login usa el cache; evita arrastrar el contador entre tests
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.vendedor = crear_empleado('vendedor@demo.com', 'Vendedor', self.sucursal)
        self.gerente = crear_empleado('gerente@demo.com', 'Gerente', self.sucursal)
        self.bodeguero = crear_empleado('bodeguero@demo.com', 'Bodeguero', self.sucursal)

        self.producto = Producto.objects.create(nombre='Chico', precio=100)
        self.stock = ProductoSucursal.objects.create(producto=self.producto, sucursal=self.sucursal, stock=5)

    def login(self, correo, password='ClaveSegura1!'):
        response = self.client.post('/api/auth/login/', {'correo': correo, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_no_puede_vender_sin_turno_abierto(self):
        self.login('vendedor@demo.com')
        response = self.client.post('/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_flujo_completo_abrir_turno_vender_pagar_cerrar_turno(self):
        self.login('vendedor@demo.com')

        abrir = self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        self.assertEqual(abrir.status_code, 201)
        self.assertEqual(abrir.data['estado'], 'abierto')

        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 2}]}, format='json'
        )
        self.assertEqual(venta.status_code, 201)
        self.assertEqual(venta.data['subtotal'], 200)
        self.assertAlmostEqual(venta.data['total'], 232, places=2)  # +16% IVA por defecto

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.stock, 3)

        id_venta = venta.data['id_venta']
        pago = self.client.post(
            f'/api/ventas/{id_venta}/pagos/',
            {'metodo_pago': 'efectivo', 'monto': venta.data['total']},
            format='json',
        )
        self.assertEqual(pago.status_code, 201)

        cerrar = self.client.post('/api/turnos/cerrar/', {'monto_contado': 732}, format='json')
        self.assertEqual(cerrar.status_code, 200)
        self.assertEqual(cerrar.data['estado'], 'cerrado')
        self.assertAlmostEqual(cerrar.data['monto_esperado'], 732, places=2)
        self.assertAlmostEqual(cerrar.data['diferencia'], 0, places=2)

    def test_venta_con_stock_insuficiente_falla_y_no_descuenta(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')

        response = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 999}]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.stock, 5)

    def test_rol_sin_permiso_no_puede_vender(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')

        self.login('bodeguero@demo.com')
        response = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        self.assertEqual(response.status_code, 403)

    def test_pago_no_puede_exceder_el_total_de_la_venta(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        id_venta = venta.data['id_venta']

        response = self.client.post(
            f'/api/ventas/{id_venta}/pagos/',
            {'metodo_pago': 'efectivo', 'monto': venta.data['total'] + 100},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_vendedor_no_puede_ver_venta_de_otro_vendedor(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        id_venta = venta.data['id_venta']

        otro_vendedor = crear_empleado('otro@demo.com', 'Vendedor', self.sucursal)
        self.login('otro@demo.com')
        response = self.client.get(f'/api/ventas/{id_venta}/')
        self.assertEqual(response.status_code, 404)

    def test_gerente_si_puede_ver_venta_de_cualquier_vendedor(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        id_venta = venta.data['id_venta']

        self.login('gerente@demo.com')
        response = self.client.get(f'/api/ventas/{id_venta}/')
        self.assertEqual(response.status_code, 200)

    def test_no_puede_abrir_dos_turnos_a_la_vez(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        segundo = self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        self.assertEqual(segundo.status_code, 400)

    def test_no_puede_cerrar_turno_sin_abrir(self):
        self.login('vendedor@demo.com')
        response = self.client.post('/api/turnos/cerrar/', {'monto_contado': 500}, format='json')
        self.assertEqual(response.status_code, 400)
