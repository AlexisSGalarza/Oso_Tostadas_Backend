from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.empleados.permissions import ROLES_SUPERVISOR, TieneEmpleadoActivo, rol_requerido
from apps.productos.models import InsumoSucursal, ProductoSucursal

from .models import DetalleVenta, Devolucion, DevolucionDetalle, Pago, Turno, Venta
from .recibo import construir_recibo_pdf
from .serializers import (
    DevolucionCreateSerializer,
    DevolucionSerializer,
    PagoSerializer,
    TurnoAbrirSerializer,
    TurnoCerrarSerializer,
    TurnoDetalleSerializer,
    TurnoSerializer,
    VentaCreateSerializer,
    VentaSerializer,
)

ROLES_VENTA = ('Vendedor', 'Cajero', 'Gerente', 'Admin')
ES_SUPERVISOR = [permissions.IsAuthenticated, TieneEmpleadoActivo, rol_requerido(*ROLES_SUPERVISOR)]


def _venta_visible_para(empleado, id_venta, queryset=None):
    """Una venta que el empleado puede operar: la propia, o cualquiera si es supervisor."""
    qs = queryset if queryset is not None else Venta.objects.select_related('turno')
    if empleado.rol.nombre_rol not in ROLES_SUPERVISOR:
        qs = qs.filter(turno__empleado=empleado)
    return get_object_or_404(qs, pk=id_venta)


class TurnoActualView(APIView):
    """GET /api/turnos/actual/ - el turno abierto del empleado autenticado, si tiene uno."""

    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get(self, request):
        turno = Turno.objects.filter(empleado=request.user.empleado, estado='abierto').first()
        if turno is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(TurnoSerializer(turno).data)


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

            # Solo el efectivo mueve el cajon fisico; las ventas/devoluciones con
            # tarjeta no deben afectar el efectivo esperado.
            total_ventas_efectivo = (
                Pago.objects.filter(venta__turno=turno, metodo_pago='efectivo')
                .exclude(venta__estado='cancelada')
                .aggregate(t=Sum('monto'))['t']
                or 0
            )
            total_devoluciones_efectivo = (
                Devolucion.objects.filter(venta__turno=turno, venta__pagos__metodo_pago='efectivo')
                .aggregate(t=Sum('monto'))['t']
                or 0
            )
            ingresos = (
                turno.movimientos_caja.filter(tipo='ingreso').aggregate(t=Sum('monto'))['t'] or 0
            )
            egresos = (
                turno.movimientos_caja.filter(tipo='egreso').aggregate(t=Sum('monto'))['t'] or 0
            )
            monto_esperado = (
                turno.monto_inicial + total_ventas_efectivo - total_devoluciones_efectivo + ingresos - egresos
            )

            turno.hora_fin = timezone.localtime().time()
            turno.monto_esperado = monto_esperado
            turno.monto_contado = monto_contado
            turno.diferencia = monto_contado - monto_esperado
            turno.estado = 'cerrado'
            turno.save()

        return Response(TurnoSerializer(turno).data)


class VentaCreateView(APIView):
    """GET /api/ventas/ lista las ventas del turno abierto. POST {detalles: [{id_producto, unidades}, ...]} registra una."""

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_VENTA),
    ]

    def get(self, request):
        empleado = request.user.empleado
        turno = Turno.objects.filter(empleado=empleado, estado='abierto').first()
        if turno is None:
            return Response([])
        ventas = (
            Venta.objects.filter(turno=turno)
            .exclude(estado='cancelada')
            .prefetch_related('detalles__producto', 'pagos', 'devoluciones__detalles__producto')
            .order_by('creado_en', 'id_venta')
        )
        return Response(VentaSerializer(ventas, many=True).data)

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
        qs = Venta.objects.select_related('turno').prefetch_related(
            'detalles__producto', 'pagos', 'devoluciones__detalles__producto'
        )
        if empleado.rol.nombre_rol in ROLES_SUPERVISOR:
            return qs
        return qs.filter(turno__empleado=empleado)


class ReciboVentaView(APIView):
    """GET /api/ventas/<id_venta>/recibo/ - descarga el recibo de compra en PDF (no es un CFDI)."""

    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def get(self, request, id_venta):
        base_qs = Venta.objects.select_related('turno__sucursal').prefetch_related('detalles__producto', 'pagos')
        venta = _venta_visible_para(request.user.empleado, id_venta, queryset=base_qs)
        pdf_bytes = construir_recibo_pdf(venta)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="recibo-{venta.id_venta}.pdf"'
        return response


