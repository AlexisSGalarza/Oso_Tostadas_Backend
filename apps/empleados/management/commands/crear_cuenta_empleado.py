from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password

from apps.empleados.models import Empleado


class Command(BaseCommand):
    help = 'Crea o actualiza la cuenta de acceso (usuario y password) de un empleado existente.'

    def add_arguments(self, parser):
        parser.add_argument('id_empleado', type=int)
        parser.add_argument('password')

    def handle(self, *args, **options):
        try:
            empleado = Empleado.objects.get(pk=options['id_empleado'])
        except Empleado.DoesNotExist:
            raise CommandError(f"No existe el empleado con id {options['id_empleado']}.")

        password = options['password']
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('\n'.join(exc.messages))

        User = get_user_model()
        username = empleado.correo.strip().lower()
        user, _ = User.objects.get_or_create(username=username, defaults={'email': username})
        user.email = username
        user.set_password(password)
        user.save()

        empleado.usuario = user
        empleado.save(update_fields=['usuario'])

        self.stdout.write(
            self.style.SUCCESS(f'Cuenta creada/actualizada para {empleado.nombre} ({username}).')
        )
