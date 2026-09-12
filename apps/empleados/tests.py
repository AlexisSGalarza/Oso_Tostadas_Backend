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
            numero_empleado='800001',
            correo='vendedor@demo.com',
            fecha_ingreso=date.today(),
            rol=self.rol,
            sucursal=self.sucursal,
            usuario=self.user,
        )

    def test_login_correcto_devuelve_tokens(self):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': '800001', 'password': 'ClaveSegura1!'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_password_incorrecto_falla(self):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': '800001', 'password': 'incorrecta'}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_numero_empleado_inexistente_falla(self):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': '999999', 'password': 'ClaveSegura1!'}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_empleado_inactivo_falla(self):
        self.empleado.estado = 'inactivo'
        self.empleado.save(update_fields=['estado'])
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': '800001', 'password': 'ClaveSegura1!'}
        )
        self.assertEqual(response.status_code, 401)

    def test_me_requiere_autenticacion(self):
        response = self.client.get('/api/me/')
        self.assertEqual(response.status_code, 401)

    def test_me_devuelve_datos_del_empleado_autenticado(self):
        login = self.client.post(
            '/api/auth/login/', {'numero_empleado': '800001', 'password': 'ClaveSegura1!'}
        )
        access = login.data['access']
        response = self.client.get('/api/me/', HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['correo'], 'vendedor@demo.com')
        self.assertEqual(response.data['numero_empleado'], '800001')
        self.assertEqual(response.data['rol'], 'Vendedor')


class GestionEmpleadosTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        self.otra_sucursal = Sucursal.objects.create(nombre='Norte', direccion='Av. 2')
        self.rol_vendedor = Rol.objects.create(nombre_rol='Vendedor')
        self.rol_admin = Rol.objects.create(nombre_rol='Admin')

        User = get_user_model()
        self.admin_user = User.objects.create_user(username='admin@demo.com', password='ClaveSegura1!')
        self.admin = Empleado.objects.create(
            nombre='Carlos', numero_empleado='800002', correo='admin@demo.com', fecha_ingreso=date.today(),
            rol=self.rol_admin, sucursal=self.sucursal, usuario=self.admin_user,
        )
        self.vendedor_user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        self.vendedor = Empleado.objects.create(
            nombre='Ana', numero_empleado='800001', correo='vendedor@demo.com', fecha_ingreso=date.today(),
            rol=self.rol_vendedor, sucursal=self.sucursal, usuario=self.vendedor_user,
        )

    def login(self, numero_empleado, password='ClaveSegura1!'):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendedor_no_puede_listar_empleados(self):
        self.login('800001')
        response = self.client.get('/api/empleados/')
        self.assertEqual(response.status_code, 403)

    def test_admin_lista_solo_su_sucursal(self):
        Empleado.objects.create(
            nombre='De otra sucursal', numero_empleado='900001', correo='otra@demo.com',
            fecha_ingreso=date.today(), rol=self.rol_vendedor, sucursal=self.otra_sucursal,
        )
        self.login('800002')
        response = self.client.get('/api/empleados/')
        self.assertEqual(response.status_code, 200)
        correos = {e['correo'] for e in response.data}
        self.assertEqual(correos, {'admin@demo.com', 'vendedor@demo.com'})

    def test_admin_crea_empleado_y_puede_iniciar_sesion_con_password_temporal(self):
        self.login('800002')
        response = self.client.post(
            '/api/empleados/',
            {'nombre': 'Nuevo Vendedor', 'correo': 'nuevo@demo.com', 'telefono': '555', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('password_temporal', response.data)
        self.assertTrue(response.data['numero_empleado'])
        numero_empleado = response.data['numero_empleado']
        password = response.data['password_temporal']

        self.client.credentials()
        login = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.assertEqual(login.status_code, 200)

    def test_admin_puede_elegir_la_password_en_vez_de_generarla(self):
        self.login('800002')
        response = self.client.post(
            '/api/empleados/',
            {
                'nombre': 'Con Password Propia', 'correo': 'propia@demo.com',
                'id_rol': self.rol_vendedor.id_rol, 'password': 'UnaClaveValida1!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password_temporal', response.data)
        numero_empleado = response.data['numero_empleado']

        self.client.credentials()
        login = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': 'UnaClaveValida1!'}
        )
        self.assertEqual(login.status_code, 200)

    def test_no_acepta_una_password_demasiado_debil(self):
        self.login('800002')
        response = self.client.post(
            '/api/empleados/',
            {
                'nombre': 'Password Debil', 'correo': 'debil@demo.com',
                'id_rol': self.rol_vendedor.id_rol, 'password': '123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_numeros_de_empleado_son_consecutivos(self):
        self.login('800002')
        primero = self.client.post(
            '/api/empleados/',
            {'nombre': 'Uno', 'correo': 'uno@demo.com', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )
        segundo = self.client.post(
            '/api/empleados/',
            {'nombre': 'Dos', 'correo': 'dos@demo.com', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )
        self.assertEqual(
            int(segundo.data['numero_empleado']), int(primero.data['numero_empleado']) + 1
        )

    def test_no_puede_crear_dos_empleados_con_el_mismo_correo(self):
        self.login('800002')
        response = self.client.post(
            '/api/empleados/',
            {'nombre': 'Duplicado', 'correo': 'vendedor@demo.com', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_alternar_estado_desactiva_y_reactiva(self):
        self.login('800002')
        response = self.client.post(f'/api/empleados/{self.vendedor.id_empleado}/alternar-estado/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'inactivo')

        response = self.client.post(f'/api/empleados/{self.vendedor.id_empleado}/alternar-estado/')
        self.assertEqual(response.data['estado'], 'activo')

    def test_restablecer_password_permite_iniciar_sesion_con_la_nueva(self):
        self.login('800002')
        response = self.client.post(f'/api/empleados/{self.vendedor.id_empleado}/restablecer-password/')
        self.assertEqual(response.status_code, 200)
        nueva_password = response.data['password_temporal']

        self.client.credentials()
        login = self.client.post(
            '/api/auth/login/', {'numero_empleado': '800001', 'password': nueva_password}
        )
        self.assertEqual(login.status_code, 200)

    def test_roles_disponibles_para_cualquier_empleado_autenticado(self):
        self.login('800001')
        response = self.client.get('/api/roles/')
        self.assertEqual(response.status_code, 200)
        nombres = {r['nombre_rol'] for r in response.data}
        self.assertEqual(nombres, {'Vendedor', 'Admin'})

    def test_admin_asigna_horario_a_un_empleado(self):
        self.login('800002')
        response = self.client.patch(
            f'/api/empleados/{self.vendedor.id_empleado}/horario/',
            {'horario_dias': 'Lunes a Viernes', 'horario_hora_inicio': '08:00', 'horario_hora_fin': '16:00'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['horario_dias'], 'Lunes a Viernes')
        self.assertEqual(response.data['horario_hora_inicio'], '08:00:00')
        self.assertEqual(response.data['horario_hora_fin'], '16:00:00')

        self.vendedor.refresh_from_db()
        self.assertEqual(self.vendedor.horario_dias, 'Lunes a Viernes')

    def test_vendedor_no_puede_asignar_horarios(self):
        self.login('800001')
        response = self.client.patch(
            f'/api/empleados/{self.vendedor.id_empleado}/horario/',
            {'horario_dias': 'Lunes a Viernes'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_asignar_horario_queda_auditado(self):
        self.login('800002')
        self.client.patch(
            f'/api/empleados/{self.vendedor.id_empleado}/horario/',
            {'horario_dias': 'Fines de semana'},
            format='json',
        )
        response = self.client.get('/api/auditoria/')
        acciones = [r['accion'] for r in response.data]
        self.assertIn('empleado.horario', acciones)
