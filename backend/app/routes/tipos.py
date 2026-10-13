from flask import Blueprint, request, jsonify
from app.database import get_db

tipos_bp = Blueprint("tipos", __name__, url_prefix="/api/tipos")


@tipos_bp.get("")
def listar_tipos():
    """Obtiene todos los tipos de prenda ordenados alfabéticamente.

    Returns
    -------
    flask.Response
        JSON con la lista de tipos de prenda, ordenados por nombre.
    """

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tipos_prenda ORDER BY nombre")
    tipos = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify(tipos)


@tipos_bp.post("")
def crear_tipo():
    """Crea un nuevo tipo de prenda.

    El prefijo se almacena en mayúsculas independientemente de cómo haya
    sido enviado en la solicitud.

    JSON Parameters
    ----------------
    nombre : str
        Nombre del tipo de prenda. Es obligatorio.
    prefijo : str
        Prefijo utilizado para generar los códigos de los productos de
        este tipo. Es obligatorio y se almacena en mayúsculas.

    Returns
    -------
    flask.Response
        JSON con los datos del tipo de prenda creado. Devuelve HTTP 201.

        Devuelve HTTP 400 si ``nombre`` o ``prefijo`` no fueron
        proporcionados.

    Notes
    -----
    El prefijo se normaliza mediante ``upper()`` antes de almacenarlo.
    """

    body = request.get_json(force=True) or {}
    nombre = body.get("nombre")
    prefijo = body.get("prefijo")
    if not nombre or not prefijo:
        return jsonify({"error": "nombre y prefijo son requeridos"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tipos_prenda (nombre, prefijo)
        VALUES (?, ?)
    """, (nombre, prefijo.upper()))

    tipo_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM tipos_prenda WHERE id = ?", (tipo_id,))
    nuevo_tipo = dict(cursor.fetchone())
    conn.close()

    return jsonify(nuevo_tipo), 201


@tipos_bp.patch("/<int:tipo_id>")
def editar_tipo(tipo_id):
    """Actualiza los datos de un tipo de prenda.

    Permite modificar el nombre y el prefijo del tipo de prenda. Los
    campos que no se proporcionan conservan sus valores actuales.

    Parameters
    ----------
    tipo_id : int
        Identificador del tipo de prenda que se desea actualizar.

    JSON Parameters
    ----------------
    nombre : str, optional
        Nuevo nombre del tipo de prenda. Si no se proporciona, se conserva
        el nombre actual.
    prefijo : str, optional
        Nuevo prefijo para los códigos de productos. Si no se proporciona,
        se conserva el prefijo actual. El valor se almacena en mayúsculas.

    Returns
    -------
    flask.Response
        JSON con los datos actualizados del tipo de prenda.

        Devuelve HTTP 404 si el tipo de prenda no existe.

    Notes
    -----
    El prefijo se normaliza mediante ``upper()`` antes de almacenarlo.
    """

    body = request.get_json(force=True) or {}

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tipos_prenda WHERE id = ?", (tipo_id,))
    actual = cursor.fetchone()

    if not actual:
        conn.close()
        return jsonify({"error": "Tipo de prenda no encontrado"}), 404

    nombre = body.get("nombre", actual["nombre"])
    prefijo = body.get("prefijo", actual["prefijo"]).upper()

    cursor.execute("""
        UPDATE tipos_prenda 
        SET nombre = ?, prefijo = ?
        WHERE id = ?
    """, (nombre, prefijo, tipo_id))

    conn.commit()
    cursor.execute("SELECT * FROM tipos_prenda WHERE id = ?", (tipo_id,))
    actualizado = dict(cursor.fetchone())
    conn.close()

    return jsonify(actualizado)


@tipos_bp.delete("/<int:tipo_id>")
def borrar_tipo(tipo_id):
    """Elimina un tipo de prenda y desvincula los productos asociados.

    Antes de eliminar el tipo de prenda, se establece ``NULL`` en
    ``productos.tipo_id`` para todos los productos que lo utilizaban.
    Los productos y sus variantes no se eliminan.

    Parameters
    ----------
    tipo_id : int
        Identificador del tipo de prenda que se desea eliminar.

    Returns
    -------
    flask.Response
        Respuesta JSON con ``{"ok": True}``.

    Notes
    -----
    La operación elimina físicamente el registro del tipo de prenda, pero
    conserva los productos asociados, que quedan sin tipo asignado.

    Los productos que posteriormente se creen con este tipo eliminado
    deberán utilizar otro tipo o no tener tipo asignado.
    """
    
    conn = get_db()
    cursor = conn.cursor()

    # Desvincular productos antes de borrar el tipo (o dejar en NULL si la FK lo permite)
    cursor.execute("UPDATE productos SET tipo_id = NULL WHERE tipo_id = ?", (tipo_id,))
    cursor.execute("DELETE FROM tipos_prenda WHERE id = ?", (tipo_id,))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})
