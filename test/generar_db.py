import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone


# ============================================================
# CONFIGURACIÓN
# ============================================================

DB_PATH = os.environ.get("DEMO_DB_PATH", "stock_local.db")

# Argentina = UTC-3
OFFSET_ARGENTINA_HORAS = 3


# ------------------------------------------------------------
# FECHAS DEL DATASET
# ------------------------------------------------------------

# "Hoy" del dataset: el día actual (hora de Argentina), así la demo
# siempre tiene ventas de hoy, de esta semana y de este mes. Si todavía
# no abrió el local, se toma ayer como último día.
_AHORA_AR = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
if (_AHORA_AR.hour, _AHORA_AR.minute) < (9, 0):
    FECHA_REFERENCIA = (_AHORA_AR - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
else:
    FECHA_REFERENCIA = _AHORA_AR.replace(hour=0, minute=0, second=0, microsecond=0)

# Cantidad de días históricos.
CANT_DIAS_HISTORICOS = 365 * 2

FECHA_INICIO = (
    FECHA_REFERENCIA
    - timedelta(days=CANT_DIAS_HISTORICOS)
)

FECHA_FIN = FECHA_REFERENCIA


# ------------------------------------------------------------
# HORARIO COMERCIAL
# ------------------------------------------------------------

HORA_INICIO_VENTAS = 8
MINUTO_INICIO_VENTAS = 15

HORA_FIN_VENTAS = 22
MINUTO_FIN_VENTAS = 0


# Última hora permitida en FECHA_REFERENCIA.
#
# Si querés simular el día completo:
#
# HORA_MAXIMA_ULTIMO_DIA = (22, 0, 59)
#
HORA_MAXIMA_ULTIMO_DIA = (22, 0, 0)

# Si el último día es hoy, no generar ventas "en el futuro".
if FECHA_REFERENCIA.date() == _AHORA_AR.date():
    HORA_MAXIMA_ULTIMO_DIA = min(HORA_MAXIMA_ULTIMO_DIA, (_AHORA_AR.hour, _AHORA_AR.minute, 0))


# ------------------------------------------------------------
# CANTIDADES
# ------------------------------------------------------------

CANT_PRODUCTOS = 180
CANT_VENTAS = 2400
CANT_MOVIMIENTOS_ENTRADA = 1700
CANT_AJUSTES_SALIDA = 180
CANT_CAMBIOS = 160


# ------------------------------------------------------------
# OTROS
# ------------------------------------------------------------

SEMILLA = 20260920

PORCENTAJE_GANANCIA_DEFAULT = 30

BORRAR_BD_EXISTENTE = True


# ============================================================
# DATOS
# ============================================================

TIPOS_PRENDA = [
    ("Bombacha", "BOM"),
    ("Corpiño", "COR"),
    ("Conjunto", "CON"),
    ("Vedetina", "VED"),
    ("Tanga", "TAN"),
    ("Body", "BDY"),
    ("Pijama", "PIJ"),
    ("Camisón", "CAM"),
    ("Top", "TOP"),
    ("Medias", "MED"),
    ("Short", "SHO"),
    ("Calza", "CAL"),
]


NOMBRES_PRODUCTOS = [
    "Bombacha clásica",
    "Bombacha tiro alto",
    "Bombacha colaless",
    "Bombacha vedetina",
    "Bombacha algodón",
    "Bombacha microfibra",
    "Corpiño clásico",
    "Corpiño con aro",
    "Corpiño deportivo",
    "Corpiño push up",
    "Corpiño balconette",
    "Corpiño sin aro",
    "Conjunto básico",
    "Conjunto encaje",
    "Conjunto microfibra",
    "Conjunto deportivo",
    "Vedetina clásica",
    "Vedetina algodón",
    "Vedetina encaje",
    "Tanga clásica",
    "Tanga regulable",
    "Tanga encaje",
    "Body manga corta",
    "Body manga larga",
    "Body encaje",
    "Pijama corto",
    "Pijama largo",
    "Pijama algodón",
    "Camisón clásico",
    "Camisón encaje",
    "Top deportivo",
    "Top básico",
    "Top encaje",
    "Medias cortas",
    "Medias largas",
    "Short deportivo",
    "Short algodón",
    "Calza básica",
    "Calza deportiva",
]


TALLES = [
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "XXL",
]


COLORES = [
    "Negro",
    "Blanco",
    "Rojo",
    "Bordó",
    "Rosa",
    "Fucsia",
    "Beige",
    "Gris",
    "Azul",
    "Celeste",
    "Verde",
    "Violeta",
]


METODOS_PAGO = [
    "Efectivo",
    "Tarjeta débito",
    "Tarjeta crédito",
    "Transferencia",
    "Otro",
]


TIPOS_TARJETA = [
    "Visa",
    "Mastercard",
    "Naranja",
    "American Express",
    "Cabal",
    "Otro"
]


CLIENTES = [
    "Brian",
    "Abril",
    "Marcelo",
    "María",
    "Laura",
    "Sofía",
    "Carolina",
    "Lucía",
    "Valentina",
    "Camila",
    "Agustina",
    "Florencia",
    "Julieta",
    "Paula",
    "Gabriela",
    "Victoria",
    "Natalia",
]


# ============================================================
# FECHAS
# ============================================================

def argentina_a_utc(fecha_argentina):
    """
    Convierte una fecha/hora de Argentina a UTC.

    Argentina: UTC-3
    Para obtener UTC se suman 3 horas.
    """

    return fecha_argentina + timedelta(
        hours=OFFSET_ARGENTINA_HORAS
    )


def fecha_sql_utc(fecha_argentina):
    """
    Devuelve el timestamp UTC que se almacena en SQLite.

    SQLite recibe:

        YYYY-MM-DD HH:MM:SS
    """

    return argentina_a_utc(
        fecha_argentina
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def inicio_horario_comercial(fecha):
    return fecha.replace(
        hour=HORA_INICIO_VENTAS,
        minute=MINUTO_INICIO_VENTAS,
        second=0,
        microsecond=0,
    )


def fin_horario_comercial(fecha):
    """
    Para el último día usamos HORA_MAXIMA_ULTIMO_DIA.
    Para los demás días usamos hasta 22:00:59.
    """

    if fecha.date() == FECHA_REFERENCIA.date():

        hora, minuto, segundo = (
            HORA_MAXIMA_ULTIMO_DIA
        )

    else:

        hora = HORA_FIN_VENTAS
        minuto = MINUTO_FIN_VENTAS
        segundo = 59

    return fecha.replace(
        hour=hora,
        minute=minuto,
        second=segundo,
        microsecond=0,
    )


def fecha_aleatoria_argentina(
    fecha_inicio,
    fecha_fin,
):
    """
    Genera una fecha aleatoria respetando:

        08:15 <= hora <= 22:00

    No se genera una fecha simplemente entre dos
    datetimes porque eso produciría horarios fuera del
    horario comercial en los días intermedios.
    """

    dia_inicio = fecha_inicio.date()
    dia_fin = fecha_fin.date()

    cantidad_dias = (
        dia_fin - dia_inicio
    ).days

    dia = (
        dia_inicio
        + timedelta(
            days=random.randint(
                0,
                cantidad_dias,
            )
        )
    )

    fecha_base = datetime.combine(
        dia,
        datetime.min.time(),
    )

    inicio = inicio_horario_comercial(
        fecha_base
    )

    fin = fin_horario_comercial(
        fecha_base
    )

    segundos = int(
        (fin - inicio).total_seconds()
    )

    return inicio + timedelta(
        seconds=random.randint(
            0,
            segundos,
        )
    )


def fecha_aleatoria_despues_de(
    fecha_minima,
    fecha_maxima,
):
    """
    Genera una fecha posterior o igual a fecha_minima
    y no posterior a fecha_maxima.

    Respeta horario comercial.
    """

    if fecha_minima > fecha_maxima:
        return None

    dia_inicio = fecha_minima.date()
    dia_fin = fecha_maxima.date()

    cantidad_dias = (
        dia_fin - dia_inicio
    ).days

    dia = (
        dia_inicio
        + timedelta(
            days=random.randint(
                0,
                cantidad_dias,
            )
        )
    )

    fecha_base = datetime.combine(
        dia,
        datetime.min.time(),
    )

    inicio = inicio_horario_comercial(
        fecha_base
    )

    fin = fin_horario_comercial(
        fecha_base
    )

    # Si estamos en el mismo día de la venta,
    # no podemos generar un cambio antes de la venta.
    if dia == dia_inicio:

        inicio = max(
            inicio,
            fecha_minima,
        )

    if inicio > fin:
        return None

    segundos = int(
        (fin - inicio).total_seconds()
    )

    return inicio + timedelta(
        seconds=random.randint(
            0,
            segundos,
        )
    )


# ============================================================
# CÓDIGOS
# ============================================================

def generar_codigo_venta(
    fecha_argentina,
    numero,
):
    return (
        fecha_argentina.strftime("%d%m%y")
        + f"{numero:03d}"
        + "V"
    )


def generar_codigo_cambio(
    fecha_argentina,
    numero,
):
    return (
        fecha_argentina.strftime("%d%m%y")
        + f"{numero:03d}"
        + "C"
    )


# ============================================================
# BASE DE DATOS
# ============================================================

def crear_base():

    db_path = os.path.abspath(
        DB_PATH
    )

    if (
        BORRAR_BD_EXISTENTE
        and os.path.exists(db_path)
    ):
        os.remove(db_path)

        print(
            f"BD anterior eliminada: {db_path}"
        )

    conn = sqlite3.connect(
        db_path
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn, db_path


# ============================================================
# SCHEMA
# ============================================================

def crear_schema(conn):

    conn.executescript("""
        PRAGMA foreign_keys = ON;


        CREATE TABLE tipos_prenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            prefijo TEXT UNIQUE NOT NULL
        );


        CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            tipo_id INTEGER,
            costo REAL DEFAULT 0,
            precio REAL DEFAULT 0,
            porcentaje_ganancia REAL DEFAULT 30,
            stock_actual INTEGER DEFAULT 0,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (tipo_id)
                REFERENCES tipos_prenda(id)
                ON DELETE SET NULL
        );


        CREATE TABLE variantes_producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            codigo TEXT UNIQUE NOT NULL,
            talle TEXT,
            color TEXT,
            cantidad_por_unidad INTEGER NOT NULL DEFAULT 1,
            costo REAL DEFAULT 0,
            precio REAL DEFAULT 0,
            porcentaje_ganancia REAL DEFAULT 30,
            stock_actual INTEGER DEFAULT 0,
            stock_minimo INTEGER DEFAULT 0,
            FOREIGN KEY (producto_id)
                REFERENCES productos(id)
                ON DELETE CASCADE
        );


        CREATE TABLE ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cliente TEXT,
            metodo_pago TEXT,
            tipo_tarjeta TEXT,
            monto_pagado REAL,
            vuelto REAL,
            total REAL DEFAULT 0,
            ganancia REAL DEFAULT 0,
            estado TEXT DEFAULT 'realizada',
            tiene_cambio INTEGER DEFAULT 0,
            total_base REAL DEFAULT 0,
            ganancia_base REAL DEFAULT 0
        );


        CREATE TABLE venta_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            producto_id INTEGER,
            variante_id INTEGER,
            cantidad INTEGER,
            precio_unitario REAL,
            costo_unitario REAL,
            subtotal REAL,
            ganancia_item REAL,
            FOREIGN KEY (venta_id)
                REFERENCES ventas(id)
                ON DELETE CASCADE,
            FOREIGN KEY (producto_id)
                REFERENCES productos(id),
            FOREIGN KEY (variante_id)
                REFERENCES variantes_producto(id)
        );


        CREATE TABLE movimientos_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variante_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (variante_id)
                REFERENCES variantes_producto(id)
                ON DELETE CASCADE
        );


        CREATE TABLE configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        );


        CREATE TABLE cambios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            codigo TEXT UNIQUE,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            monto_diferencia REAL DEFAULT 0,
            ganancia REAL DEFAULT 0,
            metodo_pago TEXT,
            observaciones TEXT,
            FOREIGN KEY (venta_id)
                REFERENCES ventas(id)
                ON DELETE CASCADE
        );


        CREATE TABLE cambio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cambio_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            variante_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            costo_unitario REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (cambio_id)
                REFERENCES cambios(id)
                ON DELETE CASCADE,
            FOREIGN KEY (variante_id)
                REFERENCES variantes_producto(id)
        );


        CREATE INDEX idx_ventas_fecha
            ON ventas(fecha);

        CREATE INDEX idx_cambios_fecha
            ON cambios(fecha);

        CREATE INDEX idx_movimientos_fecha
            ON movimientos_stock(fecha);

        CREATE INDEX idx_variantes_stock
            ON variantes_producto(stock_actual);

        CREATE INDEX idx_venta_items_venta
            ON venta_items(venta_id);

        CREATE INDEX idx_cambio_items_cambio
            ON cambio_items(cambio_id);
    """)


# ============================================================
# TIPOS DE PRENDA
# ============================================================

def crear_tipos_prenda(conn):

    for nombre, prefijo in TIPOS_PRENDA:

        conn.execute(
            """
            INSERT INTO tipos_prenda (
                nombre,
                prefijo
            )
            VALUES (?, ?)
            """,
            (
                nombre,
                prefijo,
            ),
        )

    conn.commit()


# ============================================================
# PRODUCTOS
# ============================================================

def crear_productos(conn):

    tipos = conn.execute(
        """
        SELECT id, nombre, prefijo
        FROM tipos_prenda
        """
    ).fetchall()

    variantes = []

    for i in range(
        CANT_PRODUCTOS
    ):

        tipo = random.choice(
            tipos
        )

        nombre_base = random.choice(
            NOMBRES_PRODUCTOS
        )

        nombre = (
            f"{nombre_base} {i + 1:03d}"
        )

        codigo = (
            f"{tipo['prefijo']}"
            f"{i + 1:04d}"
        )

        costo = round(
            random.uniform(
                2500,
                18000,
            ),
            2,
        )

        porcentaje = random.choice(
            [
                25,
                30,
                35,
                40,
                45,
                50,
            ]
        )

        precio = round(
            costo
            * (
                1
                + porcentaje / 100
            ),
            2,
        )

        cursor = conn.execute(
            """
            INSERT INTO productos (
                codigo,
                nombre,
                descripcion,
                tipo_id,
                costo,
                precio,
                porcentaje_ganancia,
                stock_actual,
                activo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                nombre,
                f"{nombre} de ropa íntima.",
                tipo["id"],
                costo,
                precio,
                porcentaje,
                0,
                1,
            ),
        )

        producto_id = cursor.lastrowid

        cantidad_variantes = random.randint(
            3,
            6,
        )

        combinaciones = set()

        for _ in range(
            cantidad_variantes
        ):

            while True:

                talle = random.choice(
                    TALLES
                )

                color = random.choice(
                    COLORES
                )

                if (
                    talle,
                    color,
                ) not in combinaciones:
                    break

            combinaciones.add(
                (
                    talle,
                    color,
                )
            )

            codigo_variante = (
                f"{codigo}-"
                f"{talle}-"
                f"{color[:3].upper()}"
            )

            costo_variante = round(
                costo
                * random.uniform(
                    0.95,
                    1.05,
                ),
                2,
            )

            precio_variante = round(
                costo_variante
                * (
                    1
                    + porcentaje / 100
                ),
                2,
            )

            # Stock inicial suficientemente alto.
            #
            # Esto es importante porque después se generan
            # 2400 ventas + 180 ajustes + 160 cambios.
            stock_inicial = random.randint(
                8,
                25,
            )

            stock_minimo = random.choice(
                [
                    1,
                    1,
                    2,
                    2,
                    3,
                ]
            )

            cursor_variante = conn.execute(
                """
                INSERT INTO variantes_producto (
                    producto_id,
                    codigo,
                    talle,
                    color,
                    cantidad_por_unidad,
                    costo,
                    precio,
                    porcentaje_ganancia,
                    stock_actual,
                    stock_minimo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    producto_id,
                    codigo_variante,
                    talle,
                    color,
                    1,
                    costo_variante,
                    precio_variante,
                    porcentaje,
                    stock_inicial,
                    stock_minimo,
                ),
            )

            variantes.append({
                "id": cursor_variante.lastrowid,
                "producto_id": producto_id,
                "codigo": codigo_variante,
                "talle": talle,
                "color": color,
                "costo": costo_variante,
                "precio": precio_variante,
            })

        # Actualizar stock del producto.
        conn.execute(
            """
            UPDATE productos
            SET stock_actual = (
                SELECT COALESCE(
                    SUM(stock_actual),
                    0
                )
                FROM variantes_producto
                WHERE producto_id = ?
            )
            WHERE id = ?
            """,
            (
                producto_id,
                producto_id,
            ),
        )

    conn.commit()

    return variantes


# ============================================================
# MOVIMIENTOS DE ENTRADA
# ============================================================

def crear_movimientos_entrada(
    conn,
    variantes,
):

    for _ in range(
        CANT_MOVIMIENTOS_ENTRADA
    ):

        variante = random.choice(
            variantes
        )

        cantidad = random.randint(
            2,
            10,
        )

        fecha_argentina = (
            fecha_aleatoria_argentina(
                FECHA_INICIO,
                FECHA_FIN,
            )
        )

        fecha_utc = fecha_sql_utc(
            fecha_argentina
        )

        # IMPORTANTE:
        # ahora la entrada SÍ aumenta el stock.
        conn.execute(
            """
            UPDATE variantes_producto
            SET stock_actual =
                stock_actual + ?
            WHERE id = ?
            """,
            (
                cantidad,
                variante["id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO movimientos_stock (
                variante_id,
                tipo,
                cantidad,
                motivo,
                fecha
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                variante["id"],
                "entrada",
                cantidad,
                "Ingreso de mercadería",
                fecha_utc,
            ),
        )

    conn.commit()


# ============================================================
# AJUSTES DE SALIDA
# ============================================================

def crear_ajustes_salida(
    conn,
    variantes,
):

    creados = 0

    intentos = 0

    max_intentos = (
        CANT_AJUSTES_SALIDA * 10
    )

    while (
        creados < CANT_AJUSTES_SALIDA
        and intentos < max_intentos
    ):

        intentos += 1

        variante = random.choice(
            variantes
        )

        row = conn.execute(
            """
            SELECT stock_actual
            FROM variantes_producto
            WHERE id = ?
            """,
            (
                variante["id"],
            ),
        ).fetchone()

        stock = row["stock_actual"]

        # Dejamos siempre al menos 2 unidades
        # para evitar agotar completamente el stock.
        if stock <= 2:
            continue

        cantidad = random.randint(
            1,
            min(
                3,
                stock - 2,
            ),
        )

        fecha_argentina = (
            fecha_aleatoria_argentina(
                FECHA_INICIO,
                FECHA_FIN,
            )
        )

        fecha_utc = fecha_sql_utc(
            fecha_argentina
        )

        conn.execute(
            """
            UPDATE variantes_producto
            SET stock_actual =
                stock_actual - ?
            WHERE id = ?
            """,
            (
                cantidad,
                variante["id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO movimientos_stock (
                variante_id,
                tipo,
                cantidad,
                motivo,
                fecha
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                variante["id"],
                "salida",
                cantidad,
                "Ajuste de stock",
                fecha_utc,
            ),
        )

        creados += 1

    conn.commit()

    return creados


# ============================================================
# VENTAS
# ============================================================

def crear_ventas(conn):

    variantes = conn.execute(
        """
        SELECT
            id,
            producto_id,
            codigo,
            costo,
            precio,
            stock_actual
        FROM variantes_producto
        """
    ).fetchall()

    contador_por_dia = {}

    ventas_creadas = []

    for _ in range(
        CANT_VENTAS
    ):

        fecha_argentina = (
            fecha_aleatoria_argentina(
                FECHA_INICIO,
                FECHA_FIN,
            )
        )

        fecha_dia = (
            fecha_argentina.date()
        )

        contador_por_dia[fecha_dia] = (
            contador_por_dia.get(
                fecha_dia,
                0,
            )
            + 1
        )

        numero = contador_por_dia[
            fecha_dia
        ]

        codigo = generar_codigo_venta(
            fecha_argentina,
            numero,
        )

        cliente = random.choice(
            CLIENTES
        )

        metodo_pago = random.choice(
            METODOS_PAGO
        )

        tipo_tarjeta = None

        if metodo_pago in (
            "debito",
            "credito",
        ):
            tipo_tarjeta = random.choice(
                TIPOS_TARJETA
            )

        cursor = conn.execute(
            """
            INSERT INTO ventas (
                codigo,
                fecha,
                cliente,
                metodo_pago,
                tipo_tarjeta,
                monto_pagado,
                vuelto,
                total,
                ganancia,
                estado,
                tiene_cambio,
                total_base,
                ganancia_base
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                fecha_sql_utc(
                    fecha_argentina
                ),
                cliente,
                metodo_pago,
                tipo_tarjeta,
                0,
                0,
                0,
                0,
                "realizada",
                0,
                0,
                0,
            ),
        )

        venta_id = cursor.lastrowid

        # Seleccionamos variantes con stock.
        disponibles = conn.execute(
            """
            SELECT
                id,
                producto_id,
                codigo,
                costo,
                precio,
                stock_actual
            FROM variantes_producto
            WHERE stock_actual > 2
            ORDER BY RANDOM()
            LIMIT 20
            """
        ).fetchall()

        if not disponibles:
            conn.execute(
                """
                DELETE FROM ventas
                WHERE id = ?
                """,
                (
                    venta_id,
                ),
            )
            continue

        cantidad_items = random.randint(
            1,
            min(
                4,
                len(disponibles),
            ),
        )

        seleccionadas = random.sample(
            disponibles,
            cantidad_items,
        )

        total = 0
        ganancia = 0

        for variante in seleccionadas:

            stock = variante[
                "stock_actual"
            ]

            # Nunca consumimos la última unidad.
            max_cantidad = min(
                2,
                stock - 1,
            )

            if max_cantidad < 1:
                continue

            cantidad = random.randint(
                1,
                max_cantidad,
            )

            precio = float(
                variante["precio"]
            )

            costo = float(
                variante["costo"]
            )

            subtotal = round(
                precio * cantidad,
                2,
            )

            ganancia_item = round(
                (
                    precio - costo
                ) * cantidad,
                2,
            )

            conn.execute(
                """
                INSERT INTO venta_items (
                    venta_id,
                    producto_id,
                    variante_id,
                    cantidad,
                    precio_unitario,
                    costo_unitario,
                    subtotal,
                    ganancia_item
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    venta_id,
                    variante["producto_id"],
                    variante["id"],
                    cantidad,
                    precio,
                    costo,
                    subtotal,
                    ganancia_item,
                ),
            )

            conn.execute(
                """
                UPDATE variantes_producto
                SET stock_actual =
                    stock_actual - ?
                WHERE id = ?
                """,
                (
                    cantidad,
                    variante["id"],
                ),
            )

            conn.execute(
                """
                INSERT INTO movimientos_stock (
                    variante_id,
                    tipo,
                    cantidad,
                    motivo,
                    fecha
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    variante["id"],
                    "salida",
                    cantidad,
                    f"Venta {codigo}",
                    fecha_sql_utc(
                        fecha_argentina
                    ),
                ),
            )

            total += subtotal
            ganancia += ganancia_item

        if total <= 0:

            conn.execute(
                """
                DELETE FROM ventas
                WHERE id = ?
                """,
                (
                    venta_id,
                ),
            )

            continue

        total = round(
            total,
            2,
        )

        ganancia = round(
            ganancia,
            2,
        )

        if metodo_pago == "efectivo":

            monto_pagado = (
                total
                + random.choice(
                    [
                        0,
                        0,
                        500,
                        1000,
                        2000,
                        5000,
                    ]
                )
            )

            monto_pagado = round(
                max(
                    monto_pagado,
                    total,
                ),
                2,
            )

            vuelto = round(
                monto_pagado - total,
                2,
            )

        else:

            monto_pagado = total
            vuelto = 0

        conn.execute(
            """
            UPDATE ventas
            SET
                monto_pagado = ?,
                vuelto = ?,
                total = ?,
                ganancia = ?,
                total_base = ?,
                ganancia_base = ?
            WHERE id = ?
            """,
            (
                monto_pagado,
                vuelto,
                total,
                ganancia,
                total,
                ganancia,
                venta_id,
            ),
        )

        ventas_creadas.append({
            "id": venta_id,
            "codigo": codigo,
            "fecha_argentina": fecha_argentina,
            "total": total,
            "ganancia": ganancia,
        })

    conn.commit()

    return ventas_creadas


# ============================================================
# CAMBIOS
# ============================================================

def crear_cambios(
    conn,
    ventas,
):

    if not ventas:
        return 0

    # Mezclamos las ventas para elegir aquellas que tendrán
    # cambios.
    candidatos = ventas.copy()

    random.shuffle(
        candidatos
    )

    creados = 0

    contador_por_dia = {}

    for venta in candidatos:

        if creados >= CANT_CAMBIOS:
            break

        venta_id = venta["id"]

        fecha_venta = (
            venta["fecha_argentina"]
        )

        # El cambio siempre es posterior
        # a la venta.
        fecha_cambio = (
            fecha_aleatoria_despues_de(
                fecha_venta,
                FECHA_FIN,
            )
        )

        if fecha_cambio is None:
            continue

        # Producto original de la venta.
        # Producto original de la venta.
        item = conn.execute(
            """
            SELECT
                variante_id,
                precio_unitario,
                costo_unitario
            FROM venta_items
            WHERE venta_id = ?
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (
                venta_id,
            ),
        ).fetchone()

        if item is None:
            continue

        variante_devuelta = conn.execute(
            """
            SELECT
                id,
                producto_id,
                codigo,
                costo,
                precio,
                stock_actual
            FROM variantes_producto
            WHERE id = ?
            """,
            (
                item["variante_id"],
            ),
        ).fetchone()

        if variante_devuelta is None:
            continue

        # Buscamos una variante diferente con stock.
        variante_nueva = conn.execute(
            """
            SELECT
                id,
                producto_id,
                codigo,
                costo,
                precio,
                stock_actual
            FROM variantes_producto
            WHERE id != ?
              AND stock_actual > 0
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (
                variante_devuelta["id"],
            ),
        ).fetchone()

        if variante_nueva is None:
            continue

        fecha_dia = (
            fecha_cambio.date()
        )

        contador_por_dia[fecha_dia] = (
            contador_por_dia.get(
                fecha_dia,
                0,
            )
            + 1
        )

        numero = contador_por_dia[
            fecha_dia
        ]

        codigo = generar_codigo_cambio(
            fecha_cambio,
            numero,
        )

        precio_devuelto = float(
            item["precio_unitario"]
        )

        costo_devuelto = float(
            item["costo_unitario"]
        )

        precio_nuevo = float(
            variante_nueva["precio"]
        )

        costo_nuevo = float(
            variante_nueva["costo"]
        )

        monto_diferencia = round(
            precio_nuevo
            - precio_devuelto,
            2,
        )

        ganancia_devuelto = (
            precio_devuelto
            - costo_devuelto
        )

        ganancia_nuevo = (
            precio_nuevo
            - costo_nuevo
        )

        ganancia_cambio = round(
            ganancia_nuevo
            - ganancia_devuelto,
            2,
        )

        if monto_diferencia > 0:

            metodo_pago = random.choice(
                METODOS_PAGO
            )

        elif monto_diferencia < 0:

            metodo_pago = "efectivo"

        else:

            metodo_pago = None

        cursor = conn.execute(
            """
            INSERT INTO cambios (
                venta_id,
                codigo,
                fecha,
                monto_diferencia,
                ganancia,
                metodo_pago,
                observaciones
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                venta_id,
                codigo,
                fecha_sql_utc(
                    fecha_cambio
                ),
                monto_diferencia,
                ganancia_cambio,
                metodo_pago,
                "Cambio de producto",
            ),
        )

        cambio_id = cursor.lastrowid

        # ----------------------------------------------------
        # DEVUELTO
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO cambio_items (
                cambio_id,
                tipo,
                variante_id,
                cantidad,
                precio_unitario,
                costo_unitario
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cambio_id,
                "devuelto",
                variante_devuelta["id"],
                1,
                precio_devuelto,
                costo_devuelto,
            ),
        )

        conn.execute(
            """
            UPDATE variantes_producto
            SET stock_actual =
                stock_actual + 1
            WHERE id = ?
            """,
            (
                variante_devuelta["id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO movimientos_stock (
                variante_id,
                tipo,
                cantidad,
                motivo,
                fecha
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                variante_devuelta["id"],
                "entrada",
                1,
                f"Cambio {codigo} - devolución",
                fecha_sql_utc(
                    fecha_cambio
                ),
            ),
        )

        # ----------------------------------------------------
        # NUEVO
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO cambio_items (
                cambio_id,
                tipo,
                variante_id,
                cantidad,
                precio_unitario,
                costo_unitario
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cambio_id,
                "nuevo",
                variante_nueva["id"],
                1,
                precio_nuevo,
                costo_nuevo,
            ),
        )

        conn.execute(
            """
            UPDATE variantes_producto
            SET stock_actual =
                stock_actual - 1
            WHERE id = ?
              AND stock_actual > 0
            """,
            (
                variante_nueva["id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO movimientos_stock (
                variante_id,
                tipo,
                cantidad,
                motivo,
                fecha
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                variante_nueva["id"],
                "salida",
                1,
                f"Cambio {codigo} - nuevo producto",
                fecha_sql_utc(
                    fecha_cambio
                ),
            ),
        )

        conn.execute(
            """
            UPDATE ventas
            SET tiene_cambio = 1
            WHERE id = ?
            """,
            (
                venta_id,
            ),
        )

        creados += 1

    conn.commit()

    return creados


# ============================================================
# ACTUALIZAR STOCK DE PRODUCTOS
# ============================================================

def actualizar_stock_productos(conn):

    conn.execute(
        """
        UPDATE productos
        SET stock_actual = (
            SELECT COALESCE(
                SUM(vp.stock_actual),
                0
            )
            FROM variantes_producto vp
            WHERE vp.producto_id =
                  productos.id
        )
        """
    )

    conn.commit()


# ============================================================
# CONFIGURACIÓN
# ============================================================

def crear_configuracion(conn):

    valores = [
        (
            "usuario",
            "admin",
        ),
        (
            "porcentaje_ganancia_default",
            str(
                PORCENTAJE_GANANCIA_DEFAULT
            ),
        ),
    ]

    for clave, valor in valores:

        conn.execute(
            """
            INSERT OR IGNORE INTO configuracion (
                clave,
                valor
            )
            VALUES (?, ?)
            """,
            (
                clave,
                valor,
            ),
        )

    conn.commit()


# ============================================================
# RESUMEN
# ============================================================

def mostrar_resumen(
    conn,
    db_path,
    ventas_creadas,
    cambios_creados,
    ajustes_creados,
):

    productos = conn.execute(
        """
        SELECT COUNT(*)
        FROM productos
        """
    ).fetchone()[0]

    variantes = conn.execute(
        """
        SELECT COUNT(*)
        FROM variantes_producto
        """
    ).fetchone()[0]

    variantes_con_stock = conn.execute(
        """
        SELECT COUNT(*)
        FROM variantes_producto
        WHERE stock_actual > 0
        """
    ).fetchone()[0]

    variantes_sin_stock = conn.execute(
        """
        SELECT COUNT(*)
        FROM variantes_producto
        WHERE stock_actual = 0
        """
    ).fetchone()[0]

    stock_total = conn.execute(
        """
        SELECT COALESCE(
            SUM(stock_actual),
            0
        )
        FROM variantes_producto
        """
    ).fetchone()[0]

    ventas = conn.execute(
        """
        SELECT COUNT(*)
        FROM ventas
        """
    ).fetchone()[0]

    venta_items = conn.execute(
        """
        SELECT COUNT(*)
        FROM venta_items
        """
    ).fetchone()[0]

    cambios = conn.execute(
        """
        SELECT COUNT(*)
        FROM cambios
        """
    ).fetchone()[0]

    movimientos = conn.execute(
        """
        SELECT COUNT(*)
        FROM movimientos_stock
        """
    ).fetchone()[0]

    total_ventas = conn.execute(
        """
        SELECT COALESCE(
            SUM(total_base),
            0
        )
        FROM ventas
        """
    ).fetchone()[0]

    ganancia_ventas = conn.execute(
        """
        SELECT COALESCE(
            SUM(ganancia_base),
            0
        )
        FROM ventas
        """
    ).fetchone()[0]

    ganancia_cambios = conn.execute(
        """
        SELECT COALESCE(
            SUM(ganancia),
            0
        )
        FROM cambios
        """
    ).fetchone()[0]

    print()
    print("=" * 65)
    print("BASE DE DATOS GENERADA")
    print("=" * 65)

    print(
        f"BD:                 {db_path}"
    )

    print(
        f"Período:            "
        f"{FECHA_INICIO:%Y-%m-%d} -> "
        f"{FECHA_FIN:%Y-%m-%d}"
    )

    print(
        f"Horario ventas:     "
        f"{HORA_INICIO_VENTAS:02d}:"
        f"{MINUTO_INICIO_VENTAS:02d} -> "
        f"{HORA_FIN_VENTAS:02d}:"
        f"{MINUTO_FIN_VENTAS:02d}"
    )

    print()

    print(
        f"Productos:           {productos}"
    )

    print(
        f"Variantes:           {variantes}"
    )

    print(
        f"Variantes con stock: {variantes_con_stock}"
    )

    print(
        f"Variantes stock 0:   {variantes_sin_stock}"
    )

    print(
        f"Stock total:         {stock_total}"
    )

    print()

    print(
        f"Ventas:              {ventas}"
    )

    print(
        f"Ventas solicitadas:  {CANT_VENTAS}"
    )

    print(
        f"Cambios:             {cambios}"
    )

    print(
        f"Cambios solicitados: {CANT_CAMBIOS}"
    )

    print(
        f"Ajustes salida:      {ajustes_creados}"
    )

    print(
        f"Movimientos stock:   {movimientos}"
    )

    print()

    print(
        f"Total ventas:        "
        f"${total_ventas:,.2f}"
    )

    print(
        f"Ganancia ventas:     "
        f"${ganancia_ventas:,.2f}"
    )

    print(
        f"Ganancia cambios:    "
        f"${ganancia_cambios:,.2f}"
    )

    print(
        f"Ganancia total:      "
        f"${ganancia_ventas + ganancia_cambios:,.2f}"
    )

    print()

    print("Conversión de ejemplo:")

    ejemplo = datetime(
        2025,
        12,
        31,
        22,
        0,
        0,
    )

    print(
        f"  Argentina: "
        f"{ejemplo:%Y-%m-%d %H:%M:%S}"
    )

    print(
        f"  SQLite UTC: "
        f"{fecha_sql_utc(ejemplo)}"
    )

    print("=" * 65)
    print()


# ============================================================
# MAIN
# ============================================================

def main():

    random.seed(
        SEMILLA
    )

    print()
    print(
        "Generando base de datos sintética..."
    )
    print()

    conn, db_path = crear_base()

    try:

        # 1. Estructura
        crear_schema(conn)

        # 2. Tipos
        crear_tipos_prenda(conn)

        # 3. Productos + stock inicial
        variantes = crear_productos(
            conn
        )

        # 4. Entradas que SÍ aumentan stock
        crear_movimientos_entrada(
            conn,
            variantes,
        )

        # 5. Ajustes de salida
        ajustes_creados = (
            crear_ajustes_salida(
                conn,
                variantes,
            )
        )

        # 6. Ventas
        ventas = crear_ventas(
            conn
        )

        # 7. Cambios
        cambios_creados = crear_cambios(
            conn,
            ventas,
        )

        # 8. Recalcular stock de productos
        actualizar_stock_productos(
            conn
        )

        # 9. Configuración
        crear_configuracion(
            conn
        )

        # 10. Resumen
        mostrar_resumen(
            conn,
            db_path,
            len(ventas),
            cambios_creados,
            ajustes_creados,
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()