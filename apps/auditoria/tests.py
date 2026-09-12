from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.empleados.models import Empleado, Rol
from apps.productos.models import Proveedor
from apps.sucursales.models import Sucursal

from .models import RegistroAuditoria


class AuditoriaTestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.sucursal = Sucursal.objects.create(nombre='Centro', direccion='Av. 1')
        rol_admin = Rol.objects.create(nombre_rol='Admin')
        rol_vendedor = Rol.objects.create(nombre_rol='Vendedor')
        User = get_user_model()

        admin_user = User.objects.create_user(username='admin@demo.com', password='ClaveSegura1!')
        self.admin = Empleado.objects.create(
            nombre='Carlos', numero_empleado='800002', correo='admin@demo.com', fecha_ingreso=date.today(),
            rol=rol_admin, sucursal=self.sucursal, usuario=admin_user,
        )
        vendedor_user = User.objects.create_user(username='vendedor@demo.com', password='ClaveSegura1!')
        self.vendedor = Empleado.objects.create(
            nombre='Ana', numero_empleado='800001', correo='vendedor@demo.com', fecha_ingreso=date.today(),
            rol=rol_vendedor, sucursal=self.sucursal, usuario=vendedor_user,
        )
        self.rol_vendedor = rol_vendedor

    def login(self, numero_empleado, password='ClaveSegura1!'):
        response = self.client.post(
            '/api/auth/login/', {'numero_empleado': numero_empleado, 'password': password}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendedor_no_puede_ver_auditoria(self):
        self.login('800001')
        response = self.client.get('/api/auditoria/')
        self.assertEqual(response.status_code, 403)

    def test_crear_empleado_queda_auditado(self):
        self.login('800002')
        self.client.post(
            '/api/empleados/',
            {'nombre': 'Nuevo', 'correo': 'nuevo@demo.com', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )
        response = self.client.get('/api/auditoria/')
        self.assertEqual(response.status_code, 200)
        acciones = [r['accion'] for r in response.data]
        self.assertIn('empleado.crear', acciones)
        self.assertEqual(response.data[0]['actor'], 'Carlos')

    def test_alternar_estado_empleado_queda_auditado(self):
        self.login('800002')
        self.client.post(f'/api/empleados/{self.vendedor.id_empleado}/alternar-estado/')
        response = self.client.get('/api/auditoria/')
        acciones = [r['accion'] for r in response.data]
        self.assertIn('empleado.alternar_estado', acciones)

    def test_restablecer_password_queda_auditado(self):
        self.login('800002')
        self.client.post(f'/api/empleados/{self.vendedor.id_empleado}/restablecer-password/')
        response = self.client.get('/api/auditoria/')
        acciones = [r['accion'] for r in response.data]
        self.assertIn('empleado.restablecer_password', acciones)

    def test_alternar_estado_proveedor_queda_auditado(self):
        proveedor = Proveedor.objects.create(nombre='Molino')
        self.login('800002')
        self.client.post(f'/api/proveedores/{proveedor.id_proveedor}/alternar-estado/')
        response = self.client.get('/api/auditoria/')
        acciones = [r['accion'] for r in response.data]
        self.assertIn('proveedor.alternar_estado', acciones)

    def test_auditoria_solo_incluye_la_propia_sucursal(self):
        otra_sucursal = Sucursal.objects.create(nombre='Norte', direccion='Av. 2')
        User = get_user_model()
        otro_admin_user = User.objects.create_user(username='admin2@demo.com', password='ClaveSegura1!')
        Empleado.objects.create(
            nombre='Otro Admin', numero_empleado='900002', correo='admin2@demo.com', fecha_ingreso=date.today(),
            rol=Rol.objects.get(nombre_rol='Admin'), sucursal=otra_sucursal, usuario=otro_admin_user,
        )
        RegistroAuditoria.objects.create(
            actor_id=None, accion='empleado.crear', detalle='de otra sucursal, sin actor',
        )

        self.login('900002')
        self.client.post(
            '/api/empleados/',
            {'nombre': 'De Norte', 'correo': 'denorte@demo.com', 'id_rol': self.rol_vendedor.id_rol},
            format='json',
        )

        self.login('800002')
        response = self.client.get('/api/auditoria/')
        detalles = [r['detalle'] for r in response.data]
        self.assertFalse(any('De Norte' in d for d in detalles))
