from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from app.database import get_db
from app.routes.ventas import _rango_utc_para_dia_local

cambios_bp = Blueprint("cambios", __name__, url_prefix="/api/cambios")

# Argentina es UTC-3 (sin horario de verano)
OFFSET_ARGENTINA_HORAS = 3 

def _generar_codigo_cambio(cursor):
    """Genera el código identificador de un cambio.

    El código sigue el formato ``DDMMYYNNNC``, donde:

    - ``DDMMYY`` corresponde a la fecha actual en Argentina.
    - ``NNN`` es un número correlativo de tres dígitos para ese día.
    - ``C`` identifica que el registro corresponde a un cambio.

    El número correlativo comienza en ``001`` cada día y se obtiene
    buscando en la tabla ``cambios`` los códigos generados para la
    fecha actual.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor activo de la base de datos utilizado para consultar
        los códigos de cambios existentes.

    Returns
    -------
    str
        Nuevo código de cambio con formato ``DDMMYYNNNC``.

    Notes
    -----
    Se utiliza la hora de Argentina para determinar la fecha del
    código, independientemente de la zona horaria configurada en
    el sistema.

    Examples
    --------
    Si la fecha es 19/09/2026 y ya existen los códigos
    ``190926001C`` y ``190926002C``, la función devuelve
    ``190926003C``.
    """

    ahora_local = datetime.now(timezone.utc) - timedelta(hours=OFFSET_ARGENTINA_HORAS)
    clave_dia = ahora_local.strftime("%d%m%y")

    cursor.execute("SELECT codigo FROM cambios WHERE codigo LIKE ?", (f"{clave_dia}%",))
    max_num = 0
    for row in cursor.fetchall():
        codigo = row["codigo"] or ""
        cuerpo = codigo[len(clave_dia):-1]
        if cuerpo.isdigit():
            max_num = max(max_num, int(cuerpo))

    return f"{clave_dia}{max_num + 1:03d}c"


def _cantidad_disponible_por_item(cursor, venta_id, excluir_cambio_id=None):
    """Calcula la cantidad disponible para devolución de cada variante de una venta.

    Para cada variante incluida en la venta, calcula la cantidad que todavía
    puede devolverse como:

        cantidad comprada - cantidad ya devuelta en cambios anteriores

    Si se proporciona ``excluir_cambio_id``, se excluye ese cambio del cálculo.
    Esto permite reutilizar la función al editar un cambio existente sin que
    la cantidad devuelta por ese mismo cambio reduzca nuevamente la cantidad
    disponible.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor activo de la base de datos utilizado para consultar la venta
        y sus cambios asociados.

    venta_id : int
        Identificador de la venta cuyos productos se desean consultar.

    excluir_cambio_id : int, optional
        Identificador de un cambio que debe excluirse del cálculo.
        Se utiliza principalmente al editar un cambio existente.
        Por defecto es ``None``.

    Returns
    -------
    dict
        Diccionario indexado por ``variante_id``. Cada entrada contiene:

        - ``comprada`` : cantidad originalmente comprada.
        - ``ya_devuelta`` : cantidad devuelta en cambios anteriores.
        - ``disponible`` : cantidad que todavía puede devolverse.
        - ``precio_unitario`` : precio de venta de la variante.
        - ``costo_unitario`` : costo de la variante.

    Notes
    -----
    Solo se consideran como devoluciones los registros de ``cambio_items``
    cuyo tipo sea ``'devuelto'``.

    Las variantes que aparecen en la venta pero no tienen devoluciones
    registradas tendrán ``ya_devuelta = 0``.

    Examples
    --------
    Si una venta contiene 3 unidades de una variante y 1 unidad ya fue
    devuelta en un cambio anterior, el resultado será:

        {
            variante_id: {
                "comprada": 3,
                "ya_devuelta": 1,
                "disponible": 2,
                ...
            }
        }

    Al editar un cambio existente, ``excluir_cambio_id`` evita que la
    devolución correspondiente a ese cambio sea contabilizada nuevamente.
    """

    cursor.execute("""
        SELECT vi.variante_id, vi.cantidad, vi.precio_unitario, vi.costo_unitario
        FROM venta_items vi
        WHERE vi.venta_id = ?
    """, (venta_id,))

    resumen = {}
    for row in cursor.fetchall():
        vid = row["variante_id"]
        # La misma variante puede estar en más de un ítem de la venta.
        if vid in resumen:
            resumen[vid]["comprada"] += row["cantidad"]
            continue
        resumen[vid] = {
            "comprada": row["cantidad"],
            "ya_devuelta": 0,
            "precio_unitario": row["precio_unitario"],
            "costo_unitario": row["costo_unitario"],
        }

    if excluir_cambio_id:
        cursor.execute("""
            SELECT ci.variante_id, ci.cantidad
            FROM cambio_items ci
            JOIN cambios c ON ci.cambio_id = c.id
            WHERE c.venta_id = ? AND ci.tipo = 'devuelto' AND c.id != ?
        """, (venta_id, excluir_cambio_id))
    else:
        cursor.execute("""
            SELECT ci.variante_id, ci.cantidad
            FROM cambio_items ci
            JOIN cambios c ON ci.cambio_id = c.id
            WHERE c.venta_id = ? AND ci.tipo = 'devuelto'
        """, (venta_id,))

    for row in cursor.fetchall():
        vid = row["variante_id"]
        if vid in resumen:
            resumen[vid]["ya_devuelta"] += row["cantidad"]

    for vid, r in resumen.items():
        r["disponible"] = r["comprada"] - r["ya_devuelta"]

    return resumen


