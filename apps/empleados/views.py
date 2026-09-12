from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import TieneEmpleadoActivo
from .serializers import EmpleadoMeSerializer, LoginSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ {correo, password} -> {access, refresh}."""

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get(self, request):
        return Response(EmpleadoMeSerializer(request.user.empleado).data)
