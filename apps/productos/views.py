from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import registrar as registrar_auditoria
from apps.empleados.permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido

from .etiquetas import construir_etiquetas_pdf
from .models import Insumo, InsumoSucursal, Producto, ProductoSucursal, Proveedor
from .serializers import (
    CodigoBarrasSerializer,
    EntradaInsumoSerializer,
    InsumoAdminSerializer,
    InsumoCreateSerializer,
    ProduccionSerializer,
    ProductoAdminSerializer,
    ProductoSucursalSerializer,
    ProveedorCreateSerializer,
    ProveedorSerializer,
)

ES_SUPERVISOR = [permissions.IsAuthenticated, TieneEmpleadoActivo, rol_requerido(*ROLES_SUPERVISOR)]


class ProductosDisponiblesView(generics.ListAPIView):
    """GET /api/productos/ - catalogo con stock de la sucursal del empleado autenticado."""

    serializer_class = ProductoSucursalSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get_queryset(self):
        empleado = self.request.user.empleado
        return (
            ProductoSucursal.objects.select_related('producto')
            .filter(sucursal=empleado.sucursal, producto__estado='activo')
            .order_by('producto__nombre')
        )


class ProductoAdminListView(generics.ListAPIView):
    """GET /api/admin/productos/ - inventario de productos terminados de tu sucursal (incluye inactivos)."""

    serializer_class = ProductoAdminSerializer
    permission_classes = ES_SUPERVISOR

    def get_queryset(self):
        sucursal = self.request.user.empleado.sucursal
        return (
            ProductoSucursal.objects.select_related('producto')
            .filter(sucursal=sucursal)
            .order_by('producto__nombre')
        )


class ProductoProduccionView(APIView):
    """POST /api/admin/productos/<id_producto>/produccion/ {cantidad} - suma paquetes recien empacados al stock."""

    permission_classes = ES_SUPERVISOR

    def post(self, request, id_producto):
        sucursal = request.user.empleado.sucursal
        producto = get_object_or_404(Producto, pk=id_producto)
        stock_row, _ = ProductoSucursal.objects.get_or_create(producto=producto, sucursal=sucursal)

        serializer = ProduccionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_row.stock += serializer.validated_data['cantidad']
        stock_row.save(update_fields=['stock'])

        return Response(ProductoAdminSerializer(stock_row).data, status=status.HTTP_201_CREATED)


class ProductoCodigoBarrasView(APIView):
    """PATCH /api/admin/productos/<id_producto>/codigo-barras/ {codigo_barras} - asigna o quita el codigo."""

    permission_classes = ES_SUPERVISOR

    def patch(self, request, id_producto):
        sucursal = request.user.empleado.sucursal
        stock_row = get_object_or_404(
            ProductoSucursal.objects.select_related('producto'), producto_id=id_producto, sucursal=sucursal
        )
        serializer = CodigoBarrasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codigo = serializer.validated_data['codigo_barras'] or None

        producto = stock_row.producto
        if codigo:
            repetido = Producto.objects.filter(codigo_barras=codigo).exclude(pk=producto.pk).first()
            if repetido:
                raise ValidationError(f'Ese código ya está asignado a "{repetido.nombre}".')
        producto.codigo_barras = codigo
        producto.save(update_fields=['codigo_barras'])

        registrar_auditoria(
            request.user.empleado, 'producto.codigo_barras',
            f'{"Asigno el codigo " + codigo + " a" if codigo else "Quito el codigo de barras de"} {producto.nombre}.',
        )
        return Response(ProductoAdminSerializer(stock_row).data)