@cambios_bp.get("/venta/<int:venta_id>/disponible")
def disponible_para_cambio(venta_id):
    """Obtiene los ítems de una venta y la cantidad disponible para devolución.

    Consulta una venta y sus ítems para determinar, para cada variante,
    cuántas unidades fueron compradas, cuántas ya fueron devueltas mediante
    cambios anteriores y cuántas permanecen disponibles para devolver.

    Parameters
    ----------
    venta_id : int
        Identificador de la venta que se desea consultar.

    Returns
    -------
    flask.Response
        Respuesta JSON con la información de la venta y sus ítems.
        Cada ítem contiene el producto, código, talle, color, cantidad
        comprada, cantidad ya devuelta, cantidad disponible y precio unitario.

    Query Parameters
    ----------------
    excluir_cambio_id : int, optional
        Identificador de un cambio que debe excluirse del cálculo de
        cantidades devueltas. Se utiliza al editar un cambio existente.

    Raises
    ------
    404
        Si no existe una venta con el ``venta_id`` proporcionado.

    Notes
    -----
    Este endpoint utiliza ``_cantidad_disponible_por_item`` para calcular
    las cantidades que todavía pueden devolverse.

    Examples
    --------
    GET /venta/123/disponible

    GET /venta/123/disponible?excluir_cambio_id=45
    """

    excluir_cambio_id = request.args.get("excluir_cambio_id", type=int)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if not venta:
        conn.close()
        return jsonify({"error": "Venta no encontrada"}), 404

    resumen = _cantidad_disponible_por_item(cursor, venta_id, excluir_cambio_id)

    data = []
    for vid, r in resumen.items():
        cursor.execute("""
            SELECT vp.codigo, vp.talle, vp.color, p.nombre as producto_nombre
            FROM variantes_producto vp
            JOIN productos p ON vp.producto_id = p.id
            WHERE vp.id = ?
        """, (vid,))
        info = cursor.fetchone()
        data.append({
            "variante_id": vid,
            "producto_nombre": info["producto_nombre"] if info else "—",
            "codigo": info["codigo"] if info else "—",
            "talle": info["talle"] if info else None,
            "color": info["color"] if info else None,
            "comprada": r["comprada"],
            "ya_devuelta": r["ya_devuelta"],
            "disponible": r["disponible"],
            "precio_unitario": r["precio_unitario"],
        })

    conn.close()
    return jsonify({"venta": dict(venta), "items": data})


