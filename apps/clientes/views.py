from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.facturacion.servicio import motivo_no_facturable
from apps.facturacion.views import _emitir_y_responder, _ticket_del_cliente
from apps.ventas.serializers import DetalleVentaSerializer

from .models import Cliente, TicketCliente
from .permissions import EsCliente
from .serializers import (
    AgregarTicketSerializer,
    ClienteSerializer,
    FacturarTicketSerializer,
    LoginClienteSerializer,
    RegistroClienteSerializer,
)

ES_CLIENTE = [permissions.IsAuthenticated, EsCliente]


def _tokens(usuario):
    refresh = RefreshToken.for_user(usuario)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class VistaAcceso(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class RegistroClienteView(VistaAcceso):
    """POST /api/clientes/registro/ {nombre, correo, password} - crea la cuenta y entra."""

    def post(self, request):
        serializer = RegistroClienteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        with transaction.atomic():
            usuario = get_user_model().objects.create_user(username=datos['correo'], password=datos['password'])
            cliente = Cliente.objects.create(usuario=usuario, nombre=datos['nombre'].strip(), correo=datos['correo'])
        return Response({**_tokens(usuario), 'cliente': ClienteSerializer(cliente).data}, status=status.HTTP_201_CREATED)


class LoginClienteView(VistaAcceso):
    """POST /api/clientes/login/ {correo, password}. Las cuentas del personal no entran por aqui."""

    def post(self, request):
        serializer = LoginClienteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correo = serializer.validated_data['correo'].strip().lower()
        usuario = authenticate(request, username=correo, password=serializer.validated_data['password'])
        if usuario is None or not hasattr(usuario, 'cliente') or not usuario.is_active:
            return Response({'detail': 'Correo o contraseña incorrectos.'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({**_tokens(usuario), 'cliente': ClienteSerializer(usuario.cliente).data})


class ClienteMeView(APIView):
    """GET /api/clientes/me/ - la cuenta y sus datos fiscales guardados."""

    permission_classes = ES_CLIENTE

    def get(self, request):
        return Response(ClienteSerializer(request.user.cliente).data)


def _ticket_data(ticket):
    venta = ticket.venta
    factura = getattr(venta, 'factura', None)
    return {
        'id_venta': venta.id_venta,
        'folio': venta.id_venta,
        'fecha': venta.fecha,
        'creado_en': venta.creado_en,
        'total': venta.total,
        'detalles': DetalleVentaSerializer(venta.detalles.all(), many=True).data,
        'agregado_en': ticket.agregado_en,
        'factura': (
            {
                'serie': factura.serie,
                'folio': factura.folio,
                'folio_fiscal': factura.folio_fiscal,
                'fecha_emision': factura.fecha_emision,
                'modo': factura.modo,
            }
            if factura
            else None
        ),
        'motivo_no_facturable': None if factura else motivo_no_facturable(venta),
    }


class TicketsClienteView(APIView):
    """GET /api/clientes/tickets/ lista sus tickets. POST {folio, total} agrega uno a su cuenta."""

    permission_classes = ES_CLIENTE

    def get(self, request):
        tickets = (
            TicketCliente.objects.filter(cliente=request.user.cliente)
            .select_related('venta__factura')
            .prefetch_related('venta__detalles__producto', 'venta__pagos')
        )
        return Response([_ticket_data(t) for t in tickets])

    def post(self, request):
        serializer = AgregarTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        venta = _ticket_del_cliente(serializer.validated_data['folio'], serializer.validated_data['total'])
        cliente = request.user.cliente
        existente = TicketCliente.objects.filter(venta=venta).select_related('cliente').first()
        if existente and existente.cliente_id != cliente.id_cliente:
            raise ValidationError('Ese ticket ya está registrado en otra cuenta. Si es tuyo, pide ayuda en caja.')
        ticket = existente or TicketCliente.objects.create(cliente=cliente, venta=venta)
        return Response(_ticket_data(ticket), status=status.HTTP_200_OK if existente else status.HTTP_201_CREATED)


class FacturarTicketClienteView(APIView):
    """POST /api/clientes/tickets/<id_venta>/factura/ - factura uno de sus tickets."""

    permission_classes = ES_CLIENTE

    def post(self, request, id_venta):
        cliente = request.user.cliente
        get_object_or_404(TicketCliente, cliente=cliente, venta_id=id_venta)
        serializer = FacturarTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)
        guardar = datos.pop('guardar')
        if not datos.get('correo'):
            datos['correo'] = cliente.correo

        respuesta = _emitir_y_responder(id_venta, datos)
        if respuesta.status_code == status.HTTP_201_CREATED and guardar:
            for campo in ('rfc', 'razon_social', 'codigo_postal', 'regimen_fiscal', 'uso_cfdi'):
                setattr(cliente, campo, datos[campo])
            cliente.save(update_fields=['rfc', 'razon_social', 'codigo_postal', 'regimen_fiscal', 'uso_cfdi'])
        return respuesta
