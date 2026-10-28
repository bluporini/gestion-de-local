from flask import Blueprint, request, jsonify
from app.database import get_db
from app.routes.configuracion import leer_umbral_stock_bajo

productos_bp = Blueprint("productos", __name__, url_prefix="/api/productos")


def _serializar_producto(prod_dict):
    """Adapta un producto al formato esperado por el frontend.

    Renombra las claves ``costo`` y ``precio`` como
    ``precio_costo`` y ``precio_venta``, respectivamente.
    Si alguna clave no existe, asigna ``None``.

    Parameters
    ----------
    prod_dict : dict
        Datos del producto obtenidos de la base de datos.

    Returns
    -------
    dict
        El mismo diccionario con las claves adaptadas al formato
        esperado por el frontend.
    """

    prod_dict["precio_costo"] = prod_dict.pop("costo", None)
    prod_dict["precio_venta"] = prod_dict.pop("precio", None)

    return prod_dict


def _serializar_variante(var_dict):
    """Adapta una variante al formato esperado por el frontend.

    Renombra las claves ``costo`` y ``precio`` como
    ``precio_costo`` y ``precio_venta``, respectivamente.
    Si alguna clave no existe, asigna ``None``.

    Parameters
    ----------
    var_dict : dict
        Datos de la variante obtenidos de la base de datos.

    Returns
    -------
    dict
        El mismo diccionario con las claves adaptadas al formato
        esperado por el frontend.
    """

    var_dict["precio_costo"] = var_dict.pop("costo", None)
    var_dict["precio_venta"] = var_dict.pop("precio", None)
    return var_dict

def _siguiente_secuencial_variante(cursor, producto_id, producto_codigo):
    """Obtiene el próximo número secuencial de variante de un producto.

    Busca las variantes existentes del producto y determina el mayor
    número secuencial utilizado en sus códigos. El siguiente número
    se obtiene incrementando dicho máximo en uno.

    El número no se reutiliza aunque existan variantes eliminadas.
    Por ejemplo, si existen las variantes ``REM-1`` y ``REM-3``,
    la siguiente variante será ``REM-4``.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor utilizado para consultar las variantes existentes.
    producto_id : int
        Identificador del producto al que pertenece la variante.
    producto_codigo : str
        Código base del producto utilizado como prefijo del código
        de la variante.

    Returns
    -------
    int
        Próximo número secuencial disponible para la variante.

    Notes
    -----
    Solo se consideran códigos que comienzan con ``producto_codigo + "-"``
    y cuyo primer segmento posterior al prefijo sea numérico.
    """

    cursor.execute("SELECT codigo FROM variantes_producto WHERE producto_id = ?", (producto_id,))
    prefijo_busqueda = f"{producto_codigo}-"
    max_num = 0
    for row in cursor.fetchall():
        codigo = row["codigo"] or ""
        if codigo.startswith(prefijo_busqueda):
            primer_segmento = codigo[len(prefijo_busqueda):].split("-")[0]
            if primer_segmento.isdigit():
                max_num = max(max_num, int(primer_segmento))

    return max_num + 1   


