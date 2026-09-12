from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.sucursales.models import Sucursal

from .models import Empleado, Rol


class AuthFlowTests(APITestCase):
    def setUp(self):
        cache.clear()  # el throttle de login usa el cache; evita arrastrar el contador entre tests
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.rol = Rol.objects.create(nombre_rol='Vendedor')
        User = get_user_model()
        self.user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        self.empleado = Empleado.objects.create(
            nombre='Ana',
            correo='vendedor@demo.com',
            fecha_ingreso=date.today(),
            rol=self.rol,
            sucursal=self.sucursal,
            usuario=self.user,
        )

    def test_login_correcto_devuelve_tokens(self):
        response = self.client.post(
            '/api/auth/login/', {'correo': 'vendedor@demo.com', 'password': 'ClaveSegura1!'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_password_incorrecto_falla(self):
        response = self.client.post(
            '/api/auth/login/', {'correo': 'vendedor@demo.com', 'password': 'incorrecta'}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_empleado_inactivo_falla(self):
        self.empleado.estado = 'inactivo'
        self.empleado.save(update_fields=['estado'])
        response = self.client.post(
            '/api/auth/login/', {'correo': 'vendedor@demo.com', 'password': 'ClaveSegura1!'}
        )
        self.assertEqual(response.status_code, 401)

    def test_me_requiere_autenticacion(self):
        response = self.client.get('/api/me/')
        self.assertEqual(response.status_code, 401)

    def test_me_devuelve_datos_del_empleado_autenticado(self):
        login = self.client.post(
            '/api/auth/login/', {'correo': 'vendedor@demo.com', 'password': 'ClaveSegura1!'}
        )
        access = login.data['access']
        response = self.client.get('/api/me/', HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['correo'], 'vendedor@demo.com')
        self.assertEqual(response.data['rol'], 'Vendedor')
