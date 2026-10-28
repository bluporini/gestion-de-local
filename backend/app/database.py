import sqlite3
import os
import shutil
import sys
from datetime import datetime, timedelta

from flask import g, has_app_context

# Ubicación usada en versiones anteriores en todas las plataformas
# (incluso en Windows, donde no es la convencional).
LEGACY_DATA_DIR = os.path.join(
    os.path.expanduser("~"),
    ".local",
    "share",
    "GestionDeLocal"
)


def _data_dir():
    """Carpeta de datos del usuario según la plataforma: %APPDATA% en
    Windows y ~/.local/share en el resto."""
    if os.name == "nt" and os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], "GestionDeLocal")
    return LEGACY_DATA_DIR


def _migrar_db_legacy(db_path):
    """
    Si la base todavía está en la ubicación vieja y no existe en la nueva,
    la copia (sin borrar la original, que queda como respaldo).
    """
    legacy_path = os.path.join(LEGACY_DATA_DIR, "stock_local.db")
    if os.path.abspath(legacy_path) == os.path.abspath(db_path):
        return
    if os.path.exists(db_path) or not os.path.exists(legacy_path):
        return

    shutil.copy2(legacy_path, db_path)
    for sufijo in ("-wal", "-shm", "-journal"):
        if os.path.exists(legacy_path + sufijo):
            shutil.copy2(legacy_path + sufijo, db_path + sufijo)


if getattr(sys, "frozen", False):
    # Aplicación empaquetada con PyInstaller
    DATA_DIR = _data_dir()
    os.makedirs(DATA_DIR, exist_ok=True)

    BASE_DIR = sys._MEIPASS
    DB_PATH = os.path.join(DATA_DIR, "stock_local.db")
    SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

    _migrar_db_legacy(DB_PATH)

else:
    # Desarrollo
    BASE_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    DB_PATH = os.path.join(BASE_DIR, "stock_local.db")
    SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# APP_DB_PATH permite elegir otra base (la usa la demo web, ver backend/demo.py).
if os.environ.get("APP_DB_PATH"):
    DB_PATH = os.environ["APP_DB_PATH"]

OFFSET_ARGENTINA_HORAS = 3  # Argentina es UTC-3 (sin horario de verano)


def get_db_path():
    return DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Dentro de un request de Flask, se registra para que
    # cerrar_conexiones() la cierre al final aunque la ruta falle a mitad
    # de camino (las rutas igual hacen conn.close() a mano en el camino feliz).
    if has_app_context():
        g.setdefault("_conexiones_db", []).append(conn)
    return conn


def cerrar_conexiones(_error=None):
    """Cierra las conexiones abiertas durante el request.

    Registrada con ``app.teardown_appcontext``. Cerrar sin commit descarta
    lo que no se haya confirmado, así una ruta que falla a mitad de una
    venta no deja cambios a medias ni la base bloqueada. Cerrar una
    conexión ya cerrada no hace nada.
    """
    for conn in g.pop("_conexiones_db", []):
        conn.close()


def _columnas(conn, tabla):
    cur = conn.execute(f"PRAGMA table_info({tabla})")
    return {row["name"] for row in cur.fetchall()}


def _migrar_precios_variantes(conn):
    """
    Agrega costo/precio/porcentaje_ganancia a variantes_producto si no existen
    (bases creadas antes de este cambio) y copia los valores actuales del
    producto a cada una de sus variantes existentes.
    """
    cols = _columnas(conn, "variantes_producto")
    columnas_nuevas = []

    if "costo" not in cols:
        conn.execute("ALTER TABLE variantes_producto ADD COLUMN costo REAL DEFAULT 0")
        columnas_nuevas.append("costo")

    if "precio" not in cols:
        conn.execute("ALTER TABLE variantes_producto ADD COLUMN precio REAL DEFAULT 0")
        columnas_nuevas.append("precio")

    if "porcentaje_ganancia" not in cols:
        conn.execute(
            "ALTER TABLE variantes_producto ADD COLUMN porcentaje_ganancia REAL DEFAULT 30"
        )
        columnas_nuevas.append("porcentaje_ganancia")

    if columnas_nuevas:
        conn.execute("""
            UPDATE variantes_producto
            SET
                costo = (SELECT costo FROM productos WHERE productos.id = variantes_producto.producto_id),
                precio = (SELECT precio FROM productos WHERE productos.id = variantes_producto.producto_id),
                porcentaje_ganancia = (SELECT porcentaje_ganancia FROM productos WHERE productos.id = variantes_producto.producto_id)
        """)
        conn.commit()