@cambios_bp.get("/<int:cambio_id>")
def obtener_cambio(cambio_id):
    """Obtiene un cambio y sus ítems asociados.

    Parameters
    ----------
    cambio_id : int
        Identificador del cambio.

    Returns
    -------
    flask.Response
        JSON con los datos del cambio, la venta asociada y sus ítems.
        Devuelve HTTP 404 si el cambio no existe.
    """

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, v.codigo as venta_codigo, v.cliente as venta_cliente
        FROM cambios c
        JOIN ventas v ON c.venta_id = v.id
        WHERE c.id = ?
    """, (cambio_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Cambio no encontrado"}), 404

    c_dict = dict(row)
    cursor.execute("""
        SELECT ci.*, vp.codigo as var_codigo, vp.talle, vp.color, p.nombre as producto_nombre
        FROM cambio_items ci
        JOIN variantes_producto vp ON ci.variante_id = vp.id
        JOIN productos p ON vp.producto_id = p.id
        WHERE ci.cambio_id = ?
    """, (cambio_id,))
    c_dict["items"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(c_dict)


@cambios_bp.get("")
def listar_cambios():
    """Lista los cambios registrados, ordenados del más reciente al más antiguo.

    Permite paginar los resultados y filtrar los cambios por una fecha
    determinada según la hora local de Argentina.

    Query Parameters
    ----------------
    page : int, optional
        Número de página a consultar. Debe ser mayor o igual a 1.
        Por defecto es ``1``.

    page_size : int, optional
        Cantidad de cambios por página. Se establece un máximo de ``100``.
        Por defecto es ``20``.

    fecha : str, optional
        Fecha utilizada para filtrar los cambios, en formato
        ``YYYY-MM-DD``.

    Returns
    -------
    flask.Response
        Respuesta JSON con los cambios encontrados y la información
        de paginación. Cada cambio incluye sus ítems asociados.

        El objeto devuelto contiene:

        - ``data`` : lista de cambios.
        - ``total`` : cantidad total de cambios que cumplen el filtro.
        - ``page`` : número de página solicitada.
        - ``page_size`` : cantidad de elementos por página.

    Examples
    --------
    GET /cambios

    GET /cambios?page=2&page_size=10

    GET /cambios?fecha=2026-09-19

    GET /cambios?page=2&page_size=20&fecha=2026-09-19
    """
    
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(int(request.args.get("page_size", 20)), 100)
    desde = (page - 1) * page_size
    fecha = request.args.get("fecha")

    conn = get_db()
    cursor = conn.cursor()

    condiciones = []
    params = []
    if fecha:
        desde_utc, hasta_utc = _rango_utc_para_dia_local(fecha)
        condiciones.append("c.fecha >= ? AND c.fecha <= ?")
        params += [desde_utc, hasta_utc]
    filtro_sql = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""

    cursor.execute(f"SELECT COUNT(*) as total FROM cambios c{filtro_sql}", params)
    total = cursor.fetchone()["total"]

    cursor.execute(f"""
        SELECT c.*, v.codigo as venta_codigo, v.cliente as venta_cliente
        FROM cambios c
        JOIN ventas v ON c.venta_id = v.id
        {filtro_sql}
        ORDER BY c.fecha DESC
        LIMIT ? OFFSET ?
    """, (*params, page_size, desde))
    rows = cursor.fetchall()

    data = []
    for row in rows:
        c_dict = dict(row)
        cursor.execute("""
            SELECT ci.*, vp.codigo as var_codigo, vp.talle, vp.color, p.nombre as producto_nombre
            FROM cambio_items ci
            JOIN variantes_producto vp ON ci.variante_id = vp.id
            JOIN productos p ON vp.producto_id = p.id
            WHERE ci.cambio_id = ?
        """, (c_dict["id"],))
        items = [dict(r) for r in cursor.fetchall()]
        c_dict["items"] = items
        data.append(c_dict)

    conn.close()
    return jsonify({"data": data, "total": total, "page": page, "page_size": page_size})


def _ajustar_stock_variante(cursor, variante_id, delta, motivo):
    cursor.execute("SELECT stock_actual, producto_id FROM variantes_producto WHERE id = ?", (variante_id,))
    var = cursor.fetchone()
    if not var:
        return
    nuevo_stock = var["stock_actual"] + delta
    cursor.execute("UPDATE variantes_producto SET stock_actual = ? WHERE id = ?", (nuevo_stock, variante_id))
    cursor.execute("""
        INSERT INTO movimientos_stock (variante_id, tipo, cantidad, motivo)
        VALUES (?, 'ajuste', ?, ?)
    """, (variante_id, delta, motivo))
    # productos.stock_actual lo actualiza el trigger de schema.sql.


@cambios_bp.post("")
def crear_cambio():
    body = request.get_json(force=True) or {}
    venta_id = body.get("venta_id")
    items_devueltos = body.get("items_devueltos", [])
    items_nuevos = body.get("items_nuevos", [])
    monto_diferencia = body.get("monto_diferencia", 0)
    metodo_pago = body.get("metodo_pago")
    observaciones = body.get("observaciones", "")

    if not venta_id:
        return jsonify({"error": "venta_id es requerido"}), 400
    if not items_devueltos and not items_nuevos:
        return jsonify({"error": "El cambio necesita al menos un ítem devuelto o nuevo"}), 400
    if monto_diferencia and not metodo_pago:
        return jsonify({"error": "metodo_pago es requerido cuando hay diferencia de dinero"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if not venta:
        conn.close()
        return jsonify({"error": "Venta no encontrada"}), 404

    disponible = _cantidad_disponible_por_item(cursor, venta_id)

    items_devueltos_payload = []
    subtotal_devuelto = 0
    ganancia_devuelta = 0
    for item in items_devueltos:
        vid = item.get("variante_id")
        cantidad = item.get("cantidad")
        if vid is None or not isinstance(cantidad, (int, float)) or cantidad <= 0:
            conn.close()
            return jsonify({"error": f"Ítem devuelto inválido: {item}"}), 400
        info = disponible.get(vid)
        if not info:
            conn.close()
            return jsonify({"error": f"La variante {vid} no pertenece a esta venta"}), 400
        if cantidad > info["disponible"]:
            conn.close()
            return jsonify({
                "error": f"Solo hay {info['disponible']} unidad(es) disponibles para devolver de la variante {vid}"
            }), 400
        # Si la misma variante viene en otro ítem, ese se valida contra lo que queda.
        info["disponible"] -= cantidad

        subtotal = info["precio_unitario"] * cantidad
        ganancia_item = (info["precio_unitario"] - info["costo_unitario"]) * cantidad
        subtotal_devuelto += subtotal
        ganancia_devuelta += ganancia_item

        items_devueltos_payload.append({
            "variante_id": vid,
            "cantidad": cantidad,
            "precio_unitario": info["precio_unitario"],
            "costo_unitario": info["costo_unitario"],
        })

    items_nuevos_payload = []
    subtotal_nuevo = 0
    ganancia_nueva = 0
    # La misma variante puede venir en más de un ítem: el stock se valida contra la suma.
    pedido_por_variante = {}
    for item in items_nuevos:
        vid = item.get("variante_id")
        cantidad = item.get("cantidad")
        if vid is None or not isinstance(cantidad, (int, float)) or cantidad <= 0:
            conn.close()
            return jsonify({"error": f"Ítem nuevo inválido: {item}"}), 400

        cursor.execute("SELECT stock_actual, precio, costo FROM variantes_producto WHERE id = ?", (vid,))
        var = cursor.fetchone()
        if not var:
            conn.close()
            return jsonify({"error": f"Variante {vid} no encontrada"}), 400
        pedido_por_variante[vid] = pedido_por_variante.get(vid, 0) + cantidad
        if var["stock_actual"] < pedido_por_variante[vid]:
            conn.close()
            return jsonify({"error": f"Stock insuficiente para variante {vid}"}), 400

        precio_unitario = var["precio"]
        costo_unitario = var["costo"]
        subtotal = precio_unitario * cantidad
        ganancia_item = (precio_unitario - costo_unitario) * cantidad
        subtotal_nuevo += subtotal
        ganancia_nueva += ganancia_item

        items_nuevos_payload.append({
            "variante_id": vid,
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "costo_unitario": costo_unitario,
        })

    codigo_cambio = _generar_codigo_cambio(cursor)
    ganancia_neta = round(ganancia_nueva - ganancia_devuelta, 2)
    cursor.execute("""
        INSERT INTO cambios (venta_id, codigo, monto_diferencia, ganancia, metodo_pago, observaciones)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (venta_id, codigo_cambio, monto_diferencia, ganancia_neta, metodo_pago if monto_diferencia else None, observaciones))
    cambio_id = cursor.lastrowid

    for ip in items_devueltos_payload:
        cursor.execute("""
            INSERT INTO cambio_items (cambio_id, tipo, variante_id, cantidad, precio_unitario, costo_unitario)
            VALUES (?, 'devuelto', ?, ?, ?, ?)
        """, (cambio_id, ip["variante_id"], ip["cantidad"], ip["precio_unitario"], ip["costo_unitario"]))
        _ajustar_stock_variante(cursor, ip["variante_id"], ip["cantidad"], f"Devolución parcial - cambio {codigo_cambio}")

    for ip in items_nuevos_payload:
        cursor.execute("""
            INSERT INTO cambio_items (cambio_id, tipo, variante_id, cantidad, precio_unitario, costo_unitario)
            VALUES (?, 'nuevo', ?, ?, ?, ?)
        """, (cambio_id, ip["variante_id"], ip["cantidad"], ip["precio_unitario"], ip["costo_unitario"]))
        _ajustar_stock_variante(cursor, ip["variante_id"], -ip["cantidad"], f"Salida por cambio {codigo_cambio}")

    nuevo_total = venta["total"] + (subtotal_nuevo - subtotal_devuelto)
    # OJO: el total de la venta (usado por el dashboard como "ingresos")
    # debe reflejar el dinero real que entró/salió, no el valor calculado
    # de productos — porque el monto puede haber sido editado a mano.
    nuevo_total = venta["total"] + monto_diferencia
    nueva_ganancia = venta["ganancia"] + (ganancia_nueva - ganancia_devuelta)
    cursor.execute("""
        UPDATE ventas SET total = ?, ganancia = ?, tiene_cambio = 1 WHERE id = ?
    """, (round(nuevo_total, 2), round(nueva_ganancia, 2), venta_id))

    conn.commit()

    cursor.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,))
    cambio = dict(cursor.fetchone())
    conn.close()
    return jsonify(cambio), 201


