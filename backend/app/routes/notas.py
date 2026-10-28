from flask import Blueprint, request, jsonify

from app.database import get_db

notas_bp = Blueprint("notas", __name__, url_prefix="/api/notas")

MAX_TEXTO = 2000
MAX_ETIQUETA = 30
MAX_ETIQUETAS_POR_NOTA = 10


def _texto(body):
    """Texto de la nota sin espacios sobrantes, o None si falta o es inválido."""
    valor = body.get("texto")
    if not isinstance(valor, str) or not valor.strip():
        return None
    return valor.strip()[:MAX_TEXTO]


def _normalizar_etiquetas(valor):
    """Lista de etiquetas limpia y sin repetidos (sin distinguir mayúsculas).

    Acepta una lista o un texto separado por comas. Saca el '#' inicial y
    los espacios sobrantes.

    Returns
    -------
    list[str] | None
        Las etiquetas, o None si el valor no es válido.
    """
    if isinstance(valor, str):
        valor = valor.split(",")
    if not isinstance(valor, list) or not all(isinstance(e, str) for e in valor):
        return None

    etiquetas, vistas = [], set()
    for e in valor:
        nombre = e.strip().lstrip("#").strip()[:MAX_ETIQUETA]
        if nombre and nombre.lower() not in vistas:
            vistas.add(nombre.lower())
            etiquetas.append(nombre)
    return etiquetas[:MAX_ETIQUETAS_POR_NOTA]


def _guardar_etiquetas(conn, nota_id, etiquetas):
    """Reemplaza las etiquetas de la nota y borra las que quedaron sin usar."""
    conn.execute("DELETE FROM nota_etiquetas WHERE nota_id = ?", (nota_id,))
    for nombre in etiquetas:
        conn.execute("INSERT OR IGNORE INTO etiquetas (nombre) VALUES (?)", (nombre,))
        conn.execute("""
            INSERT OR IGNORE INTO nota_etiquetas (nota_id, etiqueta_id)
            SELECT ?, id FROM etiquetas WHERE nombre = ?
        """, (nota_id, nombre))
    _borrar_etiquetas_sin_uso(conn)


def _borrar_etiquetas_sin_uso(conn):
    conn.execute("DELETE FROM etiquetas WHERE id NOT IN (SELECT etiqueta_id FROM nota_etiquetas)")


def _nota_con_etiquetas(conn, nota_id):
    fila = conn.execute("SELECT * FROM notas WHERE id = ?", (nota_id,)).fetchone()
    if not fila:
        return None
    nota = dict(fila)
    nota["etiquetas"] = [r["nombre"] for r in conn.execute("""
        SELECT e.nombre FROM etiquetas e
        JOIN nota_etiquetas ne ON ne.etiqueta_id = e.id
        WHERE ne.nota_id = ?
        ORDER BY e.nombre COLLATE NOCASE
    """, (nota_id,))]
    return nota


@notas_bp.get("")
def listar_notas():
    """Notas: primero las pendientes y, dentro de cada grupo, las más nuevas.

    Query Parameters
    ----------------
    etiqueta : str, optional
        Solo las notas con esa etiqueta.
    q : str, optional
        Busca en el texto de la nota.
    ocultar_hechas : "1", optional
        No devuelve las notas tachadas.
    """
    etiqueta = (request.args.get("etiqueta") or "").strip()
    q = (request.args.get("q") or "").strip()

    condiciones, parametros = [], []
    if etiqueta:
        condiciones.append("""n.id IN (SELECT ne.nota_id FROM nota_etiquetas ne
                                       JOIN etiquetas e ON e.id = ne.etiqueta_id
                                       WHERE e.nombre = ?)""")
        parametros.append(etiqueta)
    if q:
        condiciones.append("n.texto LIKE ?")
        parametros.append(f"%{q}%")
    if request.args.get("ocultar_hechas") == "1":
        condiciones.append("n.hecha = 0")

    consulta = "SELECT n.id FROM notas n"
    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)
    consulta += " ORDER BY n.hecha ASC, n.fecha DESC, n.id DESC"

    conn = get_db()
    ids = [r["id"] for r in conn.execute(consulta, parametros)]
    notas = [_nota_con_etiquetas(conn, nota_id) for nota_id in ids]
    conn.close()
    return jsonify(notas)


@notas_bp.get("/etiquetas")
def listar_etiquetas():
    """Etiquetas en uso, con la cantidad de notas totales y pendientes."""
    conn = get_db()
    filas = conn.execute("""
        SELECT e.nombre,
               COUNT(n.id) AS total,
               COALESCE(SUM(CASE WHEN n.hecha = 0 THEN 1 ELSE 0 END), 0) AS pendientes
        FROM etiquetas e
        JOIN nota_etiquetas ne ON ne.etiqueta_id = e.id
        JOIN notas n ON n.id = ne.nota_id
        GROUP BY e.id
        ORDER BY e.nombre COLLATE NOCASE
    """).fetchall()
    conn.close()
    return jsonify([dict(f) for f in filas])


@notas_bp.post("")
def crear_nota():
    body = request.get_json(force=True) or {}
    texto = _texto(body)
    if not texto:
        return jsonify({"error": "La nota no puede estar vacía"}), 400
    etiquetas = _normalizar_etiquetas(body.get("etiquetas", []))
    if etiquetas is None:
        return jsonify({"error": "etiquetas tiene que ser una lista de textos"}), 400

    conn = get_db()
    nota_id = conn.execute("INSERT INTO notas (texto) VALUES (?)", (texto,)).lastrowid
    _guardar_etiquetas(conn, nota_id, etiquetas)
    conn.commit()
    nota = _nota_con_etiquetas(conn, nota_id)
    conn.close()
    return jsonify(nota), 201


@notas_bp.patch("/<int:nota_id>")
def actualizar_nota(nota_id):
    """Edita el texto y/o las etiquetas, o marca la nota como hecha (tachada)."""
    body = request.get_json(force=True) or {}
    cambios = {}

    if "texto" in body:
        texto = _texto(body)
        if not texto:
            return jsonify({"error": "La nota no puede estar vacía"}), 400
        cambios["texto"] = texto
    if "hecha" in body:
        if not isinstance(body["hecha"], bool):
            return jsonify({"error": "hecha tiene que ser true o false"}), 400
        cambios["hecha"] = 1 if body["hecha"] else 0
    etiquetas = None
    if "etiquetas" in body:
        etiquetas = _normalizar_etiquetas(body["etiquetas"])
        if etiquetas is None:
            return jsonify({"error": "etiquetas tiene que ser una lista de textos"}), 400
    if not cambios and etiquetas is None:
        return jsonify({"error": "Nada para actualizar"}), 400

    conn = get_db()
    if not conn.execute("SELECT 1 FROM notas WHERE id = ?", (nota_id,)).fetchone():
        conn.close()
        return jsonify({"error": "Nota no encontrada"}), 404

    if cambios:
        asignaciones = ", ".join(f"{campo} = ?" for campo in cambios)
        conn.execute(f"UPDATE notas SET {asignaciones} WHERE id = ?", (*cambios.values(), nota_id))
    if etiquetas is not None:
        _guardar_etiquetas(conn, nota_id, etiquetas)
    conn.commit()
    nota = _nota_con_etiquetas(conn, nota_id)
    conn.close()
    return jsonify(nota)


@notas_bp.delete("/<int:nota_id>")
def borrar_nota(nota_id):
    conn = get_db()
    cursor = conn.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    _borrar_etiquetas_sin_uso(conn)
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({"error": "Nota no encontrada"}), 404
    return jsonify({"ok": True})