def _migrar_codigo_ventas(conn):
    """
    Agrega la columna `codigo` a `ventas` si no existe, y le asigna un
    código a las ventas ya existentes (formato DDMMYYNNNv, en base a
    la fecha local de Argentina de cada venta, numeradas por día en el
    orden en que se crearon).
    """
    cols = _columnas(conn, "ventas")
    if "codigo" in cols:
        return

    conn.execute("ALTER TABLE ventas ADD COLUMN codigo TEXT")

    cursor = conn.execute("SELECT id, fecha FROM ventas ORDER BY fecha ASC, id ASC")
    ventas = cursor.fetchall()

    contador_por_dia = {}
    for venta in ventas:
        fecha_utc = datetime.strptime(venta["fecha"].split(".")[0], "%Y-%m-%d %H:%M:%S")
        fecha_local = fecha_utc - timedelta(hours=OFFSET_ARGENTINA_HORAS)
        clave_dia = fecha_local.strftime("%d%m%y")
        contador_por_dia[clave_dia] = contador_por_dia.get(clave_dia, 0) + 1
        codigo = f"{clave_dia}{contador_por_dia[clave_dia]:03d}v"
        conn.execute("UPDATE ventas SET codigo = ? WHERE id = ?", (codigo, venta["id"]))

    conn.commit()

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ventas_codigo ON ventas(codigo)")
    conn.commit()


