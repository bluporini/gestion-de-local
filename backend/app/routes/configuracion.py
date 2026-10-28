from flask import Blueprint, request, jsonify
from app.database import get_db

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/api/configuracion")

# Una variante tiene "stock bajo" cuando le quedan esta cantidad de
# unidades o menos (pero más de 0: en 0 es "sin stock").
UMBRAL_STOCK_BAJO_DEFAULT = 1


def leer_umbral_stock_bajo(cursor):
    """Devuelve el umbral de stock bajo guardado en ``configuracion``.

    Si no está configurado o el valor guardado no es válido, devuelve
    ``UMBRAL_STOCK_BAJO_DEFAULT``.
    """
    cursor.execute("SELECT valor FROM configuracion WHERE clave = 'stock_bajo_umbral'")
    fila = cursor.fetchone()
    try:
        umbral = int(fila["valor"]) if fila else UMBRAL_STOCK_BAJO_DEFAULT
    except (TypeError, ValueError):
        return UMBRAL_STOCK_BAJO_DEFAULT
    return umbral if umbral >= 1 else UMBRAL_STOCK_BAJO_DEFAULT


@configuracion_bp.get("")
def obtener_configuracion():
    """Devuelve la configuración editable desde la pantalla de Configuración."""
    conn = get_db()
    umbral = leer_umbral_stock_bajo(conn.cursor())
    conn.close()
    return jsonify({"stock_bajo_umbral": umbral})


@configuracion_bp.put("")
def actualizar_configuracion():
    """Actualiza la configuración.

    JSON Parameters
    ---------------
    stock_bajo_umbral : int
        Cantidad de unidades (1 o más) a partir de la cual una variante se
        muestra como "stock bajo" en el dashboard.

    Returns
    -------
    flask.Response
        La configuración actualizada. HTTP 400 si el valor no es válido.
    """
    body = request.get_json(force=True) or {}
    umbral = body.get("stock_bajo_umbral")

    if not isinstance(umbral, int) or isinstance(umbral, bool) or not 1 <= umbral <= 1000:
        return jsonify({"error": "stock_bajo_umbral tiene que ser un número entero entre 1 y 1000"}), 400

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('stock_bajo_umbral', ?)",
        (str(umbral),),
    )
    conn.commit()
    conn.close()
    return jsonify({"stock_bajo_umbral": umbral})
