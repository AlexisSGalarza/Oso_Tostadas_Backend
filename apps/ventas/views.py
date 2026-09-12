from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.empleados.permissions import TieneEmpleadoActivo, rol_requerido
from apps.productos.models import ProductoSucursal

from .models import DetalleVenta, Turno, Venta
from .serializers import (
    PagoSerializer,
    TurnoAbrirSerializer,
    TurnoCerrarSerializer,
    TurnoSerializer,
    VentaCreateSerializer,
    VentaSerializer,
)

ROLES_VENTA = ('Vendedor', 'Cajero', 'Gerente', 'Admin')
ROLES_SUPERVISOR = ('Gerente', 'Admin')


class AbrirTurnoView(APIView):
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def post(self, request):
        empleado = request.user.empleado
        serializer = TurnoAbrirSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if Turno.objects.filter(empleado=empleado, estado='abierto').exists():
            raise ValidationError('Ya tienes un turno abierto.')

        turno = Turno.objects.create(
            empleado=empleado,
            sucursal=empleado.sucursal,
            fecha=timezone.localdate(),
            hora_inicio=timezone.localtime().time(),
            estado='abierto',
            monto_inicial=serializer.validated_data['monto_inicial'],
        )
        return Response(TurnoSerializer(turno).data, status=status.HTTP_201_CREATED)


class CerrarTurnoView(APIView):
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def post(self, request):
        empleado = request.user.empleado
        serializer = TurnoCerrarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        monto_contado = serializer.validated_data['monto_contado']

        with transaction.atomic():
            turno = (
                Turno.objects.select_for_update()
                .filter(empleado=empleado, estado='abierto')
                .first()
            )
            if turno is None:
                raise ValidationError('No tienes un turno abierto.')

            total_ventas = (
                turno.ventas.exclude(estado='cancelada').aggregate(t=Sum('total'))['t'] or 0
            )
            ingresos = (
                turno.movimientos_caja.filter(tipo='ingreso').aggregate(t=Sum('monto'))['t'] or 0
            )
            egresos = (
                turno.movimientos_caja.filter(tipo='egreso').aggregate(t=Sum('monto'))['t'] or 0
            )
            monto_esperado = turno.monto_inicial + total_ventas + ingresos - egresos

            turno.hora_fin = timezone.localtime().time()
            turno.monto_esperado = monto_esperado
            turno.monto_contado = monto_contado
            turno.diferencia = monto_contado - monto_esperado
            turno.estado = 'cerrado'
            turno.save()

        return Response(TurnoSerializer(turno).data)


class VentaCreateView(APIView):
    """POST /api/ventas/ {detalles: [{id_producto, unidades}, ...]}."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_VENTA),
    ]

    def post(self, request):
        empleado = request.user.empleado
        serializer = VentaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        detalles_in = serializer.validated_data['detalles']

        ids_producto = [d['id_producto'] for d in detalles_in]
        if len(set(ids_producto)) != len(ids_producto):
            raise ValidationError('No repitas el mismo producto; suma las unidades en una sola linea.')

        turno = Turno.objects.filter(empleado=empleado, estado='abierto').first()
        if turno is None:
            raise ValidationError('Debes abrir un turno antes de registrar una venta.')

        with transaction.atomic():
            stocks = {
                ps.producto_id: ps
                for ps in ProductoSucursal.objects.select_for_update().filter(
                    sucursal=empleado.sucursal, producto_id__in=ids_producto
                )
            }

            lineas = []
            subtotal_total = 0.0
            for item in detalles_in:
                id_producto = item['id_producto']
                unidades = item['unidades']
                stock_row = stocks.get(id_producto)
                if stock_row is None or stock_row.producto.estado != 'activo':
                    raise ValidationError(
                        f'El producto {id_producto} no esta disponible en tu sucursal.'
                    )
                if stock_row.stock < unidades:
                    raise ValidationError(
                        f'Stock insuficiente para "{stock_row.producto.nombre}" '
                        f'(disponible: {stock_row.stock}, solicitado: {unidades}).'
                    )
                precio_unitario = stock_row.producto.precio
                subtotal_linea = round(precio_unitario * unidades, 2)
                subtotal_total += subtotal_linea
                lineas.append((stock_row, unidades, precio_unitario, subtotal_linea))

            impuesto = round(subtotal_total * settings.IVA_RATE, 2)
            total = round(subtotal_total + impuesto, 2)

            venta = Venta.objects.create(
                fecha=timezone.localdate(),
                subtotal=round(subtotal_total, 2),
                impuesto=impuesto,
                total=total,
                estado='completada',
                turno=turno,
            )

            for stock_row, unidades, precio_unitario, subtotal_linea in lineas:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=stock_row.producto,
                    unidades=unidades,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal_linea,
                )
                stock_row.stock -= unidades
                stock_row.save(update_fields=['stock'])

        return Response(VentaSerializer(venta).data, status=status.HTTP_201_CREATED)


class VentaDetailView(generics.RetrieveAPIView):
    """GET /api/ventas/<pk>/ - solo ve ventas de su propio turno, salvo Gerente/Admin."""

    serializer_class = VentaSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get_queryset(self):
        empleado = self.request.user.empleado
        qs = Venta.objects.select_related('turno').prefetch_related('detalles__producto')
        if empleado.rol.nombre_rol in ROLES_SUPERVISOR:
            return qs
        return qs.filter(turno__empleado=empleado)


class PagoCreateView(generics.CreateAPIView):
    """POST /api/ventas/<id_venta>/pagos/ - registra un pago sobre una venta propia."""

    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get_venta(self):
        empleado = self.request.user.empleado
        qs = Venta.objects.all()
        if empleado.rol.nombre_rol not in ROLES_SUPERVISOR:
            qs = qs.filter(turno__empleado=empleado)
        return get_object_or_404(qs, pk=self.kwargs['id_venta'])

    def perform_create(self, serializer):
        venta = self.get_venta()
        monto = serializer.validated_data['monto']
        if monto <= 0:
            raise ValidationError('El monto del pago debe ser mayor a 0.')

        ya_pagado = venta.pagos.aggregate(t=Sum('monto'))['t'] or 0
        if ya_pagado + monto > venta.total:
            raise ValidationError(
                f'El pago excede el saldo pendiente (pagado: {ya_pagado}, total: {venta.total}).'
            )

        serializer.save(venta=venta, fecha=timezone.localdate())
