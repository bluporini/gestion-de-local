# Desarrollo

Guía para levantar el proyecto en local y compilarlo como instalador de Windows.

## Estructura del proyecto

```
.
├── backend
│   ├── app
│   │   ├── database.py       # Inicialización y acceso a stock_local.db (SQLite)
│   │   ├── main.py           # create_app(): registra blueprints y sirve el frontend
│   │   ├── routes/           # Un blueprint por área (productos, ventas, dashboard, update, etc.)
│   │   └── supabase_backup.py # Respaldos en Supabase
│   ├── requirements.txt
│   └── wsgi.py                # Punto de entrada de desarrollo: arranca Flask y abre el navegador
├── frontend
│   ├── index.html
│   ├── js/                    # Un archivo por sección + api.js (llamadas al backend) + update-banner.js
│   ├── styles.css
│   └── logo.png
├── installer
│   ├── installer.iss          # Instalador de Windows (Inno Setup)
│   └── updater
│       └── updater.py         # Cliente de actualizaciones vía GitHub Releases
├── scripts
│   └── limpiar_backups.py     # Retención de respaldos (corre en GitHub Actions)
├── launcher.py                # Punto de entrada del ejecutable final
├── schema.sql                 # Esquema de la base de datos SQLite
├── version.json               # Versión actual instalada (la actualiza updater.py)
└── docs/
```

## Levantar el proyecto en local

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python wsgi.py
```

Esto:
1. Inicializa `stock_local.db` si no existe (ver `schema.sql`).
2. Levanta Flask en `http://127.0.0.1:5000/`, sirviendo tanto la API (`/api/...`) como el frontend estático (`frontend/`).
3. Abre el navegador automáticamente en esa URL.
4. No busca actualizaciones ni hace respaldos automáticos: eso solo pasa en el ejecutable compilado.

### Variable de entorno opcionales en desarrollo

| Variable | Uso |
|---|---|
| `PORT` | Cambiar el puerto (por defecto `5000`) |
| `FLASK_DEBUG` | `true` para activar el modo debug de Flask en desarrollo (nunca se activa en el build empaquetado, sin importar esta variable) |

## Tests

```bash
# Desde la raíz, con el venv activado
pip install -r backend/requirements-dev.txt
python -m pytest -q
```

Los tests (`backend/tests/`) usan una base SQLite temporal creada con el mismo `init_db()` de la app, así que no tocan `stock_local.db`. Al agregar lógica de ventas, cambios o stock, sumar un test: `conftest.py` tiene fixtures para crear productos (`crear_producto`) y ventas (`vender`) y el helper `assert_stock_consistente()`.

Los workflows de build corren los tests antes de compilar: si alguno falla, no se publica la versión.

## Cómo se sirve el frontend

`backend/app/main.py` configura Flask con `static_folder` apuntando a `frontend/` y sirve `index.html` en la raíz (`/`). Esto es así tanto en desarrollo como en el ejecutable empaquetado (ver [`_frontend_dir()`](../backend/app/main.py) para el detalle de cómo resuelve la ruta en cada caso).

`frontend/js/api.js` usa `window.location.origin` como base de la API, así funciona igual en desarrollo y en el `.exe` final con cualquier puerto. El backend no habilita CORS a propósito: no hace falta, y evita que otras páginas abiertas en el navegador lean la API local.

## Agregar una ruta nueva al backend

Seguir el patrón de los blueprints existentes en `backend/app/routes/`:

```python
# backend/app/routes/mi_ruta.py
from flask import Blueprint, jsonify

mi_ruta_bp = Blueprint("mi_ruta", __name__, url_prefix="/api/mi-ruta")

@mi_ruta_bp.route("/", methods=["GET"])
def index():
    return jsonify({"ok": True})
```

Y registrarlo en `backend/app/main.py`:

```python
from app.routes.mi_ruta import mi_ruta_bp
# ...
app.register_blueprint(mi_ruta_bp)
```

## Compilar el ejecutable (PyInstaller)

Normalmente no hace falta compilar a mano: lo hace `.github/workflows/build-windows.yml` al pushear un tag. Para compilar en local (Windows), los mismos comandos que usa el workflow:

```bash
# Desde la raíz del proyecto, con el venv activado.
# supabase.env: SUPABASE_URL=... y SUPABASE_KEY=... (clave anon). Está en .gitignore.

# 1. La app principal (en Windows, --add-data usa ; como separador; en Linux, :)
pyinstaller --onefile --windowed --name GestionDeLocal --paths backend ^
  --add-data "frontend;frontend" --add-data "schema.sql;." --add-data "supabase.env;." ^
  launcher.py

# 2. El updater (independiente, no necesita el frontend)
pyinstaller --onefile --name updater installer/updater/updater.py
```

- `--paths backend` es obligatorio: sin él, el `.exe` falla con `ModuleNotFoundError: No module named 'app'`.
- `schema.sql` tiene que ir adentro: `init_db()` lo lee desde el bundle.
- Sin `supabase.env`, la app funciona pero los respaldos no.

Los ejecutables quedan en `dist/GestionDeLocal.exe` y `dist/updater.exe`. Para armar el instalador hay que copiarlos a `installer/dist/`, junto con un `updater_config.json` con el token de lectura del repo de releases (sin él, el updater no funciona), y compilar `installer/installer.iss` con Inno Setup.

> **Importante:** compilar en Windows (o con una toolchain cruzada) para que el `.exe` funcione en la máquina del cliente. Compilar en Linux genera un binario ELF, no un `.exe`.

## Publicar una nueva versión

Ver el paso a paso completo en [`actualizaciones.md`](./actualizaciones.md).