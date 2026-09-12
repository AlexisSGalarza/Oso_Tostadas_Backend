import itertools
from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol
from apps.productos.models import Producto, ProductoSucursal
from apps.sucursales.models import Sucursal

from .models import Pago, Turno, Venta

_CONTADOR_NUMERO_EMPLEADO = itertools.count(800001)


def crear_empleado(correo, rol_nombre, sucursal, password='ClaveSegura1!'):
    rol, _ = Rol.objects.get_or_create(nombre_rol=rol_nombre)
    User = get_user_model()
    user = User.objects.create_user(username=correo, password=password)
    return Empleado.objects.create(
        nombre=correo.split('@')[0],
        numero_empleado=str(next(_CONTADOR_NUMERO_EMPLEADO)),
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
        numero_empleado = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_turno_actual_sin_turno_abierto_devuelve_204(self):
        self.login('vendedor@demo.com')
        response = self.client.get('/api/turnos/actual/')
        self.assertEqual(response.status_code, 204)

    def test_turno_actual_devuelve_el_turno_abierto_tras_relogin(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')

        # simula un logout/login sin cerrar turno (token nuevo, mismo turno abierto en el servidor)
        self.login('vendedor@demo.com')
        response = self.client.get('/api/turnos/actual/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'abierto')

    def test_listar_ventas_sobrevive_a_relogin_y_no_incluye_otros_turnos(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        self.client.post(
            f"/api/ventas/{venta.data['id_venta']}/pagos/",
            {'metodo_pago': 'tarjeta', 'monto': venta.data['total']},
            format='json',
        )

        # simula logout/login (token nuevo) a mitad del turno: el historial no debe perderse
        self.login('vendedor@demo.com')
        listado = self.client.get('/api/ventas/')
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(len(listado.data), 1)
        self.assertEqual(listado.data[0]['id_venta'], venta.data['id_venta'])
        self.assertEqual(listado.data[0]['pagos'][0]['metodo_pago'], 'tarjeta')
        self.assertIsNotNone(listado.data[0]['creado_en'])

    def test_listar_ventas_sin_turno_abierto_devuelve_vacio(self):
        self.login('vendedor@demo.com')
        response = self.client.get('/api/ventas/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

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

    def test_monto_esperado_solo_cuenta_ventas_en_efectivo(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')

        venta_efectivo = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )  # total 116
        self.client.post(
            f"/api/ventas/{venta_efectivo.data['id_venta']}/pagos/",
            {'metodo_pago': 'efectivo', 'monto': venta_efectivo.data['total']},
            format='json',
        )

        venta_tarjeta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )  # total 116
        self.client.post(
            f"/api/ventas/{venta_tarjeta.data['id_venta']}/pagos/",
            {'metodo_pago': 'tarjeta', 'monto': venta_tarjeta.data['total']},
            format='json',
        )

        cerrar = self.client.post('/api/turnos/cerrar/', {'monto_contado': 616}, format='json')
        self.assertEqual(cerrar.status_code, 200)
        # esperado en efectivo = 500 (inicial) + 116 (solo la venta en efectivo) = 616
        # la venta con tarjeta (116) no debe sumarse al efectivo esperado.
        self.assertAlmostEqual(cerrar.data['monto_esperado'], 616, places=2)
        self.assertAlmostEqual(cerrar.data['diferencia'], 0, places=2)

    def test_descargar_recibo_pdf(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        id_venta = venta.data['id_venta']
        self.client.post(
            f'/api/ventas/{id_venta}/pagos/', {'metodo_pago': 'efectivo', 'monto': venta.data['total']},
            format='json',
        )

        response = self.client.get(f'/api/ventas/{id_venta}/recibo/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_no_puede_descargar_recibo_de_venta_ajena(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 1}]}, format='json'
        )
        id_venta = venta.data['id_venta']

        otro = crear_empleado('otro-recibo@demo.com', 'Vendedor', self.sucursal)
        self.login('otro-recibo@demo.com')
        response = self.client.get(f'/api/ventas/{id_venta}/recibo/')
        self.assertEqual(response.status_code, 404)

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


class DevolucionesTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.vendedor = crear_empleado('vendedor@demo.com', 'Vendedor', self.sucursal)
        self.producto = Producto.objects.create(nombre='Chico', precio=100)
        self.stock = ProductoSucursal.objects.create(producto=self.producto, sucursal=self.sucursal, stock=5)

    def login(self, correo, password='ClaveSegura1!'):
        numero_empleado = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def abrir_turno_y_vender(self, unidades=3):
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        return self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': unidades}]},
            format='json',
        )

    def test_devolucion_repone_stock_y_calcula_monto_con_iva(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=3)
        id_venta = venta.data['id_venta']
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.stock, 2)  # 5 - 3

        devolucion = self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 2}]},
            format='json',
        )
        self.assertEqual(devolucion.status_code, 201)
        self.assertAlmostEqual(devolucion.data['monto'], 232, places=2)  # 2*100 * 1.16

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.stock, 4)  # 2 + 2 repuestas

    def test_no_puede_devolver_mas_de_lo_vendido(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=2)
        id_venta = venta.data['id_venta']

        response = self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 3}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_no_puede_devolver_dos_veces_las_mismas_unidades(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=2)
        id_venta = venta.data['id_venta']

        primera = self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 2}]},
            format='json',
        )
        self.assertEqual(primera.status_code, 201)

        segunda = self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]},
            format='json',
        )
        self.assertEqual(segunda.status_code, 400)

    def test_devolucion_se_resta_del_monto_esperado_al_cerrar_turno(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=2)  # total = 232
        id_venta = venta.data['id_venta']
        self.client.post(
            f'/api/ventas/{id_venta}/pagos/', {'metodo_pago': 'efectivo', 'monto': venta.data['total']},
            format='json',
        )
        self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]},
            format='json',
        )  # devuelve 116

        cierre = self.client.post('/api/turnos/cerrar/', {'monto_contado': 616}, format='json')
        self.assertEqual(cierre.status_code, 200)
        # esperado = 500 (inicial) + 232 (venta) - 116 (devolucion) = 616
        self.assertAlmostEqual(cierre.data['monto_esperado'], 616, places=2)
        self.assertAlmostEqual(cierre.data['diferencia'], 0, places=2)

    def test_venta_lista_incluye_sus_devoluciones(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=2)
        id_venta = venta.data['id_venta']
        self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]},
            format='json',
        )

        listado = self.client.get('/api/ventas/')
        self.assertEqual(len(listado.data[0]['devoluciones']), 1)
        self.assertEqual(listado.data[0]['devoluciones'][0]['detalles'][0]['cantidad'], 1)

    def test_vendedor_no_puede_devolver_venta_de_otro_vendedor(self):
        self.login('vendedor@demo.com')
        venta = self.abrir_turno_y_vender(unidades=2)
        id_venta = venta.data['id_venta']

        otro = crear_empleado('otro@demo.com', 'Vendedor', self.sucursal)
        self.login('otro@demo.com')
        response = self.client.post(
            f'/api/ventas/{id_venta}/devoluciones/',
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]},
            format='json',
        )
        self.assertEqual(response.status_code, 404)


class ReportesYDashboardTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.vendedor = crear_empleado('vendedor@demo.com', 'Vendedor', self.sucursal)
        self.admin = crear_empleado('admin@demo.com', 'Admin', self.sucursal)
        self.producto = Producto.objects.create(nombre='Chico', precio=100)
        self.stock = ProductoSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal, stock=5, stock_minimo=10,
        )

    def login(self, correo, password='ClaveSegura1!'):
        numero_empleado = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendedor_no_puede_ver_reportes_ni_dashboard(self):
        self.login('vendedor@demo.com')
        self.assertEqual(self.client.get('/api/reportes/semana/').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/dashboard/').status_code, 403)

    def test_reporte_semana_incluye_la_venta_de_hoy(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 2}]}, format='json'
        )

        self.login('admin@demo.com')
        response = self.client.get('/api/reportes/semana/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['dias']), 7)
        self.assertAlmostEqual(response.data['dias'][-1]['ventas'], 232, places=2)
        self.assertEqual(response.data['dias'][-1]['tickets'], 1)
        self.assertEqual(response.data['productos'][0]['nombre'], 'Chico')
        self.assertEqual(response.data['productos'][0]['cantidad'], 2)

    def test_dashboard_incluye_turno_abierto_y_alerta_de_stock_bajo(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')

        self.login('admin@demo.com')
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['resumen']['turnos_activos'], 1)
        self.assertEqual(len(response.data['turnos']), 1)
        self.assertEqual(response.data['turnos'][0]['empleado'], 'vendedor')
        self.assertTrue(any('Chico' in p['texto'] for p in response.data['pendientes']))

    def test_dashboard_alerta_faltante_en_corte(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        self.client.post('/api/turnos/cerrar/', {'monto_contado': 400}, format='json')

        self.login('admin@demo.com')
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.data['resumen']['cortes_por_revisar'], 1)
        self.assertTrue(any('faltante' in p['texto'] for p in response.data['pendientes']))

    def test_dashboard_puede_consultar_un_dia_anterior(self):
        from datetime import timedelta
        from django.utils import timezone as tz

        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        turno = Turno.objects.get(empleado__correo='vendedor@demo.com', estado='abierto')
        ayer = tz.localdate() - timedelta(days=1)
        turno.fecha = ayer
        turno.save(update_fields=['fecha'])

        self.login('admin@demo.com')
        hoy_response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(len(hoy_response.data['turnos']), 0)
        self.assertTrue(hoy_response.data['es_hoy'])

        ayer_response = self.client.get(f'/api/admin/dashboard/?fecha={ayer.isoformat()}')
        self.assertEqual(len(ayer_response.data['turnos']), 1)
        self.assertFalse(ayer_response.data['es_hoy'])
        self.assertEqual(ayer_response.data['fecha'], ayer.isoformat())

    def test_dashboard_fecha_invalida_da_400(self):
        self.login('admin@demo.com')
        response = self.client.get('/api/admin/dashboard/?fecha=no-es-una-fecha')
        self.assertEqual(response.status_code, 400)


class AdminTurnoDetalleTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.otra_sucursal = Sucursal.objects.create(nombre='Norte', direccion='Av. 2')
        self.vendedor = crear_empleado('vendedor@demo.com', 'Vendedor', self.sucursal)
        self.admin = crear_empleado('admin@demo.com', 'Admin', self.sucursal)
        self.admin_otra = crear_empleado('admin-norte@demo.com', 'Admin', self.otra_sucursal)
        self.producto = Producto.objects.create(nombre='Chico', precio=100)
        self.stock = ProductoSucursal.objects.create(producto=self.producto, sucursal=self.sucursal, stock=5)

    def login(self, correo, password='ClaveSegura1!'):
        numero_empleado = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendedor_no_puede_ver_turno_detalle_admin(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        id_turno = self.client.get('/api/turnos/actual/').data['id_turno']
        response = self.client.get(f'/api/admin/turnos/{id_turno}/')
        self.assertEqual(response.status_code, 403)

    def test_admin_ve_ventas_del_turno_de_cualquier_vendedor(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        id_turno = self.client.get('/api/turnos/actual/').data['id_turno']
        self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 2}]}, format='json'
        )

        self.login('admin@demo.com')
        response = self.client.get(f'/api/admin/turnos/{id_turno}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['empleado_nombre'], 'vendedor')
        self.assertEqual(len(response.data['ventas']), 1)

    def test_admin_puede_devolver_sobre_venta_de_otro_turno(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        venta = self.client.post(
            '/api/ventas/', {'detalles': [{'id_producto': self.producto.id_producto, 'unidades': 2}]}, format='json'
        )

        self.login('admin@demo.com')
        response = self.client.post(
            f"/api/ventas/{venta.data['id_venta']}/devoluciones/",
            {'detalles': [{'id_producto': self.producto.id_producto, 'cantidad': 1}]},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_admin_no_ve_turno_de_otra_sucursal(self):
        self.login('vendedor@demo.com')
        self.client.post('/api/turnos/abrir/', {'monto_inicial': 500}, format='json')
        id_turno = self.client.get('/api/turnos/actual/').data['id_turno']

        self.login('admin-norte@demo.com')
        response = self.client.get(f'/api/admin/turnos/{id_turno}/')
        self.assertEqual(response.status_code, 404)
