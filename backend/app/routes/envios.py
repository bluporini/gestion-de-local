from datetime import datetime

from flask import Blueprint, request, jsonify

from app.database import get_db

envios_bp = Blueprint("envios", __name__, url_prefix="/api/envios")

# "entregado" y "resuelto" (un problema ya solucionado) son estados cerrados.
ESTADOS = ("por_preparar", "despachado", "entregado", "problema", "resuelto")
QUIEN_PAGA = ("cliente", "local")
CAMPOS_TEXTO = {
    # campo: largo máximo
    "empresa": 60,
    "numero_seguimiento": 60,
    "destinatario": 120,
    "telefono": 40,
    "direccion": 200,
    "localidad": 80,
    "provincia": 60,
    "codigo_postal": 15,
    "observaciones": 1000,
}
CONSULTA_ENVIO = """
    SELECT e.*, v.codigo AS venta_codigo, v.cliente AS venta_cliente
    FROM envios e
    LEFT JOIN ventas v ON e.venta_id = v.id
"""


def _validar(body, parcial):
    """Valida y normaliza los datos de un envío.

    Parameters
    ----------
    body : dict
        Datos recibidos.
    parcial : bool
        True al editar: solo se validan los campos presentes.

    Returns
    -------
    tuple[dict | None, str | None]
        ``(datos, None)`` si es válido, o ``(None, mensaje_de_error)``.
    """
    datos = {}

    for campo, maximo in CAMPOS_TEXTO.items():
        if campo in body:
            valor = body[campo]
            if valor is not None and not isinstance(valor, str):
                return None, f"{campo} tiene que ser texto"
            valor = (valor or "").strip()[:maximo]
            datos[campo] = valor or None

    if not parcial or "empresa" in body:
        if not datos.get("empresa"):
            return None, "La empresa de envío es requerida"
    if not parcial or "destinatario" in body:
        if not datos.get("destinatario"):
            return None, "El destinatario es requerido"

    if "fecha" in body or not parcial:
        fecha = body.get("fecha")
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
        except (TypeError, ValueError):
            return None, "La fecha es requerida (formato YYYY-MM-DD)"
        datos["fecha"] = fecha

    if "costo" in body:
        costo = body["costo"]
        if costo is None or costo == "":
            costo = 0
        if isinstance(costo, bool) or not isinstance(costo, (int, float)) or costo < 0:
            return None, "El costo tiene que ser un número mayor o igual a 0"
        datos["costo"] = float(costo)

    if "paga" in body:
        if body["paga"] not in QUIEN_PAGA:
            return None, "paga tiene que ser 'cliente' o 'local'"
        datos["paga"] = body["paga"]

    if "estado" in body:
        if body["estado"] not in ESTADOS:
            return None, "Estado inválido"
        datos["estado"] = body["estado"]

    if "venta_id" in body:
        venta_id = body["venta_id"]
        if venta_id is not None and (isinstance(venta_id, bool) or not isinstance(venta_id, int)):
            return None, "venta_id inválido"
        datos["venta_id"] = venta_id

    return datos, None


def _venta_existe(conn, venta_id):
    return venta_id is None or conn.execute("SELECT 1 FROM ventas WHERE id = ?", (venta_id,)).fetchone()


@envios_bp.get("")
def listar_envios():
    """Envíos, del más nuevo al más viejo. Filtros opcionales:
    ``estado`` y ``q`` (busca en destinatario, seguimiento, localidad y
    código de venta)."""
    estado = request.args.get("estado")
    q = (request.args.get("q") or "").strip()

    condiciones, parametros = [], []
    if estado in ESTADOS:
        condiciones.append("e.estado = ?")
        parametros.append(estado)
    if q:
        condiciones.append("""(e.destinatario LIKE ? OR e.numero_seguimiento LIKE ?
                               OR e.localidad LIKE ? OR v.codigo LIKE ?)""")
        parametros += [f"%{q}%"] * 4

    consulta = CONSULTA_ENVIO
    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)
    consulta += " ORDER BY e.fecha DESC, e.id DESC"

    conn = get_db()
    filas = conn.execute(consulta, parametros).fetchall()
    conn.close()
    return jsonify([dict(f) for f in filas])


@envios_bp.get("/<int:envio_id>")
def obtener_envio(envio_id):
    conn = get_db()
    fila = conn.execute(CONSULTA_ENVIO + " WHERE e.id = ?", (envio_id,)).fetchone()
    conn.close()
    if not fila:
        return jsonify({"error": "Envío no encontrado"}), 404
    return jsonify(dict(fila))


@envios_bp.post("")
def crear_envio():
    datos, error = _validar(request.get_json(force=True) or {}, parcial=False)
    if error:
        return jsonify({"error": error}), 400

    conn = get_db()
    if not _venta_existe(conn, datos.get("venta_id")):
        conn.close()
        return jsonify({"error": "La venta vinculada no existe"}), 400

    columnas = ", ".join(datos)
    marcadores = ", ".join("?" for _ in datos)
    cursor = conn.execute(f"INSERT INTO envios ({columnas}) VALUES ({marcadores})", tuple(datos.values()))
    conn.commit()
    envio = dict(conn.execute(CONSULTA_ENVIO + " WHERE e.id = ?", (cursor.lastrowid,)).fetchone())
    conn.close()
    return jsonify(envio), 201


@envios_bp.patch("/<int:envio_id>")
def actualizar_envio(envio_id):
    datos, error = _validar(request.get_json(force=True) or {}, parcial=True)
    if error:
        return jsonify({"error": error}), 400
    if not datos:
        return jsonify({"error": "Nada para actualizar"}), 400

    conn = get_db()
    if not conn.execute("SELECT 1 FROM envios WHERE id = ?", (envio_id,)).fetchone():
        conn.close()
        return jsonify({"error": "Envío no encontrado"}), 404
    if not _venta_existe(conn, datos.get("venta_id")):
        conn.close()
        return jsonify({"error": "La venta vinculada no existe"}), 400

    asignaciones = ", ".join(f"{campo} = ?" for campo in datos)
    conn.execute(f"UPDATE envios SET {asignaciones} WHERE id = ?", (*datos.values(), envio_id))
    conn.commit()
    envio = dict(conn.execute(CONSULTA_ENVIO + " WHERE e.id = ?", (envio_id,)).fetchone())
    conn.close()
    return jsonify(envio)


@envios_bp.delete("/<int:envio_id>")
def borrar_envio(envio_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM envios WHERE id = ?", (envio_id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Envío no encontrado"}), 404
    return jsonify({"ok": True})
