from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol
from apps.sucursales.models import Sucursal

from .models import Producto, ProductoSucursal


class CatalogoTests(APITestCase):
    def setUp(self):
        cache.clear()  # el throttle de login usa el cache; evita arrastrar el contador entre tests
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.otra_sucursal = Sucursal.objects.create(nombre='Norte', direccion='Av. 2')
        rol = Rol.objects.create(nombre_rol='Vendedor')
        User = get_user_model()
        user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        self.empleado = Empleado.objects.create(
            nombre='Ana', correo='vendedor@demo.com', fecha_ingreso=date.today(),
            rol=rol, sucursal=self.sucursal, usuario=user,
        )

        self.producto_activo = Producto.objects.create(nombre='Chico', precio=25)
        self.producto_inactivo = Producto.objects.create(nombre='Descontinuado', precio=10, estado='inactivo')
        ProductoSucursal.objects.create(producto=self.producto_activo, sucursal=self.sucursal, stock=50)
        ProductoSucursal.objects.create(producto=self.producto_inactivo, sucursal=self.sucursal, stock=5)

        producto_otra_sucursal = Producto.objects.create(nombre='Solo en Norte', precio=99)
        ProductoSucursal.objects.create(producto=producto_otra_sucursal, sucursal=self.otra_sucursal, stock=10)

        login = self.client.post('/api/auth/login/', {'correo': 'vendedor@demo.com', 'password': 'ClaveSegura1!'})
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
