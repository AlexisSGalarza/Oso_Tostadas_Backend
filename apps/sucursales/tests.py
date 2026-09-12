from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol

from .models import Sucursal


class SucursalMiaTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1', fondo_caja_default=500)
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

    def login(self, correo, password='ClaveSegura1!'):
        numero_empleado = Empleado.objects.get(correo=correo).numero_empleado
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_cualquier_empleado_activo_puede_leer_su_sucursal(self):
        self.login('vendedor@demo.com')
        response = self.client.get('/api/sucursales/mia/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['fondo_caja_default'], 500)

    def test_vendedor_no_puede_editar_la_sucursal(self):
        self.login('vendedor@demo.com')
        response = self.client.patch('/api/sucursales/mia/', {'nombre': 'Otro nombre'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_admin_puede_editar_su_sucursal(self):
        self.login('admin@demo.com')
        response = self.client.patch(
            '/api/sucursales/mia/',
            {'nombre': 'Sucursal Centro', 'direccion': 'Nueva 123', 'fondo_caja_default': 800,
             'hora_apertura': '08:00', 'hora_cierre': '20:00'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.sucursal.refresh_from_db()
        self.assertEqual(self.sucursal.direccion, 'Nueva 123')
        self.assertEqual(self.sucursal.fondo_caja_default, 800)