def _revertir_cambio(cursor, cambio):
    """
    Devuelve (delta_total, delta_ganancia): lo que ese cambio le había
    sumado al total/ganancia de la venta (para poder restárselo).
    delta_total ahora es directamente el monto_diferencia guardado en el
    cambio (el dinero real que se movió), no el subtotal de productos.
    """
    cambio_id = cambio["id"]
    cursor.execute("SELECT * FROM cambio_items WHERE cambio_id = ?", (cambio_id,))
    items = cursor.fetchall()

    ganancia_devuelta = 0
    ganancia_nueva = 0

    for item in items:
        ganancia_item = (item["precio_unitario"] - item["costo_unitario"]) * item["cantidad"]

        if item["tipo"] == "devuelto":
            _ajustar_stock_variante(cursor, item["variante_id"], -item["cantidad"], f"Reversión de cambio {cambio['codigo']}")
            ganancia_devuelta += ganancia_item
        else:
            _ajustar_stock_variante(cursor, item["variante_id"], item["cantidad"], f"Reversión de cambio {cambio['codigo']}")
            ganancia_nueva += ganancia_item

    cursor.execute("DELETE FROM cambio_items WHERE cambio_id = ?", (cambio_id,))

    delta_total = cambio["monto_diferencia"] or 0
    delta_ganancia = ganancia_nueva - ganancia_devuelta
    return delta_total, delta_ganancia


