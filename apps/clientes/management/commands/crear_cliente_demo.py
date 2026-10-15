from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.clientes.models import Cliente

CORREO = 'cliente@demo.com'
PASSWORD = 'Demo1234!'


class Command(BaseCommand):
    help = 'Crea (o reinicia la contraseña de) la cuenta de cliente de prueba para facturar.'

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        usuario, _ = User.objects.get_or_create(username=CORREO)
        usuario.set_password(PASSWORD)
        usuario.is_active = True
        usuario.save()
        cliente, creado = Cliente.objects.get_or_create(
            usuario=usuario, defaults={'nombre': 'Cliente de Prueba', 'correo': CORREO}
        )
        estado = 'creada' if creado else 'ya existía; se reinició la contraseña'
        self.stdout.write(self.style.SUCCESS(f'Cuenta de cliente {estado}: {CORREO} / {PASSWORD}'))
