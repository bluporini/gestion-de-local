from flask import Blueprint, request, jsonify
from app.database import get_db
from datetime import datetime, timedelta, timezone

ventas_bp = Blueprint("ventas", __name__, url_prefix="/api/ventas")

# Argentina es UTC-3 (sin horario de verano)
OFFSET_ARGENTINA_HORAS = 3 

def _rango_utc_para_dia_local(fecha_str):
    """Convierte un día local de Argentina en su rango equivalente en UTC.

    La fecha recibida representa un día calendario en hora local de
    Argentina. Como las fechas de la base de datos se almacenan en UTC,
    se calcula el intervalo UTC correspondiente a todo ese día local.

    Parameters
    ----------
    fecha_str : str
        Fecha local de Argentina en formato ``YYYY-MM-DD``.

    Returns
    -------
    tuple[str, str]
        Par ``(desde_utc, hasta_utc)`` con el inicio y el final del día
        expresados en UTC, en formato ``YYYY-MM-DD HH:MM:SS``.

    Notes
    -----
    El rango incluye todo el día local, desde las 00:00:00 hasta las
    23:59:59. Se utiliza ``OFFSET_ARGENTINA_HORAS`` para realizar la
    conversión a UTC.

    Examples
    --------
    Para ``"2026-09-19"`` devuelve el rango UTC correspondiente al
    19 de septiembre completo en hora de Argentina.
    """

    inicio_local = datetime.strptime(fecha_str, "%Y-%m-%d")
    desde_utc = inicio_local + timedelta(hours=OFFSET_ARGENTINA_HORAS)
    hasta_utc = desde_utc + timedelta(days=1) - timedelta(seconds=1)

    return desde_utc.strftime("%Y-%m-%d %H:%M:%S"), hasta_utc.strftime("%Y-%m-%d %H:%M:%S")

def _generar_codigo_venta(cursor):
    """Genera el próximo código secuencial de venta del día.

    El código tiene el formato ``DDMMYYNNNV``, donde:

    - ``DDMMYY`` corresponde a la fecha local de Argentina.
    - ``NNN`` es un número secuencial de tres dígitos.
    - ``V`` identifica que el código corresponde a una venta.

    La numeración comienza en ``001`` cada día y se determina a partir
    del mayor número de venta existente para esa fecha.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor utilizado para consultar los códigos de venta existentes.

    Returns
    -------
    str
        Próximo código de venta generado.

    Notes
    -----
    La fecha utilizada para generar el código corresponde al día local
    de Argentina, aunque las fechas almacenadas en la base de datos se
    manejen en UTC.

    Examples
    --------
    Si la fecha local es 19/09/2026 y la última venta del día es
    ``190926007V``, el siguiente código será ``190926008V``.

    Si todavía no existen ventas para ese día, el código será
    ``190926001V``.
    """

    ahora_local = datetime.now(timezone.utc) - timedelta(hours=OFFSET_ARGENTINA_HORAS)
    clave_dia = ahora_local.strftime("%d%m%y")

    cursor.execute("SELECT codigo FROM ventas WHERE codigo LIKE ?", (f"{clave_dia}%",))
    max_num = 0
    for row in cursor.fetchall():
        codigo = row["codigo"] or ""
        cuerpo = codigo[len(clave_dia):-1]  # saca la fecha del inicio y la "V" del final
        if cuerpo.isdigit():
            max_num = max(max_num, int(cuerpo))

    return f"{clave_dia}{max_num + 1:03d}V"