class PagoCreateView(generics.CreateAPIView):
    """POST /api/ventas/<id_venta>/pagos/ - registra un pago sobre una venta propia."""

    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated, TieneEmpleadoActivo]

    def perform_create(self, serializer):
        venta = _venta_visible_para(self.request.user.empleado, self.kwargs['id_venta'])
        monto = serializer.validated_data['monto']
        if monto <= 0:
            raise ValidationError('El monto del pago debe ser mayor a 0.')

        ya_pagado = venta.pagos.aggregate(t=Sum('monto'))['t'] or 0
        if ya_pagado + monto > venta.total:
            raise ValidationError(
                f'El pago excede el saldo pendiente (pagado: {ya_pagado}, total: {venta.total}).'
            )

        serializer.save(venta=venta, fecha=timezone.localdate())


class DevolucionCreateView(APIView):
    """POST /api/ventas/<id_venta>/devoluciones/ {detalles: [{id_producto, cantidad}, ...]}.

    Repone el stock de la sucursal de la venta y calcula el monto con el mismo
    IVA_RATE que se uso al vender, para que sea proporcional a lo realmente cobrado.
    """

    permission_classes = [
        permissions.IsAuthenticated,
        TieneEmpleadoActivo,
        rol_requerido(*ROLES_VENTA),
    ]

    def post(self, request, id_venta):
        empleado = request.user.empleado
        venta = _venta_visible_para(empleado, id_venta)

        serializer = DevolucionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        detalles_in = serializer.validated_data['detalles']

        ids_producto = [d['id_producto'] for d in detalles_in]
        if len(set(ids_producto)) != len(ids_producto):
            raise ValidationError('No repitas el mismo producto; suma las unidades en una sola linea.')

        with transaction.atomic():
            detalles_venta = {
                d.producto_id: d
                for d in DetalleVenta.objects.select_for_update().filter(
                    venta=venta, producto_id__in=ids_producto
                )
            }
            ya_devuelto = dict(
                DevolucionDetalle.objects.filter(venta=venta, producto_id__in=ids_producto)
                .values('producto_id')
                .annotate(total=Sum('cantidad'))
                .values_list('producto_id', 'total')
            )

            lineas = []
            monto_total = 0.0
            for item in detalles_in:
                id_producto = item['id_producto']
                cantidad = item['cantidad']
                detalle_venta = detalles_venta.get(id_producto)
                if detalle_venta is None:
                    raise ValidationError(f'El producto {id_producto} no forma parte de esta venta.')

                disponible = detalle_venta.unidades - ya_devuelto.get(id_producto, 0)
                if cantidad > disponible:
                    raise ValidationError(
                        f'Solo puedes devolver {disponible} unidad(es) de '
                        f'"{detalle_venta.producto.nombre}" (ya devuelto: {ya_devuelto.get(id_producto, 0)}).'
                    )

                monto_linea = round(detalle_venta.precio_unitario * cantidad * (1 + settings.IVA_RATE), 2)
                monto_total += monto_linea
                lineas.append((detalle_venta, cantidad))

            devolucion = Devolucion.objects.create(
                fecha=timezone.localdate(), monto=round(monto_total, 2), venta=venta,
            )

            for detalle_venta, cantidad in lineas:
                DevolucionDetalle.objects.create(
                    devolucion=devolucion,
                    venta=venta,
                    producto=detalle_venta.producto,
                    cantidad=cantidad,
                )
                stock_row, _ = ProductoSucursal.objects.select_for_update().get_or_create(
                    producto=detalle_venta.producto,
                    sucursal=venta.turno.sucursal,
                    defaults={'stock': 0},
                )
                stock_row.stock += cantidad
                stock_row.save(update_fields=['stock'])

        return Response(DevolucionSerializer(devolucion).data, status=status.HTTP_201_CREATED)


class ReporteSemanaView(APIView):
    """GET /api/reportes/semana/ - ventas de los ultimos 7 dias y productos mas vendidos, de tu sucursal."""

    permission_classes = ES_SUPERVISOR

    def get(self, request):
        sucursal = request.user.empleado.sucursal
        hoy = timezone.localdate()
        desde = hoy - timedelta(days=6)

        ventas_periodo = Venta.objects.filter(
            turno__sucursal=sucursal, fecha__range=(desde, hoy)
        ).exclude(estado='cancelada')

        por_dia = {
            fila['fecha']: fila
            for fila in ventas_periodo.values('fecha').annotate(ventas=Sum('total'), tickets=Count('id_venta'))
        }
        dias = [
            {
                'fecha': str(desde + timedelta(days=offset)),
                'ventas': por_dia.get(desde + timedelta(days=offset), {}).get('ventas') or 0,
                'tickets': por_dia.get(desde + timedelta(days=offset), {}).get('tickets') or 0,
            }
            for offset in range(7)
        ]

        productos = list(
            DetalleVenta.objects.filter(venta__in=ventas_periodo)
            .values('producto__nombre')
            .annotate(cantidad=Sum('unidades'), ingresos=Sum('subtotal'))
            .order_by('-cantidad')
        )
        productos = [
            {'nombre': p['producto__nombre'], 'cantidad': p['cantidad'], 'ingresos': p['ingresos']}
            for p in productos
        ]

        return Response({'dias': dias, 'productos': productos})


