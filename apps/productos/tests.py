from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol
from apps.sucursales.models import Sucursal

from .models import Insumo, InsumoSucursal, Producto, ProductoSucursal, Proveedor


class CatalogoTests(APITestCase):
    def setUp(self):
        cache.clear()  # el throttle de login usa el cache; evita arrastrar el contador entre tests
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.otra_sucursal = Sucursal.objects.create(nombre='Norte', direccion='Av. 2')
        rol = Rol.objects.create(nombre_rol='Vendedor')
        User = get_user_model()
        user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        self.empleado = Empleado.objects.create(
            nombre='Ana', numero_empleado='800001', correo='vendedor@demo.com', fecha_ingreso=date.today(),
            rol=rol, sucursal=self.sucursal, usuario=user,
        )

        self.producto_activo = Producto.objects.create(nombre='Chico', precio=25)
        self.producto_inactivo = Producto.objects.create(nombre='Descontinuado', precio=10, estado='inactivo')
        ProductoSucursal.objects.create(producto=self.producto_activo, sucursal=self.sucursal, stock=50)
        ProductoSucursal.objects.create(producto=self.producto_inactivo, sucursal=self.sucursal, stock=5)

        producto_otra_sucursal = Producto.objects.create(nombre='Solo en Norte', precio=99)
        ProductoSucursal.objects.create(producto=producto_otra_sucursal, sucursal=self.otra_sucursal, stock=10)

        login = self.client.post('/api/auth/login/', {'numero_empleado': '800001', 'password': 'ClaveSegura1!'})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def test_requiere_autenticacion(self):
        self.client.credentials()
        response = self.client.get('/api/productos/')
        self.assertEqual(response.status_code, 401)

    def test_solo_muestra_activos_de_la_propia_sucursal(self):
        response = self.client.get('/api/productos/')
        self.assertEqual(response.status_code, 200)
        nombres = {p['nombre'] for p in response.data}
        self.assertEqual(nombres, {'Chico'})


class InventarioAdminTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        rol_admin = Rol.objects.create(nombre_rol='Admin')
        rol_vendedor = Rol.objects.create(nombre_rol='Vendedor')
        User = get_user_model()

        admin_user = User.objects.create_user(username='admin@demo.com', password='ClaveSegura1!')
        Empleado.objects.create(
            nombre='Carlos', numero_empleado='800002', correo='admin@demo.com', fecha_ingreso=date.today(),
            rol=rol_admin, sucursal=self.sucursal, usuario=admin_user,
        )
        vendedor_user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        Empleado.objects.create(
            nombre='Ana', numero_empleado='800001', correo='vendedor@demo.com', fecha_ingreso=date.today(),
            rol=rol_vendedor, sucursal=self.sucursal, usuario=vendedor_user,
        )

        self.producto = Producto.objects.create(nombre='Chico', precio=25)
        self.stock_producto = ProductoSucursal.objects.create(
            producto=self.producto, sucursal=self.sucursal, stock=10, stock_minimo=20,
        )
        self.insumo = Insumo.objects.create(nombre='Masa', unidad_medida='kg')
        self.stock_insumo = InsumoSucursal.objects.create(
            insumo=self.insumo, sucursal=self.sucursal, stock=5, stock_minimo=25,
        )
        self.proveedor = Proveedor.objects.create(nombre='Molino La Espiga', insumo_principal='Masa de maiz')

    def login(self, numero_empleado, password='ClaveSegura1!'):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendedor_no_puede_ver_inventario_admin(self):
        self.login('800001')
        response = self.client.get('/api/admin/productos/')
        self.assertEqual(response.status_code, 403)

    def test_admin_lista_productos_con_minimo(self):
        self.login('800002')
        response = self.client.get('/api/admin/productos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['stock'], 10)
        self.assertEqual(response.data[0]['stock_minimo'], 20)

    def test_registrar_produccion_suma_stock(self):
        self.login('800002')
        response = self.client.post(
            f'/api/admin/productos/{self.producto.id_producto}/produccion/', {'cantidad': 15}, format='json'
        )
        self.assertEqual(response.status_code, 201)
        self.stock_producto.refresh_from_db()
        self.assertEqual(self.stock_producto.stock, 25)

    def test_admin_lista_insumos(self):
        self.login('800002')
        response = self.client.get('/api/admin/insumos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['nombre'], 'Masa')
        self.assertIsNone(response.data[0]['proveedor'])

    def test_registrar_entrada_suma_stock_y_asigna_proveedor_principal(self):
        self.login('800002')
        response = self.client.post(
            f'/api/admin/insumos/{self.insumo.id_insumo}/entrada/',
            {'cantidad': 30, 'id_proveedor': self.proveedor.id_proveedor},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.stock_insumo.refresh_from_db()
        self.assertEqual(self.stock_insumo.stock, 35)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.proveedor_principal_id, self.proveedor.id_proveedor)

    def test_crear_insumo_nuevo_con_stock_inicial(self):
        self.login('800002')
        response = self.client.post(
            '/api/admin/insumos/',
            {
                'nombre': 'Queso',
                'unidad_medida': 'kg',
                'id_proveedor': self.proveedor.id_proveedor,
                'stock_minimo': 10,
                'stock_inicial': 20,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['nombre'], 'Queso')
        self.assertEqual(response.data['stock'], 20)
        self.assertEqual(response.data['stock_minimo'], 10)
        self.assertEqual(response.data['id_proveedor'], self.proveedor.id_proveedor)

        nuevo_insumo = Insumo.objects.get(nombre='Queso')
        self.assertTrue(InsumoSucursal.objects.filter(insumo=nuevo_insumo, sucursal=self.sucursal).exists())

    def test_vendedor_no_puede_crear_insumo(self):
        self.login('800001')
        response = self.client.post('/api/admin/insumos/', {'nombre': 'Queso', 'unidad_medida': 'kg'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_listar_y_crear_proveedores(self):
        self.login('800002')
        listado = self.client.get('/api/proveedores/')
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(len(listado.data), 1)

        creado = self.client.post(
            '/api/proveedores/',
            {'nombre': 'Aceites del Bajio', 'insumo_principal': 'Aceite vegetal'},
            format='json',
        )
        self.assertEqual(creado.status_code, 201)
        self.assertEqual(creado.data['estado'], 'activo')

    def test_alternar_estado_proveedor(self):
        self.login('800002')
        response = self.client.post(f'/api/proveedores/{self.proveedor.id_proveedor}/alternar-estado/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'inactivo')

    def test_proveedor_es_urgente_si_su_insumo_esta_bajo_el_minimo(self):
        self.login('800002')
        # antes de asociarlo al insumo con stock bajo, no deberia salir urgente
        sin_asociar = self.client.get('/api/proveedores/')
        self.assertFalse(sin_asociar.data[0]['urgente'])

        self.insumo.proveedor_principal = self.proveedor
        self.insumo.save(update_fields=['proveedor_principal'])

        response = self.client.get('/api/proveedores/')
        self.assertTrue(response.data[0]['urgente'])

        self.stock_insumo.stock = 100
        self.stock_insumo.save(update_fields=['stock'])
        response = self.client.get('/api/proveedores/')
        self.assertFalse(response.data[0]['urgente'])