@productos_bp.get("")
def listar_productos():
    """Lista productos con paginación, búsqueda y filtro por stock.

    Permite obtener los productos paginados y filtrar los resultados por
    nombre o código. Por defecto, solo se incluyen productos con stock
    disponible.

    Cada producto incluye sus variantes asociadas y los datos del tipo de
    prenda.

    Query Parameters
    ----------------
    page : int, optional
        Número de página. Comienza en 1. Por defecto, ``1``.
    page_size : int, optional
        Cantidad de productos por página. Por defecto, ``20`` y con un
        máximo de ``100``.
    q : str, optional
        Texto utilizado para buscar coincidencias parciales en el nombre
        o código del producto.
    con_stock : str, optional
        Determina qué productos incluir según su stock.

        ``"1"`` (por defecto)
            Solo productos con ``stock_actual > 0``.

        ``"0"``
            Solo productos con ``stock_actual = 0``.

    Returns
    -------
    flask.Response
        JSON con los productos encontrados y los datos de paginación:

        ``data``
            Lista de productos, incluyendo sus variantes y tipo de prenda.

        ``total``
            Cantidad total de productos que cumplen los filtros.

        ``page``
            Número de página solicitada.

        ``page_size``
            Cantidad de productos por página.

    Notes
    -----
    Los resultados se ordenan alfabéticamente por nombre de producto.

    El campo ``variantes_producto`` contiene las variantes asociadas a
    cada producto.

    El campo ``tipos_prenda`` contiene el nombre y prefijo del tipo de
    prenda asociado al producto.
    """

    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(int(request.args.get("page_size", 20)), 100)
    desde = (page - 1) * page_size
    q = (request.args.get("q") or "").strip()
    con_stock = request.args.get("con_stock", "1") != "0"

    conn = get_db()
    cursor = conn.cursor()

    condiciones = ["p.stock_actual > 0" if con_stock else "p.stock_actual = 0"]
    filtro_params = []

    if q:
        condiciones.append("(p.nombre LIKE ? OR p.codigo LIKE ?)")
        comodin = f"%{q}%"
        filtro_params = [comodin, comodin]

    filtro_sql = " WHERE " + " AND ".join(condiciones)
    cursor.execute(f"SELECT COUNT(*) as total FROM productos p{filtro_sql}", filtro_params)
    total = cursor.fetchone()["total"]
    cursor.execute(f"""
        SELECT p.*, tp.nombre as tipo_nombre, tp.prefijo as tipo_prefijo
        FROM productos p
        LEFT JOIN tipos_prenda tp ON p.tipo_id = tp.id
        {filtro_sql}
        ORDER BY p.nombre
        LIMIT ? OFFSET ?
    """, (*filtro_params, page_size, desde))

    productos_rows = cursor.fetchall()
    data = []
    for p in productos_rows:
        prod_dict = dict(p)
        cursor.execute("SELECT * FROM variantes_producto WHERE producto_id = ?", (prod_dict["id"],))
        variantes = [_serializar_variante(dict(v)) for v in cursor.fetchall()]
        prod_dict["variantes_producto"] = variantes
        prod_dict["tipos_prenda"] = {"nombre": prod_dict.pop("tipo_nombre", None), "prefijo": prod_dict.pop("tipo_prefijo", None)}
        prod_dict = _serializar_producto(prod_dict)
        data.append(prod_dict)

    conn.close()

    return jsonify({
        "data": data,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@productos_bp.get("/buscar")
def buscar_productos():
    """Obtiene el catálogo de productos para el buscador del modal de venta.

    Devuelve todos los productos activos junto con sus variantes. La
    respuesta está pensada para ser utilizada por el buscador de productos
    del proceso de creación de una venta, por lo que no utiliza paginación.

    Cada variante incluye su propio precio de venta y costo, ya que estos
    valores se almacenan a nivel de variante y no de producto.

    Returns
    -------
    flask.Response
        JSON con la lista de productos activos. Cada producto contiene:

        ``id``
            Identificador del producto.

        ``nombre``
            Nombre del producto.

        ``variantes_producto``
            Lista de variantes asociadas. Cada variante incluye ``id``,
            ``codigo``, ``talle``, ``color``, ``stock``, ``precio_venta`` y
            ``precio_costo``.

    Notes
    -----
    Solo se incluyen productos cuyo campo ``activo`` es igual a ``1``.

    Los campos ``costo`` y ``precio`` de la base de datos se exponen en la
    respuesta como ``precio_costo`` y ``precio_venta``, respectivamente.

    Este endpoint devuelve el catálogo completo y no está pensado para
    reemplazar a ``listar_productos()``, que utiliza paginación y filtros.
    """

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos WHERE activo = 1")
    productos = cursor.fetchall()

    data = []
    for p in productos:
        prod_dict = dict(p)
        cursor.execute("""
            SELECT id, codigo, talle, color, stock_actual as stock, costo, precio
            FROM variantes_producto
            WHERE producto_id = ?
        """, (prod_dict["id"],))

        variantes = []
        for v in cursor.fetchall():
            v_dict = dict(v)
            v_dict["precio_venta"] = v_dict.pop("precio", 0)
            v_dict["precio_costo"] = v_dict.pop("costo", 0)
            variantes.append(v_dict)
        prod_dict["variantes_producto"] = variantes
        data.append(prod_dict)

    conn.close()

    return jsonify(data)


@productos_bp.get("/stock-bajo")
def stock_bajo():
    """Obtiene las variantes con stock bajo.

    Se consideran con stock bajo las variantes que tienen más de 0 y menos
    de 5 unidades disponibles. Las variantes con stock igual a 0 se
    consideran sin stock y no se incluyen en este listado.

    Returns
    -------
    flask.Response
        JSON con la lista de variantes cuyo stock se encuentra por debajo
        del umbral establecido. Cada variante incluye los datos del
        producto asociado.

    Notes
    -----
    El rango considerado como stock bajo es:

    ``0 < stock_actual <= umbral`` (umbral configurable, ver routes/configuracion.py)

    El umbral de 5 unidades es exclusivo: una variante con exactamente
    5 unidades no se considera con stock bajo.
    """

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vp.*, p.nombre as producto_nombre 
        FROM variantes_producto vp
        JOIN productos p ON vp.producto_id = p.id
        WHERE vp.stock_actual > 0 AND vp.stock_actual <= ?
    """, (leer_umbral_stock_bajo(cursor),))
    rows = cursor.fetchall()

    conn.close()

    return jsonify([_serializar_variante(dict(r)) for r in rows])


def _generar_codigo_producto(cursor, tipo_id):
    """Genera un código único para un producto a partir de su tipo.

    Utiliza el prefijo asociado al tipo de prenda y genera el siguiente
    número secuencial disponible entre los códigos existentes con ese
    prefijo.

    Si ``tipo_id`` no existe o no corresponde a un tipo de prenda válido,
    se utiliza el prefijo ``"GEN"``.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor de la base de datos utilizado para consultar el prefijo del
        tipo de prenda y los códigos de productos existentes.
    tipo_id : int or None
        Identificador del tipo de prenda que determina el prefijo del
        código.

    Returns
    -------
    str
        Código generado con el formato ``PREFIJO-N``, donde ``N`` es el
        siguiente número secuencial disponible.

    Notes
    -----
    Solo se consideran códigos cuyo formato comienza con el prefijo
    correspondiente seguido de ``"-"`` y cuyo sufijo es numérico.

    La secuencia comienza en ``0`` si todavía no existe ningún código con
    ese prefijo.

    Los números utilizados anteriormente no se reutilizan: se toma el
    máximo existente y se genera el siguiente.

    Examples
    --------
    Si existen los códigos ``REM-0``, ``REM-1`` y ``REM-3``, el siguiente
    código generado será ``REM-4``.
    """

    prefijo = "GEN"

    if tipo_id:
        cursor.execute("SELECT prefijo FROM tipos_prenda WHERE id = ?", (tipo_id,))
        tp = cursor.fetchone()
        if tp:
            prefijo = tp["prefijo"]
    cursor.execute("SELECT codigo FROM productos WHERE codigo LIKE ?", (f"{prefijo}-%",))
    max_num = -1

    for row in cursor.fetchall():
        sufijo = row["codigo"][len(prefijo) + 1:]
        if sufijo.isdigit():
            max_num = max(max_num, int(sufijo))

    return f"{prefijo}-{max_num + 1}"


@productos_bp.post("")
def crear_producto():
    """Crea un producto y, opcionalmente, sus variantes iniciales.

    El producto se crea con stock inicial igual a cero. Si no se proporciona
    un código, se genera automáticamente a partir del tipo de prenda.

    Las variantes iniciales son creadas mediante ``_crear_variante_db()``.
    Cada variante puede definir sus propios valores de precio y costo. Los
    valores de costo, precio y porcentaje del producto se utilizan como
    valores predeterminados para las variantes cuando corresponda.

    Parameters
    ----------
    JSON Parameters
    ----------------
    nombre : str
        Nombre del producto. Es obligatorio.
    tipo_id : int, optional
        Identificador del tipo de prenda utilizado para clasificar el
        producto y, si corresponde, generar su código.
    descripcion : str, optional
        Descripción del producto. Por defecto, ``""``.
    nota : str, optional
        Observación libre sobre el producto. Por defecto, ``""``.
    codigo : str, optional
        Código del producto. Si no se proporciona, se genera
        automáticamente mediante ``_generar_codigo_producto()``.
    variantes : list of dict, optional
        Lista de variantes iniciales que se crearán junto con el producto.
        Por defecto, no se crean variantes.

    Returns
    -------
    flask.Response
        JSON con los datos del producto creado y sus variantes iniciales.
        Devuelve HTTP 201.

        Devuelve HTTP 400 si no se proporciona ``nombre``.

    Notes
    -----
    El stock total del producto se calcula como la suma del stock actual
    de todas sus variantes después de crearlas.

    El producto se crea inicialmente con ``stock_actual = 0`` y estado
    activo.

    La creación de las variantes y sus reglas específicas se delegan en
    ``_crear_variante_db()``.
    """

    body = request.get_json(force=True) or {}
    nombre = body.get("nombre")
    if not nombre:
        return jsonify({"error": "nombre es requerido"}), 400
    tipo_id = body.get("tipo_id")
    descripcion = body.get("descripcion", "")
    nota = body.get("nota") or ""

    conn = get_db()
    cursor = conn.cursor()

    codigo_base = body.get("codigo")
    if not codigo_base:
        codigo_base = _generar_codigo_producto(cursor, tipo_id)

    cursor.execute("""
        INSERT INTO productos (codigo, nombre, tipo_id, stock_actual, descripcion, activo, nota)
        VALUES (?, ?, ?, 0, ?, 1, ?)
    """, (codigo_base, nombre, tipo_id, descripcion, nota))
    producto_id = cursor.lastrowid


    variantes_creadas = []
    for v in body.get("variantes", []):
        variantes_creadas.append(
            _serializar_variante(_crear_variante_db(cursor, producto_id, tipo_id, v, codigo_base))
        )


    conn.commit()
    cursor.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
    producto = _serializar_producto(dict(cursor.fetchone()))
    producto["variantes_producto"] = variantes_creadas
    conn.close()
    return jsonify(producto), 201


def _crear_variante_db(cursor, producto_id, tipo_id, v, producto_codigo):
    """Crea una variante de producto y devuelve sus datos almacenados.

    Construye los datos de una variante a partir de los valores recibidos,
    aplicando valores predeterminados para talle, color, stock, cantidad por
    unidad y porcentaje de ganancia. Si no se proporciona un precio de
    venta, este se calcula automáticamente a partir del costo y el
    porcentaje de ganancia.

    Si no se proporciona un código, genera uno a partir del código del
    producto, un número secuencial y las características de la variante.
    En caso de conflicto con un código existente, agrega un sufijo
    incremental para garantizar su unicidad.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Cursor de la base de datos utilizado para consultar códigos
        existentes e insertar la variante.
    producto_id : int
        Identificador del producto al que pertenece la variante.
    tipo_id : int or None
        Identificador del tipo de prenda. Actualmente no se utiliza
        directamente en esta función, pero forma parte de los datos
        recibidos para la creación de la variante.
    v : dict
        Datos de la variante. Puede incluir ``talle``, ``color``, ``stock``,
        ``cantidad_por_unidad``, ``codigo``, ``precio_costo`` o ``costo``,
        ``porcentaje_ganancia`` y ``precio_venta`` o ``precio``.
    producto_codigo : str
        Código base del producto utilizado para generar automáticamente
        el código de la variante.

    Returns
    -------
    dict
        Datos completos de la variante recién creada, tal como quedan
        almacenados en la base de datos.

    Notes
    -----
    Los valores predeterminados son:

    - ``talle``: ``"Único"``
    - ``color``: ``"Único"``
    - ``stock``: ``0``
    - ``cantidad_por_unidad``: ``1``
    - ``porcentaje_ganancia``: ``30``

    El costo puede recibirse mediante ``precio_costo`` o ``costo``.
    ``precio_costo`` tiene prioridad.

    El precio de venta puede recibirse mediante ``precio_venta`` o
    ``precio``. Si no se proporciona, se calcula como:

    ``precio_venta = costo * (1 + porcentaje_ganancia / 100)``

    Si no se proporciona un código, se genera con el formato:

    ``producto_codigo-secuencial-talle-color-xcantidad_por_unidad``

    Los espacios se eliminan del código generado. Si el código resultante
    ya existe, se agrega un sufijo numérico incremental hasta encontrar un
    código disponible.

    ``stock_minimo`` se crea inicialmente con valor ``0``.
    """
    
    talle = v.get("talle") or "Único"
    color = v.get("color") or "Único"
    stock = v.get("stock", 0)
    cantidad_por_unidad = v.get("cantidad_por_unidad", 1)
    codigo = v.get("codigo")

    # Precio/costo/% propios de la variante
    costo = v.get("precio_costo", v.get("costo", 0))
    porcentaje = v.get("porcentaje_ganancia", 30)
    precio = v.get("precio_venta", v.get("precio"))
    if not precio:
        precio = costo * (1 + (porcentaje / 100))

    if not codigo:
        secuencial = _siguiente_secuencial_variante(cursor, producto_id, producto_codigo)
        base = f"{producto_codigo}-{secuencial}-{talle}-{color}-x{cantidad_por_unidad}".replace(" ", "")
        codigo = base
        intento = 0
        while True:
            cursor.execute("SELECT 1 FROM variantes_producto WHERE codigo = ?", (codigo,))
            if not cursor.fetchone():
                break
            intento += 1
            codigo = f"{base}-{intento}"

    cursor.execute("""
        INSERT INTO variantes_producto (
            producto_id, codigo, talle, color, cantidad_por_unidad,
            costo, precio, porcentaje_ganancia,
            stock_actual, stock_minimo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        producto_id, codigo, talle, color, cantidad_por_unidad,
        costo, precio, porcentaje, stock
    ))

    var_id = cursor.lastrowid
    cursor.execute("SELECT * FROM variantes_producto WHERE id = ?", (var_id,))

    return dict(cursor.fetchone())


@productos_bp.post("/<int:producto_id>/variantes")
def crear_variante(producto_id):
    """Crea una nueva variante para un producto.

    Verifica que el producto exista, crea la variante mediante
    ``_crear_variante_db()`` y actualiza el stock total almacenado en el
    producto a partir de sus variantes.

    Parameters
    ----------
    producto_id : int
        Identificador del producto al que pertenecerá la nueva variante.

    JSON Parameters
    ----------------
    Los campos aceptados dependen de ``_crear_variante_db()`` y corresponden
    a los datos necesarios para crear una variante del producto.

    Returns
    -------
    flask.Response
        JSON con los datos de la variante creada. Devuelve HTTP 201.

        Devuelve HTTP 404 si el producto no existe.

    Notes
    -----
    Después de crear la variante, ``productos.stock_actual`` se recalcula
    como la suma del stock actual de todas las variantes del producto.

    La generación y validación de los datos propios de la variante se
    delega en ``_crear_variante_db()``.
    """

    body = request.get_json(force=True) or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT tipo_id FROM productos WHERE id = ?", (producto_id,))
    prod = cursor.fetchone()
    if not prod:
        conn.close()
        return jsonify({"error": "Producto no encontrado"}), 404

    cursor.execute("SELECT codigo FROM productos WHERE id = ?", (producto_id,))
    producto_codigo = cursor.fetchone()["codigo"]

    variante = _serializar_variante(_crear_variante_db(cursor, producto_id, prod["tipo_id"], body, producto_codigo))


    conn.commit()
    conn.close()

    return jsonify(variante), 201


@productos_bp.patch("/variantes/<int:variante_id>/stock")
def ajustar_stock(variante_id):
    """Ajusta manualmente el stock de una variante.

    Modifica el stock actual de la variante sumando la cantidad indicada y
    registra el ajuste en ``movimientos_stock``. Después actualiza el stock
    total del producto como la suma del stock de todas sus variantes.

    Un valor positivo de ``cantidad`` incrementa el stock, mientras que un
    valor negativo lo disminuye.

    Parameters
    ----------
    variante_id : int
        Identificador de la variante cuyo stock se desea ajustar.

    JSON Parameters
    ----------------
    cantidad : int or float
        Cantidad que se suma al stock actual. Puede ser positiva o negativa.
    motivo : str, optional
        Motivo del ajuste que se almacena en el movimiento de stock.
        Por defecto, ``"Ajuste manual"``.

    Returns
    -------
    flask.Response
        JSON con el resultado de la operación y el nuevo stock de la
        variante:

        ``{"ok": True, "stock": nuevo_stock}``

        Devuelve HTTP 400 si ``cantidad`` no es numérica y HTTP 404 si la
        variante no existe.

    Notes
    -----
    El ajuste queda registrado con tipo ``"ajuste"`` en
    ``movimientos_stock``.

    El stock total almacenado en ``productos.stock_actual`` se recalcula
    después de modificar la variante.
    """

    body = request.get_json(force=True) or {}
    cantidad = body.get("cantidad")
    motivo = body.get("motivo", "Ajuste manual")

    if not isinstance(cantidad, (int, float)):
        return jsonify({"error": "cantidad debe ser numérica"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_actual, producto_id FROM variantes_producto WHERE id = ?", (variante_id,))
    var = cursor.fetchone()

    if not var:
        conn.close()
        return jsonify({"error": "variante no encontrada"}), 404

    nuevo_stock = var["stock_actual"] + cantidad
    cursor.execute("UPDATE variantes_producto SET stock_actual = ? WHERE id = ?", (nuevo_stock, variante_id))
    cursor.execute("""
        INSERT INTO movimientos_stock (variante_id, tipo, cantidad, motivo)
        VALUES (?, 'ajuste', ?, ?)
    """, (variante_id, cantidad, motivo))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "stock": nuevo_stock})


@productos_bp.patch("/<int:producto_id>")
def actualizar_producto(producto_id):
    """Actualiza los datos generales de un producto.

    Solo se modifican los datos propios del producto. Las variantes
    asociadas no se modifican mediante este endpoint.

    Parameters
    ----------
    producto_id : int
        Identificador del producto que se desea actualizar.

    JSON Parameters
    ----------------
    nombre : str, optional
        Nombre del producto. Si no se proporciona, se conserva el valor
        actual.
    descripcion : str, optional
        Descripción del producto. Si no se proporciona, se conserva el
        valor actual.
    tipo_id : int, optional
        Identificador del tipo de producto. Si no se proporciona, se
        conserva el valor actual.
    activo : bool, optional
        Indica si el producto está activo. Si no se proporciona, se
        conserva el valor actual.
    nota : str, optional
        Observación libre sobre el producto. Si no se proporciona, se
        conserva el valor actual.

    Returns
    -------
    flask.Response
        JSON con los datos actualizados del producto.

        Devuelve HTTP 404 si el producto no existe.

    Notes
    -----
    Los campos no incluidos en la solicitud mantienen sus valores
    actuales.
    """

    body = request.get_json(force=True) or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
    actual = cursor.fetchone()

    if not actual:
        conn.close()
        return jsonify({"error": "Producto no encontrado"}), 404
    
    nombre = body.get("nombre", actual["nombre"])
    descripcion = body.get("descripcion", actual["descripcion"])
    tipo_id = body.get("tipo_id", actual["tipo_id"])
    activo = body.get("activo", actual["activo"])
    nota = body.get("nota", actual["nota"]) or ""
    cursor.execute("""
        UPDATE productos 
        SET nombre = ?, descripcion = ?, tipo_id = ?, activo = ?, nota = ?
        WHERE id = ?
    """, (nombre, descripcion, tipo_id, activo, nota, producto_id))
    conn.commit()
    cursor.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
    updated = _serializar_producto(dict(cursor.fetchone()))
    conn.close()

    return jsonify(updated)


@productos_bp.delete("/<int:producto_id>")
def borrar_producto(producto_id):
    """Elimina un producto y todas sus variantes asociadas.

    La eliminación se realiza de forma permanente. Primero se eliminan las
    variantes pertenecientes al producto y luego el registro del producto.

    Parameters
    ----------
    producto_id : int
        Identificador del producto que se desea eliminar.

    Returns
    -------
    flask.Response
        Respuesta JSON con ``{"ok": True}``.

    Notes
    -----
    Si el producto no existe, las operaciones de eliminación no afectan
    ningún registro y el endpoint devuelve igualmente una respuesta exitosa.
    """

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM variantes_producto WHERE producto_id = ?", (producto_id,))
    cursor.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@productos_bp.patch("/variantes/<int:variante_id>")
def actualizar_variante(variante_id):
    """Actualiza los datos y precios de una variante de producto.

    Permite modificar las características de la variante y sus valores
    económicos. Si no se proporciona un precio de venta explícito y se
    modifica el costo o el porcentaje de ganancia, el precio de venta se
    recalcula automáticamente.

    Parameters
    ----------
    variante_id : int
        Identificador de la variante que se desea actualizar.

    JSON Parameters
    ----------------
    talle : str, optional
        Talle de la variante. Si no se proporciona, se conserva el valor
        actual o se utiliza ``"Único"``.
    color : str, optional
        Color de la variante. Si no se proporciona, se conserva el valor
        actual o se utiliza ``"Único"``.
    codigo : str, optional
        Código identificador de la variante. Si no se proporciona, se
        conserva el código actual.
    cantidad_por_unidad : int, optional
        Cantidad de unidades representadas por una unidad de la variante.
        Los valores menores que 1 se ajustan a 1.
    precio_costo : float, optional
        Costo de la variante.
    porcentaje_ganancia : float, optional
        Porcentaje de ganancia aplicado sobre el costo.
    precio_venta : float, optional
        Precio de venta de la variante. Si se proporciona explícitamente,
        tiene prioridad sobre el cálculo automático.

    Returns
    -------
    flask.Response
        JSON con los datos actualizados de la variante.

        Devuelve HTTP 404 si la variante no existe.

    Notes
    -----
    Si ``precio_venta`` no se proporciona y se modifica ``precio_costo``
    o ``porcentaje_ganancia``, el precio se calcula mediante:

    ``precio_venta = precio_costo * (1 + porcentaje_ganancia / 100)``

    Si no se modifica ninguno de esos valores y no se proporciona un
    precio de venta, se conserva el precio actual.
    """

    body = request.get_json(force=True) or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM variantes_producto WHERE id = ?", (variante_id,))
    actual = cursor.fetchone()
    if not actual:
        conn.close()
        return jsonify({"error": "Variante no encontrada"}), 404

    talle = body.get("talle") or actual["talle"] or "Único"
    color = body.get("color") or actual["color"] or "Único"
    codigo = body.get("codigo") or actual["codigo"]

    cantidad_por_unidad = body.get("cantidad_por_unidad", actual["cantidad_por_unidad"])
    try:
        cantidad_por_unidad = int(cantidad_por_unidad)
    except (TypeError, ValueError):
        cantidad_por_unidad = 1
    if cantidad_por_unidad < 1:
        cantidad_por_unidad = 1

    costo = body.get("precio_costo", actual["costo"])
    porcentaje = body.get("porcentaje_ganancia", actual["porcentaje_ganancia"])
    precio = body.get("precio_venta")

    if precio is None:
        if "precio_costo" in body or "porcentaje_ganancia" in body:
            # Recalcular si cambió costo o % y no mandaron precio explícito
            precio = costo * (1 + (porcentaje / 100))
        else:
            precio = actual["precio"]

    cursor.execute("""
        UPDATE variantes_producto
        SET
            talle = ?,
            color = ?,
            codigo = ?,
            cantidad_por_unidad = ?,
            costo = ?,
            precio = ?,
            porcentaje_ganancia = ?
        WHERE id = ?
    """, (
        talle, color, codigo, cantidad_por_unidad,
        costo, precio, porcentaje,
        variante_id
    ))
    conn.commit()
    cursor.execute("SELECT * FROM variantes_producto WHERE id = ?", (variante_id,))
    updated = _serializar_variante(dict(cursor.fetchone()))
    conn.close()
    return jsonify(updated)


@productos_bp.delete("/variantes/<int:variante_id>")
def borrar_variante(variante_id):
    """Elimina una variante de producto y actualiza el stock total del producto.

    La variante se elimina de forma permanente. Si la variante existe,
    se obtiene el producto al que pertenece, se elimina la variante y se
    recalcula el stock total del producto como la suma del stock de sus
    variantes restantes.

    Parameters
    ----------
    variante_id : int
        Identificador de la variante que se desea eliminar.

    Returns
    -------
    flask.Response
        Respuesta JSON con ``{"ok": True}``.

    Notes
    -----
    Si la variante no existe, no se realiza ninguna modificación y se
    devuelve igualmente una respuesta exitosa.

    El stock total almacenado en ``productos.stock_actual`` se actualiza
    después de eliminar la variante.
    """

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT producto_id FROM variantes_producto WHERE id = ?", (variante_id,))
    var = cursor.fetchone()
    if var:
        cursor.execute("DELETE FROM variantes_producto WHERE id = ?", (variante_id,))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})