@cambios_bp.delete("/<int:cambio_id>")
def borrar_cambio(cambio_id):
    """Revierte stock y totales de la venta, y borra el cambio."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,))
    cambio = cursor.fetchone()
    if not cambio:
        conn.close()
        return jsonify({"error": "Cambio no encontrado"}), 404

    venta_id = cambio["venta_id"]

    delta_total, delta_ganancia = _revertir_cambio(cursor, cambio)

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if venta:
        nuevo_total = venta["total"] - delta_total
        nueva_ganancia = venta["ganancia"] - delta_ganancia

        cursor.execute("DELETE FROM cambios WHERE id = ?", (cambio_id,))

        cursor.execute("SELECT COUNT(*) as total FROM cambios WHERE venta_id = ?", (venta_id,))
        quedan_cambios = cursor.fetchone()["total"] > 0

        cursor.execute("""
            UPDATE ventas SET total = ?, ganancia = ?, tiene_cambio = ? WHERE id = ?
        """, (round(nuevo_total, 2), round(nueva_ganancia, 2), 1 if quedan_cambios else 0, venta_id))
    else:
        cursor.execute("DELETE FROM cambios WHERE id = ?", (cambio_id,))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@cambios_bp.patch("/<int:cambio_id>")
def actualizar_cambio(cambio_id):
    """
    Edita un cambio: revierte su efecto actual (stock y totales) y vuelve a
    aplicarlo con los datos nuevos, validando disponibilidad y stock igual
    que al crear uno.
    """
    body = request.get_json(force=True) or {}
    items_devueltos = body.get("items_devueltos", [])
    items_nuevos = body.get("items_nuevos", [])
    monto_diferencia = body.get("monto_diferencia", 0)
    metodo_pago = body.get("metodo_pago")
    observaciones = body.get("observaciones", "")

    if not items_devueltos and not items_nuevos:
        return jsonify({"error": "El cambio necesita al menos un ítem devuelto o nuevo"}), 400
    if monto_diferencia and not metodo_pago:
        return jsonify({"error": "metodo_pago es requerido cuando hay diferencia de dinero"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,))
    cambio = cursor.fetchone()
    if not cambio:
        conn.close()
        return jsonify({"error": "Cambio no encontrado"}), 404

    venta_id = cambio["venta_id"]

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if not venta:
        conn.close()
        return jsonify({"error": "Venta no encontrada"}), 404

    # 1) Revertimos el efecto actual del cambio
    delta_total_viejo, delta_ganancia_viejo = _revertir_cambio(cursor, cambio)
    total_base = venta["total"] - delta_total_viejo
    ganancia_base = venta["ganancia"] - delta_ganancia_viejo

    # 2) Validamos los ítems nuevos, igual que en crear_cambio
    disponible = _cantidad_disponible_por_item(cursor, venta_id)

    items_devueltos_payload = []
    subtotal_devuelto = 0
    ganancia_devuelta = 0
    for item in items_devueltos:
        vid = item.get("variante_id")
        cantidad = item.get("cantidad")
        if vid is None or not isinstance(cantidad, (int, float)) or cantidad <= 0:
            conn.close()
            return jsonify({"error": f"Ítem devuelto inválido: {item}"}), 400
        info = disponible.get(vid)
        if not info:
            conn.close()
            return jsonify({"error": f"La variante {vid} no pertenece a esta venta"}), 400
        if cantidad > info["disponible"]:
            conn.close()
            return jsonify({
                "error": f"Solo hay {info['disponible']} unidad(es) disponibles para devolver de la variante {vid}"
            }), 400
        # Si la misma variante viene en otro ítem, ese se valida contra lo que queda.
        info["disponible"] -= cantidad

        subtotal = info["precio_unitario"] * cantidad
        ganancia_item = (info["precio_unitario"] - info["costo_unitario"]) * cantidad
        subtotal_devuelto += subtotal
        ganancia_devuelta += ganancia_item

        items_devueltos_payload.append({
            "variante_id": vid, "cantidad": cantidad,
            "precio_unitario": info["precio_unitario"], "costo_unitario": info["costo_unitario"],
        })

    items_nuevos_payload = []
    subtotal_nuevo = 0
    ganancia_nueva = 0
    # La misma variante puede venir en más de un ítem: el stock se valida contra la suma.
    pedido_por_variante = {}
    for item in items_nuevos:
        vid = item.get("variante_id")
        cantidad = item.get("cantidad")
        if vid is None or not isinstance(cantidad, (int, float)) or cantidad <= 0:
            conn.close()
            return jsonify({"error": f"Ítem nuevo inválido: {item}"}), 400

        cursor.execute("SELECT stock_actual, precio, costo FROM variantes_producto WHERE id = ?", (vid,))
        var = cursor.fetchone()
        if not var:
            conn.close()
            return jsonify({"error": f"Variante {vid} no encontrada"}), 400
        pedido_por_variante[vid] = pedido_por_variante.get(vid, 0) + cantidad
        if var["stock_actual"] < pedido_por_variante[vid]:
            conn.close()
            return jsonify({"error": f"Stock insuficiente para variante {vid}"}), 400

        precio_unitario = var["precio"]
        costo_unitario = var["costo"]
        subtotal = precio_unitario * cantidad
        ganancia_item = (precio_unitario - costo_unitario) * cantidad
        subtotal_nuevo += subtotal
        ganancia_nueva += ganancia_item

        items_nuevos_payload.append({
            "variante_id": vid, "cantidad": cantidad,
            "precio_unitario": precio_unitario, "costo_unitario": costo_unitario,
        })

    # 3) Aplicamos el nuevo estado
    for ip in items_devueltos_payload:
        cursor.execute("""
            INSERT INTO cambio_items (cambio_id, tipo, variante_id, cantidad, precio_unitario, costo_unitario)
            VALUES (?, 'devuelto', ?, ?, ?, ?)
        """, (cambio_id, ip["variante_id"], ip["cantidad"], ip["precio_unitario"], ip["costo_unitario"]))
        _ajustar_stock_variante(cursor, ip["variante_id"], ip["cantidad"], f"Devolución parcial - cambio {cambio['codigo']} (editado)")

    for ip in items_nuevos_payload:
        cursor.execute("""
            INSERT INTO cambio_items (cambio_id, tipo, variante_id, cantidad, precio_unitario, costo_unitario)
            VALUES (?, 'nuevo', ?, ?, ?, ?)
        """, (cambio_id, ip["variante_id"], ip["cantidad"], ip["precio_unitario"], ip["costo_unitario"]))
        _ajustar_stock_variante(cursor, ip["variante_id"], -ip["cantidad"], f"Salida por cambio {cambio['codigo']} (editado)")

    cursor.execute("""
        UPDATE cambios SET monto_diferencia = ?, ganancia = ?, metodo_pago = ?, observaciones = ? WHERE id = ?
    """, (
        monto_diferencia,
        round(ganancia_nueva - ganancia_devuelta, 2),
        metodo_pago if monto_diferencia else None,
        observaciones,
        cambio_id
    ))

    nuevo_total = total_base + monto_diferencia
    nueva_ganancia = ganancia_base + (ganancia_nueva - ganancia_devuelta)
    cursor.execute("""
        UPDATE ventas SET total = ?, ganancia = ?, tiene_cambio = 1 WHERE id = ?
    """, (round(nuevo_total, 2), round(nueva_ganancia, 2), venta_id))

    conn.commit()

    cursor.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,))
    actualizado = dict(cursor.fetchone())
    conn.close()
    return jsonify(actualizado)


@cambios_bp.patch("/<int:cambio_id>/observaciones")
def actualizar_observaciones_cambio(cambio_id):
    """Edita solo las observaciones (la nota) de un cambio.

    A diferencia de ``PATCH /<id>``, no revierte ni vuelve a aplicar el
    cambio: no toca stock, ítems ni totales.
    """
    body = request.get_json(force=True) or {}
    observaciones = body.get("observaciones") or ""

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE cambios SET observaciones = ? WHERE id = ?", (observaciones, cambio_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Cambio no encontrado"}), 404

    conn.commit()
    cursor.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,))
    actualizado = dict(cursor.fetchone())
    conn.close()
    return jsonify(actualizado)