class ProductoEtiquetasView(APIView):
    """GET /api/admin/productos/etiquetas/?copias=N - PDF con las etiquetas de codigo de barras para imprimir."""

    permission_classes = ES_SUPERVISOR

    def get(self, request):
        sucursal = request.user.empleado.sucursal
        try:
            copias = min(max(int(request.query_params.get('copias', 1)), 1), 21)
        except ValueError:
            raise ValidationError('El número de copias no es válido.')
        productos = list(
            Producto.objects.filter(
                stock_sucursales__sucursal=sucursal, estado='activo', codigo_barras__isnull=False
            ).order_by('nombre')
        )
        if not productos:
            raise ValidationError('Ningún producto tiene código de barras todavía.')
        response = HttpResponse(construir_etiquetas_pdf(productos, copias), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="etiquetas-codigo-barras.pdf"'
        return response


class InsumoAdminListView(generics.ListCreateAPIView):
    """GET /api/admin/insumos/ lista existencias de insumos de tu sucursal. POST da de alta un insumo nuevo."""

    permission_classes = ES_SUPERVISOR

    def get_serializer_class(self):
        return InsumoCreateSerializer if self.request.method == 'POST' else InsumoAdminSerializer

    def get_queryset(self):
        sucursal = self.request.user.empleado.sucursal
        return (
            InsumoSucursal.objects.select_related('insumo', 'insumo__proveedor_principal')
            .filter(sucursal=sucursal)
            .order_by('insumo__nombre')
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_minimo = serializer.validated_data.pop('stock_minimo', 0)
        stock_inicial = serializer.validated_data.pop('stock_inicial', 0)
        insumo = serializer.save()

        sucursal = request.user.empleado.sucursal
        stock_row = InsumoSucursal.objects.create(
            insumo=insumo, sucursal=sucursal, stock=stock_inicial, stock_minimo=stock_minimo,
        )

        registrar_auditoria(
            request.user.empleado, 'insumo.crear', f'Dio de alta el insumo {insumo.nombre}.',
        )
        return Response(InsumoAdminSerializer(stock_row).data, status=status.HTTP_201_CREATED)


class InsumoEntradaView(APIView):
    """POST /api/admin/insumos/<id_insumo>/entrada/ {cantidad, id_proveedor} - registra una entrada de insumo."""

    permission_classes = ES_SUPERVISOR

    def post(self, request, id_insumo):
        sucursal = request.user.empleado.sucursal
        insumo = get_object_or_404(Insumo, pk=id_insumo)
        stock_row, _ = InsumoSucursal.objects.get_or_create(insumo=insumo, sucursal=sucursal)

        serializer = EntradaInsumoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stock_row.stock += serializer.validated_data['cantidad']
        stock_row.save(update_fields=['stock'])

        proveedor = serializer.validated_data.get('proveedor')
        if proveedor is not None and insumo.proveedor_principal_id is None:
            insumo.proveedor_principal = proveedor
            insumo.save(update_fields=['proveedor_principal'])

        return Response(InsumoAdminSerializer(stock_row).data, status=status.HTTP_201_CREATED)


class ProveedorListCreateView(generics.ListCreateAPIView):
    """GET /api/proveedores/ lista los proveedores. POST da de alta uno nuevo.

    'urgente' se calcula contra la sucursal del empleado autenticado: es True si
    alguno de los insumos que surte esta por debajo de su stock minimo ahi.
    """

    permission_classes = ES_SUPERVISOR
    queryset = Proveedor.objects.all().order_by('nombre')

    def get_serializer_class(self):
        return ProveedorCreateSerializer if self.request.method == 'POST' else ProveedorSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'sucursal': self.request.user.empleado.sucursal}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proveedor = serializer.save()
        return Response(
            ProveedorSerializer(proveedor, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class ProveedorEstadoView(APIView):
    """POST /api/proveedores/<id>/alternar-estado/ - activa/desactiva un proveedor."""

    permission_classes = ES_SUPERVISOR

    def post(self, request, id_proveedor):
        proveedor = get_object_or_404(Proveedor, pk=id_proveedor)
        proveedor.estado = 'inactivo' if proveedor.estado == 'activo' else 'activo'
        proveedor.save(update_fields=['estado'])
        registrar_auditoria(
            request.user.empleado, 'proveedor.alternar_estado',
            f'{"Desactivo" if proveedor.estado == "inactivo" else "Reactivo"} al proveedor {proveedor.nombre}.',
        )
        return Response(ProveedorSerializer(proveedor, context={'sucursal': request.user.empleado.sucursal}).data)