@ventas_bp.get("")
def listar_ventas():
    """Lista las ventas ordenadas de más reciente a más antigua.

    Permite filtrar las ventas por un día determinado y paginar los
    resultados. Cuando se especifica una fecha, esta se interpreta como
    un día calendario en hora local de Argentina y se convierte al rango
    UTC correspondiente para consultar la base de datos.

    Cada venta incluye sus ítems asociados junto con los datos de la
    variante y del producto correspondiente.

    Query Parameters
    ----------------
    fecha : str, optional
        Día por el cual filtrar las ventas, en formato ``YYYY-MM-DD``.
        Se interpreta según la fecha local de Argentina.

    page : int, optional
        Número de página. Comienza en 1. Por defecto es ``1``.

    page_size : int, optional
        Cantidad máxima de ventas por página. Por defecto es ``20`` y
        se limita a un máximo de ``100``.

    Returns
    -------
    flask.Response
        Respuesta JSON con las siguientes claves:

        ``data``
            Lista de ventas correspondientes a la página solicitada.
            Cada venta incluye sus ítems en ``venta_items``.

        ``total``
            Cantidad total de ventas que cumplen el filtro.

        ``page``
            Número de página solicitado.

        ``page_size``
            Cantidad de elementos por página.

    Examples
    --------
    Obtener las primeras 20 ventas::

        GET /ventas

    Obtener la segunda página con 10 ventas::

        GET /ventas?page=2&page_size=10

    Obtener las ventas del 19 de septiembre de 2026::

        GET /ventas?fecha=2026-09-19
    """

    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(int(request.args.get("page_size", 20)), 100)
    desde = (page - 1) * page_size

    fecha = request.args.get("fecha")

    conn = get_db()
    cursor = conn.cursor()

    desde_utc = hasta_utc = None
    if fecha:
        desde_utc, hasta_utc = _rango_utc_para_dia_local(fecha)

    if fecha:
        cursor.execute("""
            SELECT COUNT(*) as total FROM ventas 
            WHERE fecha >= ? AND fecha <= ?
        """, (desde_utc, hasta_utc))
    else:
        cursor.execute("SELECT COUNT(*) as total FROM ventas")

    total = cursor.fetchone()["total"]

    if fecha:
        cursor.execute("""
            SELECT * FROM ventas 
            WHERE fecha >= ? AND fecha <= ?
            ORDER BY fecha DESC LIMIT ? OFFSET ?
        """, (desde_utc, hasta_utc, page_size, desde))
    else:
        cursor.execute("""
            SELECT * FROM ventas 
            ORDER BY fecha DESC LIMIT ? OFFSET ?
        """, (page_size, desde))

    ventas_rows = cursor.fetchall()
    data = []

    for v in ventas_rows:
        v_dict = dict(v)
        # Obtener los ítems de la venta con detalles de variantes y productos
        cursor.execute("""
            SELECT vi.*, vp.codigo as var_codigo, vp.talle, vp.color, p.nombre as prod_nombre
            FROM venta_items vi
            JOIN variantes_producto vp ON vi.variante_id = vp.id
            JOIN productos p ON vp.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (v_dict["id"],))

        items = []
        for item_row in cursor.fetchall():
            item_dict = dict(item_row)
            item_dict["variantes_producto"] = {
                "codigo": item_dict.pop("var_codigo"),
                "talle": item_dict.pop("talle"),
                "color": item_dict.pop("color"),
                "productos": {"nombre": item_dict.pop("prod_nombre")}
            }
            items.append(item_dict)

        v_dict["venta_items"] = items
        data.append(v_dict)

    conn.close()

    return jsonify({
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    })

@ventas_bp.get("/buscar")
def buscar_ventas():
    """Busca ventas realizadas por código o nombre de cliente.

    El endpoint está destinado a localizar una venta para iniciar un
    cambio. Solo se consideran ventas con estado ``"realizada"``.

    La búsqueda se realiza parcialmente sobre los campos ``codigo`` y
    ``cliente`` y los resultados se ordenan desde la venta más reciente.
    Se devuelven como máximo 15 ventas.

    Query Parameters
    ----------------
    q : str
        Texto utilizado para buscar coincidencias en el código de la
        venta o en el nombre del cliente.

    Returns
    -------
    flask.Response
        Respuesta JSON con una lista de ventas coincidentes. Cada venta
        incluye sus ítems en ``venta_items``, junto con los datos de la
        variante y del producto.

        Si ``q`` está vacío, devuelve una lista vacía.

    Examples
    --------
    Buscar por código o cliente::

        GET /ventas/buscar?q=190926

    Buscar por nombre de cliente::

        GET /ventas/buscar?q=Juan
    """

    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    conn = get_db()
    cursor = conn.cursor()
    comodin = f"%{q}%"
    cursor.execute("""
        SELECT * FROM ventas
        WHERE estado = 'realizada' AND (codigo LIKE ? OR cliente LIKE ?)
        ORDER BY fecha DESC LIMIT 15
    """, (comodin, comodin))
    ventas_rows = cursor.fetchall()

    data = []
    for v in ventas_rows:
        v_dict = dict(v)
        cursor.execute("""
            SELECT vi.*, vp.codigo as var_codigo, vp.talle, vp.color, p.nombre as prod_nombre
            FROM venta_items vi
            JOIN variantes_producto vp ON vi.variante_id = vp.id
            JOIN productos p ON vp.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (v_dict["id"],))
        items = []
        for item_row in cursor.fetchall():
            item_dict = dict(item_row)
            item_dict["variantes_producto"] = {
                "codigo": item_dict.pop("var_codigo"),
                "talle": item_dict.pop("talle"),
                "color": item_dict.pop("color"),
                "productos": {"nombre": item_dict.pop("prod_nombre")}
            }
            items.append(item_dict)
        v_dict["venta_items"] = items
        data.append(v_dict)

    conn.close()
    return jsonify(data)

