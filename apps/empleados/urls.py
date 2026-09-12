from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('roles/', views.RolListView.as_view(), name='roles'),
    path('empleados/', views.EmpleadoListCreateView.as_view(), name='empleados'),
    path('empleados/<int:id_empleado>/alternar-estado/', views.EmpleadoEstadoView.as_view(), name='empleado-alternar-estado'),
    path(
        'empleados/<int:id_empleado>/restablecer-password/',
        views.EmpleadoResetPasswordView.as_view(),
        name='empleado-restablecer-password',
    ),
    path('empleados/<int:id_empleado>/horario/', views.EmpleadoHorarioView.as_view(), name='empleado-horario'),
]
