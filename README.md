# Oso Tostadas — Backend

API REST (Django + Django REST Framework) del punto de venta para la tostadería Oso Tostadas. Maneja empleados, turnos, ventas, pagos, devoluciones, inventario, proveedores, reportes y auditoría, con autenticación por número de empleado.

Repo hermano: [Oso_Tostadas_Frontend](https://github.com/AlexisSGalarza/Oso_Tostadas_Frontend) (React + TypeScript, consume esta API).

## Stack

- Python 3.14, Django 6.1, Django REST Framework
- PostgreSQL
- `djangorestframework-simplejwt` (autenticación por JWT)
- `fpdf2` (generación de recibos en PDF)
- `django-cors-headers`, `python-decouple`

## Estructura

```
config/            Ajustes de Django, URLs raíz
apps/
  empleados/        Empleados, roles, login, horarios
  sucursales/        Sucursal y su configuración (horario, fondo de caja)
  productos/         Catálogo, stock por sucursal, insumos, proveedores
  ventas/            Turnos, ventas, pagos, devoluciones, reportes, dashboard, recibos PDF
  auditoria/         Bitácora de acciones administrativas
```

Cada modelo mapea a una tabla ya existente en la base (`db_table` explícito), organizados por dominio en apps de Django en vez de una sola app monolítica.

## Configuración

1. Crear y activar un entorno virtual, e instalar dependencias:

   **macOS / Linux:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   **Windows (PowerShell):**

   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Si PowerShell bloquea el script por la política de ejecución, corre una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` o usa `venv\Scripts\activate.bat` desde `cmd.exe` en su lugar.

2. Crear un archivo `.env` en la raíz del proyecto con:

   ```
   SECRET_KEY=una-clave-secreta
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   DB_NAME=oso_tostadas_db
   DB_USER=oso_tostadas
   DB_PASSWORD=tu-password
   DB_HOST=localhost
   DB_PORT=5432
   IVA_RATE=0.16
   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

3. Crear la base de datos en Postgres (el rol necesita permiso de `CREATEDB` para poder correr los tests, que usan una base separada) y aplicar las migraciones:

   ```bash
   python manage.py migrate
   ```

4. Sembrar datos de demostración (sucursal, roles, catálogo de productos y dos cuentas de prueba):

   ```bash
   python manage.py seed_demo
   ```

   Esto crea:
   - Vendedor → número de empleado `800001` / contraseña `Demo1234!`
   - Admin → número de empleado `800002` / contraseña `Demo1234!`

5. Levantar el servidor:

   ```bash
   python manage.py runserver
   ```

   La API queda disponible en `http://localhost:8000/api/`.

## Pruebas

```bash
python manage.py test apps
```

## Flujo de negocio

- **Login**: por `numero_empleado` + contraseña (no por correo). El correo se genera automáticamente a partir del nombre y solo se usa como dato de contacto.
- **Turno**: un empleado abre un turno con un fondo de caja inicial antes de poder vender. Al cerrarlo, el efectivo esperado solo considera ventas/devoluciones pagadas en efectivo (las de tarjeta no mueven el cajón físico).
- **Venta**: descuenta stock de la sucursal del empleado, calcula IVA sobre el subtotal y bloquea si no hay existencia suficiente.
- **Pago**: se registra por separado de la venta (así se soporta el pago con tarjeta, procesado en una terminal externa — este backend solo guarda el resultado ya autorizado).
- **Devolución**: repone stock y calcula el monto proporcional con el mismo IVA de la venta original; no se puede devolver más de lo ya vendido (ni acumulado entre varias devoluciones parciales).
- **Recibo**: `GET /api/ventas/<id>/recibo/` genera un PDF de comprobante de compra. No es un CFDI ni tiene validez fiscal.
- **Panel de Admin/Gerente**: gestión de usuarios (con horario de trabajo asignable), inventario (productos e insumos con mínimos y alertas), proveedores, reportes de ventas de 7 días, dashboard con libro de turnos navegable por fecha (no solo el día actual) y detalle de cualquier turno con posibilidad de procesar devoluciones, y bitácora de auditoría de acciones administrativas.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/login/` | Login por número de empleado |
| POST | `/api/auth/refresh/` | Refresco de token JWT |
| GET | `/api/me/` | Datos del empleado autenticado |
| GET/POST | `/api/empleados/` | Listar / crear empleados (Admin/Gerente) |
| POST | `/api/empleados/<id>/alternar-estado/` | Activar/desactivar acceso |
| POST | `/api/empleados/<id>/restablecer-password/` | Nueva contraseña temporal |
| PATCH | `/api/empleados/<id>/horario/` | Asignar horario de trabajo |
| GET | `/api/roles/` | Catálogo de roles |
| GET/PATCH | `/api/sucursales/mia/` | Configuración de la sucursal |
| GET | `/api/productos/` | Catálogo con stock (para vender) |
| GET | `/api/admin/productos/`, `/api/admin/insumos/` | Inventario administrativo |
| POST | `/api/admin/productos/<id>/produccion/`, `/api/admin/insumos/<id>/entrada/` | Movimientos de stock |
| GET/POST | `/api/proveedores/` | Proveedores |
| GET/POST | `/api/turnos/abrir/`, `/api/turnos/cerrar/`, `/api/turnos/actual/` | Ciclo de turno |
| GET/POST | `/api/ventas/` | Listar ventas del turno abierto / registrar una venta |
| GET | `/api/ventas/<id>/` | Detalle de una venta |
| POST | `/api/ventas/<id>/pagos/` | Registrar pago |
| POST | `/api/ventas/<id>/devoluciones/` | Registrar devolución |
| GET | `/api/ventas/<id>/recibo/` | Descargar recibo en PDF |
| GET | `/api/reportes/semana/` | Ventas de los últimos 7 días |
| GET | `/api/admin/dashboard/?fecha=AAAA-MM-DD` | Resumen, libro de turnos y pendientes de un día |
| GET | `/api/admin/turnos/<id>/` | Detalle de un turno con todas sus ventas |
| GET | `/api/auditoria/` | Bitácora de acciones administrativas |

Todos los endpoints (salvo login/refresh) requieren `Authorization: Bearer <access_token>`; los de `admin/` además requieren rol Gerente o Admin.