@ventas_bp.post("")
def crear_venta():
    """Crea una venta, registra sus ítems y actualiza el stock.

    Valida los datos de la venta, verifica la disponibilidad de stock,
    calcula el total y la ganancia, registra la venta y sus ítems,
    descuenta las cantidades vendidas de las variantes y actualiza el
    stock total de los productos afectados.

    Las ventas se crean inicialmente con estado ``"realizada"``.

    JSON Parameters
    ---------------
    cliente : str, optional
        Nombre o identificación del cliente.

    metodo_pago : str
        Método de pago utilizado. Los valores admitidos son
        ``"efectivo"``, ``"tarjeta_credito"`` y ``"tarjeta_debito"``.

    tipo_tarjeta : str, optional
        Tipo de tarjeta utilizado. Es obligatorio cuando ``metodo_pago``
        es ``"tarjeta_credito"`` o ``"tarjeta_debito"``.

    monto_pagado : float, optional
        Importe entregado por el cliente. Es obligatorio cuando el
        método de pago es ``"efectivo"`` y debe ser igual o mayor al
        total de la venta.

    items : list of dict
        Ítems incluidos en la venta. Cada elemento debe contener:

        ``variante_id``
            Identificador de la variante vendida.

        ``cantidad``
            Cantidad vendida de la variante. Debe ser mayor que cero.

    Returns
    -------
    flask.Response
        Respuesta JSON con los datos de la venta creada y código HTTP
        ``201``.

    Raises
    ------
    400
        Si faltan datos requeridos, el formato de ``items`` es inválido,
        el método de pago requiere información adicional, una variante
        no existe, no hay stock suficiente o el monto pagado es menor
        que el total.

    Notes
    -----
    El precio y el costo unitarios se obtienen de la variante al momento
    de crear la venta. La ganancia de cada ítem se calcula como:

    ``(precio_unitario - costo_unitario) * cantidad``

    El stock se descuenta de cada variante y posteriormente se recalcula
    el stock total de cada producto afectado como la suma del stock de
    todas sus variantes.

    Para pagos en efectivo se calcula el vuelto. Para otros métodos de
    pago, ``monto_pagado`` y ``vuelto`` se almacenan como ``None``.

    La venta y sus ítems se confirman mediante una única transacción
    antes de devolver la respuesta.

    Examples
    --------
    Ejemplo de solicitud::

        POST /ventas

        {
            "cliente": "Juan",
            "metodo_pago": "efectivo",
            "monto_pagado": 25000,
            "items": [
                {
                    "variante_id": 12,
                    "cantidad": 2
                }
            ]
        }

    Respuesta exitosa::

        HTTP 201
        {
            "id": 25,
            "codigo": "190926001V",
            ...
        }
    """

    body = request.get_json(force=True) or {}
    cliente = body.get("cliente")
    metodo_pago = body.get("metodo_pago")
    items = body.get("items", [])
    tipo_tarjeta = body.get("tipo_tarjeta")
    monto_pagado = body.get("monto_pagado")

    if not metodo_pago or not items:
        return jsonify({"error": "metodo_pago e items son requeridos"}), 400

    if not isinstance(items, list):
        return jsonify({"error": "items debe ser una lista"}), 400

    if metodo_pago == "efectivo" and monto_pagado is None:
        return jsonify({"error": "monto_pagado es requerido cuando el método de pago es efectivo"}), 400

    if metodo_pago in ("tarjeta_credito", "tarjeta_debito") and not tipo_tarjeta:
        return jsonify({"error": "tipo_tarjeta es requerido para pagos con tarjeta"}), 400

    conn = get_db()
    cursor = conn.cursor()

    items_payload = []
    total = 0
    ganancia_total = 0
    # Cantidad pedida por variante en toda la venta: el carrito puede traer
    # la misma variante en más de un ítem, y el stock se valida contra la suma.
    pedido_por_variante = {}

    for item in items:
        if not isinstance(item, dict):
            conn.close()
            return jsonify({"error": "Cada item debe ser un objeto con variante_id y cantidad"}), 400

        var_id = item.get("variante_id")
        cantidad = item.get("cantidad")

        if var_id is None or cantidad is None:
            conn.close()
            return jsonify({"error": "Cada item requiere variante_id y cantidad"}), 400

        if not isinstance(cantidad, (int, float)) or cantidad <= 0:
            conn.close()
            return jsonify({"error": f"Cantidad inválida para variante {var_id}"}), 400

        cursor.execute("""
            SELECT vp.id, vp.stock_actual as stock, vp.producto_id, vp.costo, vp.precio as precio_venta
            FROM variantes_producto vp
            WHERE vp.id = ?
        """, (var_id,))
        variante = cursor.fetchone()

        if not variante:
            conn.close()
            return jsonify({"error": f"Variante {var_id} no encontrada"}), 400

        pedido_por_variante[var_id] = pedido_por_variante.get(var_id, 0) + cantidad
        if variante["stock"] < pedido_por_variante[var_id]:
            conn.close()
            return jsonify({"error": f"Stock insuficiente para variante {var_id}"}), 400

        precio_unitario = variante["precio_venta"]
        costo_unitario = variante["costo"]
        subtotal = round(precio_unitario * cantidad, 2)
        ganancia_item = round((precio_unitario - costo_unitario) * cantidad, 2)

        total += subtotal
        ganancia_total += ganancia_item

        items_payload.append({
            "variante_id": var_id,
            "cantidad": cantidad,
            "precio_unitario": precio_unitario,
            "costo_unitario": costo_unitario,
            "subtotal": subtotal,
            "ganancia_item": ganancia_item,
            "producto_id": variante["producto_id"]
        })

    total = round(total, 2)

    if metodo_pago == "efectivo" and monto_pagado < total:
        conn.close()
        return jsonify({"error": "El monto pagado es menor al total de la venta"}), 400

    vuelto = round(monto_pagado - total, 2) if metodo_pago == "efectivo" else None

    codigo_venta = _generar_codigo_venta(cursor)

    # Insertar la venta
    cursor.execute("""
        INSERT INTO ventas (codigo, cliente, metodo_pago, tipo_tarjeta, monto_pagado, vuelto, total, ganancia, estado, total_base, ganancia_base)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'realizada', ?, ?)
    """, (
        codigo_venta,
        cliente,
        metodo_pago,
        tipo_tarjeta if metodo_pago in ("tarjeta_credito", "tarjeta_debito") else None,
        monto_pagado if metodo_pago == "efectivo" else None,
        vuelto,
        total,
        round(ganancia_total, 2),
        total,
        round(ganancia_total, 2)
    ))

    venta_id = cursor.lastrowid

    # Insertar ítems y descontar stock por variante y producto
    for ip in items_payload:
        cursor.execute("""
            INSERT INTO venta_items (venta_id, producto_id, variante_id, cantidad, precio_unitario, costo_unitario, subtotal, ganancia_item)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            venta_id, ip["producto_id"], ip["variante_id"], ip["cantidad"],
            ip["precio_unitario"], ip["costo_unitario"], ip["subtotal"], ip["ganancia_item"]
        ))

        # Descontar stock de la variante
        cursor.execute("""
            UPDATE variantes_producto 
            SET stock_actual = stock_actual - ? 
            WHERE id = ?
        """, (ip["cantidad"], ip["variante_id"]))

    conn.commit()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = dict(cursor.fetchone())
    conn.close()

    return jsonify(venta), 201


@ventas_bp.patch("/<int:venta_id>")
def editar_venta(venta_id):
    """Actualiza datos generales de una venta.

    Permite modificar únicamente el cliente y el método de pago de una
    venta existente. No modifica sus ítems, cantidades, precios, total,
    ganancia ni stock.

    Parameters
    ----------
    venta_id : int
        Identificador de la venta que se desea actualizar.

    JSON Parameters
    ---------------
    cliente : str, optional
        Nombre o identificación del cliente.

    metodo_pago : str, optional
        Nuevo método de pago de la venta.

    Returns
    -------
    flask.Response
        Respuesta JSON con los datos actualizados de la venta.

        Devuelve HTTP 400 si no se proporciona ningún campo válido y
        HTTP 404 si la venta no existe.

    Notes
    -----
    Los campos distintos de ``cliente`` y ``metodo_pago`` se ignoran.
    """

    body = request.get_json(force=True) or {}
    campos_permitidos = ["cliente", "metodo_pago"]
    payload = {k: v for k, v in body.items() if k in campos_permitidos}

    if not payload:
        return jsonify({"error": "Nada para actualizar"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": "Venta no encontrada"}), 404

    cliente = payload.get("cliente")
    metodo_pago = payload.get("metodo_pago")

    if cliente is not None and metodo_pago is not None:
        cursor.execute("UPDATE ventas SET cliente = ?, metodo_pago = ? WHERE id = ?", (cliente, metodo_pago, venta_id))
    elif cliente is not None:
        cursor.execute("UPDATE ventas SET cliente = ? WHERE id = ?", (cliente, venta_id))
    elif metodo_pago is not None:
        cursor.execute("UPDATE ventas SET metodo_pago = ? WHERE id = ?", (metodo_pago, venta_id))

    conn.commit()
    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = dict(cursor.fetchone())
    conn.close()

    return jsonify(venta)


@ventas_bp.delete("/<int:venta_id>")
def borrar_venta(venta_id):
    """Elimina definitivamente una venta y revierte sus efectos en stock.

    Si la venta existe, primero revierte los cambios asociados a ella.
    Luego, si la venta tenía estado ``"realizada"``, repone en stock las
    cantidades correspondientes a sus ítems.

    Los movimientos de reposición se registran en ``movimientos_stock``
    con tipo ``"devolucion"``. Finalmente, se eliminan los ítems y la
    venta.

    Parameters
    ----------
    venta_id : int
        Identificador de la venta que se desea eliminar.

    Returns
    -------
    flask.Response
        Respuesta JSON con ``{"ok": True}`` si la venta fue eliminada.

        Devuelve HTTP 404 si la venta no existe.

    Notes
    -----
    Los cambios asociados a la venta deben revertirse antes de eliminar
    la venta, ya que la eliminación posterior podría borrar en cascada
    los registros de cambios sin revertir previamente sus efectos sobre
    el stock.

    Si la venta no tiene estado almacenado, se considera
    ``"realizada"`` por compatibilidad con registros anteriores.

    La reposición del stock se realiza por variante y posteriormente se
    recalcula el stock total del producto afectado.
    """

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if not venta:
        conn.close()
        return jsonify({"error": "venta no encontrada"}), 404

    estado = venta["estado"] if "estado" in venta.keys() else "realizada"

    # Igual que en la devolución total: si tuvo cambios, deshacerlos
    # primero (si no, el DELETE en cascada de cambios se lleva puesto los
    # registros pero nunca repone/descuenta el stock que esos cambios
    # habían movido).
    _revertir_cambios_de_venta(cursor, venta_id)

    if estado == "realizada":
        cursor.execute("SELECT * FROM venta_items WHERE venta_id = ?", (venta_id,))
        items = cursor.fetchall()
        for item in items:
            var_id = item["variante_id"]
            cantidad = item["cantidad"]

            cursor.execute("SELECT stock_actual, producto_id FROM variantes_producto WHERE id = ?", (var_id,))
            var = cursor.fetchone()
            if var:
                nuevo_stock = var["stock_actual"] + cantidad
                cursor.execute("UPDATE variantes_producto SET stock_actual = ? WHERE id = ?", (nuevo_stock, var_id))

                # Registrar movimiento
                cursor.execute("""
                    INSERT INTO movimientos_stock (variante_id, tipo, cantidad, motivo)
                    VALUES (?, 'devolucion', ?, ?)
                """, (var_id, cantidad, f"Venta {venta_id} borrada"))

    cursor.execute("DELETE FROM venta_items WHERE venta_id = ?", (venta_id,))
    cursor.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@ventas_bp.post("/<int:venta_id>/devolucion")
def marcar_devolucion(venta_id):
    """Marca una venta como devuelta y repone sus ítems en stock.

    Revierte primero los cambios asociados a la venta, de modo que el
    stock quede en el estado correspondiente únicamente a la venta
    original. Luego repone las cantidades de todos sus ítems y registra
    los movimientos de stock correspondientes.

    Finalmente, marca la venta con estado ``"devolucion"`` y restaura
    ``total`` y ``ganancia`` a los valores originales almacenados en
    ``total_base`` y ``ganancia_base``.

    Parameters
    ----------
    venta_id : int
        Identificador de la venta que se desea marcar como devolución.

    Returns
    -------
    flask.Response
        Respuesta JSON con los datos actualizados de la venta.

        Devuelve HTTP 404 si la venta no existe y HTTP 400 si la venta
        ya estaba marcada como devolución.

    Notes
    -----
    Los cambios asociados se revierten antes de reponer los ítems de la
    venta original. Esto evita duplicar o saltear movimientos de stock.

    Por cada ítem se incrementa el stock de su variante y se registra un
    movimiento de tipo ``"devolucion"``. Luego se recalcula el stock total
    del producto a partir de sus variantes.

    Una venta marcada como ``"devolucion"`` deja de considerarse en los
    cálculos de ingresos y ganancias del sistema.
    """

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    if not venta:
        conn.close()
        return jsonify({"error": "venta no encontrada"}), 404

    estado = venta["estado"] if "estado" in venta.keys() else "realizada"
    if estado == "devolucion":
        conn.close()
        return jsonify({"error": "la venta ya estaba marcada como devolución"}), 400

    # Si esta venta tuvo cambios, hay que deshacerlos primero: así el stock
    # queda "como si solo hubiera existido la venta original", y lo que
    # sigue (reponer venta_items) es correcto sin duplicar ni saltear nada.
    _revertir_cambios_de_venta(cursor, venta_id)

    cursor.execute("SELECT * FROM venta_items WHERE venta_id = ?", (venta_id,))
    items = cursor.fetchall()

    for item in items:
        var_id = item["variante_id"]
        cantidad = item["cantidad"]

        cursor.execute("SELECT stock_actual, producto_id FROM variantes_producto WHERE id = ?", (var_id,))
        var = cursor.fetchone()
        if var:
            nuevo_stock = var["stock_actual"] + cantidad
            cursor.execute("UPDATE variantes_producto SET stock_actual = ? WHERE id = ?", (nuevo_stock, var_id))

            cursor.execute("""
                INSERT INTO movimientos_stock (variante_id, tipo, cantidad, motivo)
                VALUES (?, 'devolucion', ?, ?)
            """, (var_id, cantidad, f"Devolución venta {venta_id}"))


    # Volvemos el total/ganancia al valor original de la venta (sin el
    # agregado de los cambios que acabamos de revertir), por prolijidad —
    # aunque al estar en estado "devolucion" ya se excluye de los ingresos.
    cursor.execute("SELECT total_base, ganancia_base FROM ventas WHERE id = ?", (venta_id,))
    base = cursor.fetchone()
    if base:
        cursor.execute("UPDATE ventas SET total = ?, ganancia = ? WHERE id = ?", (base["total_base"], base["ganancia_base"], venta_id))


    cursor.execute("UPDATE ventas SET estado = 'devolucion' WHERE id = ?", (venta_id,))
    conn.commit()

    cursor.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    return jsonify(updated)

def _revertir_cambios_de_venta(cursor, venta_id):
    """Revierte y elimina todos los cambios asociados a una venta.

    Deshace los efectos de stock producidos por cada cambio asociado a
    la venta y luego elimina sus registros. Al finalizar, el stock queda
    en el estado que tendría si los cambios nunca hubieran existido.

    Para cada ítem del cambio:

    - ``"devuelto"``: se descuenta del stock la cantidad que había sido
      repuesta cuando se registró la devolución.
    - ``"nuevo"``: se repone en stock la cantidad que había sido
      descontada cuando se registró el nuevo artículo.

    Finalmente, elimina los ítems y los cambios asociados y establece
    ``tiene_cambio`` en ``0`` para la venta.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor utilizado para consultar, actualizar y eliminar los
        registros asociados.
    venta_id : int
        Identificador de la venta cuyos cambios deben revertirse.

    Notes
    -----
    Esta función debe ejecutarse antes de una devolución total o antes
    de eliminar una venta. Después de su ejecución, esas operaciones
    pueden trabajar únicamente con los ``venta_items`` originales sin
    duplicar ni omitir movimientos de stock.

    La función elimina físicamente los registros de ``cambios`` y
    ``cambio_items`` asociados a la venta.
    """

    cursor.execute("SELECT * FROM cambios WHERE venta_id = ?", (venta_id,))
    cambios = cursor.fetchall()

    for cambio in cambios:
        cursor.execute("SELECT * FROM cambio_items WHERE cambio_id = ?", (cambio["id"],))
        items = cursor.fetchall()

        for item in items:
            if item["tipo"] == "devuelto":
                # Al crear el cambio esto sumó stock (el cliente lo devolvió).
                # Al revertir, restamos esa reposición.
                _revertir_ajuste_stock(cursor, item["variante_id"], -item["cantidad"], f"Reversión de cambio {cambio['codigo']} (devolución total)")
            else:  # 'nuevo'
                # Al crear el cambio esto restó stock (salió vendido).
                # Al revertir, lo devolvemos.
                _revertir_ajuste_stock(cursor, item["variante_id"], item["cantidad"], f"Reversión de cambio {cambio['codigo']} (devolución total)")

        cursor.execute("DELETE FROM cambio_items WHERE cambio_id = ?", (cambio["id"],))
        cursor.execute("DELETE FROM cambios WHERE id = ?", (cambio["id"],))

    cursor.execute("UPDATE ventas SET tiene_cambio = 0 WHERE id = ?", (venta_id,))


def _revertir_ajuste_stock(cursor, variante_id, delta, motivo):
    """Revierte un ajuste de stock y actualiza el stock del producto.

    Modifica el stock actual de una variante aplicando ``delta``, registra
    el movimiento en ``movimientos_stock`` y recalcula el stock total del
    producto sumando el stock de todas sus variantes.

    Si la variante no existe, no realiza ninguna operación.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor utilizado para consultar y actualizar la base de datos.
    variante_id : int
        Identificador de la variante cuyo stock se modifica.
    delta : int
        Cantidad que se suma al stock actual de la variante. Puede ser
        positiva o negativa según el ajuste que se quiera realizar.
    motivo : str
        Descripción del motivo del movimiento de stock.

    Notes
    -----
    El movimiento generado se registra con tipo ``"ajuste"``.

    Después de modificar la variante, el stock total del producto se
    recalcula como la suma del stock actual de todas sus variantes.
    """

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
