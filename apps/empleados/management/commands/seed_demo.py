from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.empleados.models import Empleado, Rol
from apps.productos.models import Producto, ProductoSucursal
from apps.sucursales.models import Sucursal

PRODUCTOS_DEMO = [
    ('Paquete chico (10 pzas)', 25.0, 50),
    ('Paquete mediano (20 pzas)', 45.0, 50),
    ('Paquete grande (50 pzas)', 100.0, 30),
    ('Paquete familiar (100 pzas)', 180.0, 20),
]


class Command(BaseCommand):
    help = 'Crea datos de demo (sucursal, roles, productos con stock y un empleado por rol) para probar la API/front localmente.'

    def handle(self, *args, **options):
        sucursal, _ = Sucursal.objects.get_or_create(
            nombre='Sucursal Centro',
            defaults={'direccion': 'Av. Principal 123', 'telefono': '555-0100'},
        )

        rol_vendedor, _ = Rol.objects.get_or_create(nombre_rol='Vendedor')
        rol_admin, _ = Rol.objects.get_or_create(nombre_rol='Admin')

        for nombre, precio, stock in PRODUCTOS_DEMO:
            producto, _ = Producto.objects.get_or_create(
                nombre=nombre, defaults={'precio': precio}
            )
            ProductoSucursal.objects.get_or_create(
                producto=producto, sucursal=sucursal, defaults={'stock': stock}
            )

        User = get_user_model()

        def crear_empleado_con_acceso(nombre, correo, password, rol):
            empleado, _ = Empleado.objects.get_or_create(
                correo=correo,
                defaults={
                    'nombre': nombre,
                    'fecha_ingreso': date.today(),
                    'rol': rol,
                    'sucursal': sucursal,
                },
            )
            user, _ = User.objects.get_or_create(username=correo, defaults={'email': correo})
            user.set_password(password)
            user.save()
            empleado.usuario = user
            empleado.save(update_fields=['usuario'])
            return empleado

        crear_empleado_con_acceso('María Vendedora', 'vendedor@osotostadas.demo', 'Demo1234!', rol_vendedor)
        crear_empleado_con_acceso('Carlos Admin', 'admin@osotostadas.demo', 'Demo1234!', rol_admin)

        self.stdout.write(self.style.SUCCESS(
            'Datos de demo listos:\n'
            '  vendedor@osotostadas.demo / Demo1234!\n'
            '  admin@osotostadas.demo / Demo1234!'
        ))