class AdminTurnoDetalleView(generics.RetrieveAPIView):
    """GET /api/admin/turnos/<id_turno>/ - un turno de tu sucursal con todas sus ventas y devoluciones."""

    serializer_class = TurnoDetalleSerializer
    permission_classes = ES_SUPERVISOR
    lookup_url_kwarg = 'id_turno'

    def get_queryset(self):
        sucursal = self.request.user.empleado.sucursal
        return Turno.objects.select_related('empleado').filter(sucursal=sucursal)


class AdminDashboardView(APIView):
    """GET /api/admin/dashboard/?fecha=YYYY-MM-DD - libro de turnos y resumen de un dia (por defecto hoy)."""

    permission_classes = ES_SUPERVISOR

    def get(self, request):
        sucursal = request.user.empleado.sucursal
        fecha_param = request.query_params.get('fecha')
        if fecha_param:
            try:
                dia = date.fromisoformat(fecha_param)
            except ValueError:
                raise ValidationError('Fecha invalida, usa el formato AAAA-MM-DD.')
        else:
            dia = timezone.localdate()

        turnos_del_dia = (
            Turno.objects.filter(sucursal=sucursal, fecha=dia)
            .select_related('empleado')
            .order_by('hora_inicio')
        )

        turnos_data = []
        pendientes = []
        for turno in turnos_del_dia:
            ventas_turno = turno.ventas.exclude(estado='cancelada').aggregate(t=Sum('total'))['t'] or 0
            turnos_data.append({
                'id_turno': turno.id_turno,
                'empleado': turno.empleado.nombre,
                'hora_inicio': turno.hora_inicio,
                'hora_fin': turno.hora_fin,
                'estado': turno.estado,
                'ventas': ventas_turno,
                'diferencia': turno.diferencia,
            })
            if turno.estado == 'cerrado' and turno.diferencia:
                texto_signo = 'faltante' if turno.diferencia < 0 else 'sobrante'
                pendientes.append({
                    'severidad': 'urgente' if abs(turno.diferencia) >= 50 else 'aviso',
                    'texto': f'{turno.empleado.nombre}: {texto_signo} de {abs(turno.diferencia):.2f} en su corte.',
                })

        for stock_row in (
            ProductoSucursal.objects.select_related('producto')
            .filter(sucursal=sucursal, producto__estado='activo', stock__lt=F('stock_minimo'))
        ):
            pendientes.append({
                'severidad': 'urgente' if stock_row.stock <= 0 else 'aviso',
                'texto': (
                    f'Producto: {stock_row.producto.nombre} con solo {stock_row.stock} unidades '
                    f'en existencia (minimo {stock_row.stock_minimo}).'
                ),
            })

        for stock_row in (
            InsumoSucursal.objects.select_related('insumo')
            .filter(sucursal=sucursal, insumo__estado='activo', stock__lt=F('stock_minimo'))
        ):
            pendientes.append({
                'severidad': 'urgente' if stock_row.stock <= 0 else 'aviso',
                'texto': (
                    f'Insumo: {stock_row.insumo.nombre} por debajo del minimo '
                    f'({stock_row.stock}/{stock_row.stock_minimo} {stock_row.insumo.unidad_medida}).'
                ),
            })

        ventas_dia = (
            Venta.objects.filter(turno__sucursal=sucursal, fecha=dia)
            .exclude(estado='cancelada')
            .aggregate(t=Sum('total'))['t']
            or 0
        )

        return Response({
            'fecha': dia.isoformat(),
            'es_hoy': dia == timezone.localdate(),
            'resumen': {
                'ventas_dia': ventas_dia,
                'turnos_activos': turnos_del_dia.filter(estado='abierto').count(),
                'cortes_por_revisar': sum(1 for t in turnos_data if t['estado'] == 'cerrado' and t['diferencia']),
            },
            'turnos': turnos_data,
            'pendientes': pendientes,
        })
