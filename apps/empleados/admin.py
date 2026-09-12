from django.contrib import admin

from .models import Empleado, Rol

admin.site.register(Rol)
admin.site.register(Empleado)