def _migrar_tabla_cambios(conn):
    """Agrega tiene_cambio a ventas y crea cambios/cambio_items si no existen
    (bases creadas antes de la funcionalidad de cambios)."""
    cols = _columnas(conn, "ventas")
    if "tiene_cambio" not in cols:
        conn.execute("ALTER TABLE ventas ADD COLUMN tiene_cambio INTEGER DEFAULT 0")
        conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cambios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            codigo TEXT UNIQUE,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            monto_diferencia REAL DEFAULT 0,
            metodo_pago TEXT,
            observaciones TEXT,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cambio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cambio_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            variante_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            costo_unitario REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (cambio_id) REFERENCES cambios(id) ON DELETE CASCADE,
            FOREIGN KEY (variante_id) REFERENCES variantes_producto(id)
        )
    """)
    conn.commit()

    # Agrega la columna ganancia a cambios si no existe, y la calcula
    # retroactivamente para los cambios ya cargados (ganancia de ítems
    # nuevos - ganancia de ítems devueltos, por cada cambio).
    cols = _columnas(conn, "cambios")
    if "ganancia" not in cols:
        conn.execute("ALTER TABLE cambios ADD COLUMN ganancia REAL DEFAULT 0")
        conn.commit()

        cursor = conn.execute("SELECT id FROM cambios")
        for row in cursor.fetchall():
            cambio_id = row["id"]
            items_cursor = conn.execute(
                "SELECT tipo, cantidad, precio_unitario, costo_unitario FROM cambio_items WHERE cambio_id = ?",
                (cambio_id,)
            )
            ganancia_neta = 0
            for item in items_cursor.fetchall():
                ganancia_item = (item["precio_unitario"] - item["costo_unitario"]) * item["cantidad"]
                if item["tipo"] == "nuevo":
                    ganancia_neta += ganancia_item
                else:  # 'devuelto'
                    ganancia_neta -= ganancia_item
            conn.execute("UPDATE cambios SET ganancia = ? WHERE id = ?", (round(ganancia_neta, 2), cambio_id))
        conn.commit()

def _migrar_totales_base_ventas(conn):
    """
    Agrega total_base/ganancia_base a ventas si no existen (bases creadas
    antes de este cambio), y las calcula retroactivamente: para ventas sin
    cambios asociados, total_base = total actual. Para ventas con cambios,
    total_base = total actual menos la suma de monto_diferencia/ganancia
    de todos sus cambios (revirtiendo el efecto acumulado).
    """
    cols = _columnas(conn, "ventas")
    columnas_nuevas = []

    if "total_base" not in cols:
        conn.execute("ALTER TABLE ventas ADD COLUMN total_base REAL DEFAULT 0")
        columnas_nuevas.append("total_base")
    if "ganancia_base" not in cols:
        conn.execute("ALTER TABLE ventas ADD COLUMN ganancia_base REAL DEFAULT 0")
        columnas_nuevas.append("ganancia_base")

    if columnas_nuevas:
        conn.commit()
        cursor = conn.execute("SELECT id, total, ganancia FROM ventas")
        for venta in cursor.fetchall():
            sub = conn.execute(
                "SELECT COALESCE(SUM(monto_diferencia), 0) as md, COALESCE(SUM(ganancia), 0) as g "
                "FROM cambios WHERE venta_id = ?",
                (venta["id"],)
            ).fetchone()
            total_base = venta["total"] - (sub["md"] or 0)
            ganancia_base = venta["ganancia"] - (sub["g"] or 0)
            conn.execute(
                "UPDATE ventas SET total_base = ?, ganancia_base = ? WHERE id = ?",
                (round(total_base, 2), round(ganancia_base, 2), venta["id"])
            )
        conn.commit()


def _migrar_canal_ventas(conn):
    """
    Agrega la columna canal ('local' o 'virtual') a ventas si no existe.
    Las ventas anteriores quedan como 'local' por el DEFAULT.
    """
    if "canal" not in _columnas(conn, "ventas"):
        conn.execute("ALTER TABLE ventas ADD COLUMN canal TEXT NOT NULL DEFAULT 'local'")
        conn.commit()


def _migrar_nota_productos(conn):
    """Agrega la columna nota (texto libre) a productos si no existe."""
    if "nota" not in _columnas(conn, "productos"):
        conn.execute("ALTER TABLE productos ADD COLUMN nota TEXT DEFAULT ''")
        conn.commit()


def _migrar_nota_ventas(conn):
    """Agrega la columna nota (texto libre) a ventas si no existe."""
    if "nota" not in _columnas(conn, "ventas"):
        conn.execute("ALTER TABLE ventas ADD COLUMN nota TEXT DEFAULT ''")
        conn.commit()


def _migrar_notas_sin_bloques(conn):
    """
    Las primeras notas (solo en desarrollo, nunca publicadas) estaban
    agrupadas en bloques (notas_bloques + notas.bloque_id). Ahora son una
    lista con etiquetas: si encuentra el formato viejo, recrea la tabla
    `notas` sin bloque_id y convierte el nombre de cada bloque en la
    etiqueta de sus notas.
    """
    if "bloque_id" not in _columnas(conn, "notas"):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("""
        CREATE TABLE notas_nueva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            texto TEXT NOT NULL,
            hecha INTEGER NOT NULL DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO notas_nueva (id, texto, hecha, fecha) SELECT id, texto, hecha, fecha FROM notas")
    conn.execute("""
        INSERT OR IGNORE INTO etiquetas (nombre)
        SELECT DISTINCT b.nombre FROM notas_bloques b JOIN notas n ON n.bloque_id = b.id
    """)
    conn.execute("""
        INSERT OR IGNORE INTO nota_etiquetas (nota_id, etiqueta_id)
        SELECT n.id, e.id
        FROM notas n
        JOIN notas_bloques b ON n.bloque_id = b.id
        JOIN etiquetas e ON e.nombre = b.nombre
    """)
    conn.execute("DROP TABLE notas")
    conn.execute("ALTER TABLE notas_nueva RENAME TO notas")
    conn.execute("DROP TABLE IF EXISTS notas_bloques")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def _sincronizar_stock_productos(conn):
    """
    Recalcula productos.stock_actual como la suma de sus variantes.

    Desde que existen los triggers de schema.sql esto se mantiene solo,
    pero se corre en cada arranque para corregir bases creadas antes de
    los triggers (o cualquier diferencia que haya quedado). Es barato.
    """
    conn.execute("""
        UPDATE productos
        SET stock_actual = (SELECT COALESCE(SUM(v.stock_actual), 0)
                            FROM variantes_producto v WHERE v.producto_id = productos.id)
        WHERE stock_actual IS NOT (SELECT COALESCE(SUM(v.stock_actual), 0)
                                   FROM variantes_producto v WHERE v.producto_id = productos.id)
    """)
    conn.commit()


def init_db():
    conn = get_db()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
        conn.executescript(file.read())

    conn.commit()

    _migrar_precios_variantes(conn)
    _migrar_codigo_ventas(conn)
    _migrar_tabla_cambios(conn)
    _migrar_totales_base_ventas(conn)
    _migrar_canal_ventas(conn)
    _migrar_nota_productos(conn)
    _migrar_nota_ventas(conn)
    _sincronizar_stock_productos(conn)
    _migrar_notas_sin_bloques(conn)

    conn.close()