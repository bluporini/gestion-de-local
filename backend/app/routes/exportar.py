import csv
import io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, request, jsonify

from app.database import get_db
from app.routes.ventas import OFFSET_ARGENTINA_HORAS, _rango_utc_para_dia_local

exportar_bp = Blueprint("exportar", __name__, url_prefix="/api/exportar")

NOMBRES_METODO_PAGO = {
    "efectivo": "Efectivo",
    "tarjeta_debito": "Tarjeta débito",
    "tarjeta_credito": "Tarjeta crédito",
    "transferencia": "Transferencia",
    "otro": "Otro",
}


def _numero(valor):
    """Formatea un número con coma decimal (Excel en español la espera así)."""
    return f"{(valor or 0):.2f}".replace(".", ",")


def _fecha_local(fecha_utc_str):
    """'YYYY-MM-DD HH:MM:SS' en UTC -> 'DD/MM/YYYY HH:MM' en hora de Argentina."""
    if not fecha_utc_str:
        return ""
    fecha = datetime.strptime(str(fecha_utc_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
    return (fecha - timedelta(hours=OFFSET_ARGENTINA_HORAS)).strftime("%d/%m/%Y %H:%M")


def _respuesta_csv(nombre_archivo, encabezados, filas):
    """Arma un CSV que Excel (configuración regional en español) abre directo:
    separador ';', coma decimal y BOM UTF-8 para que muestre bien los acentos."""
    salida = io.StringIO()
    writer = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    writer.writerow(encabezados)
    writer.writerows(filas)
    return Response(
        "﻿" + salida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@exportar_bp.get("/ventas.csv")
def exportar_ventas():
    """Exporta las ventas de un rango de fechas (hora de Argentina) a CSV.

    Query Parameters
    ----------------
    desde, hasta : str
        Fechas ``YYYY-MM-DD`` (inclusive). Son obligatorias.

    Notes
    -----
    ``Total`` y ``Ganancia`` son los valores actuales de la venta: incluyen
    los cambios que haya tenido. Las devoluciones se exportan con su estado
    para que se puedan filtrar en Excel.
    """
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    try:
        desde_utc, _ = _rango_utc_para_dia_local(desde)
        _, hasta_utc = _rango_utc_para_dia_local(hasta)
    except (TypeError, ValueError):
        return jsonify({"error": "desde y hasta son requeridos (formato YYYY-MM-DD)"}), 400
    if desde_utc > hasta_utc:
        return jsonify({"error": "La fecha 'desde' es posterior a 'hasta'"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM ventas
        WHERE fecha >= ? AND fecha <= ?
        ORDER BY fecha ASC
    """, (desde_utc, hasta_utc))
    ventas = cursor.fetchall()

    filas = []
    for v in ventas:
        cursor.execute("""
            SELECT vi.cantidad, p.nombre, vp.talle, vp.color
            FROM venta_items vi
            JOIN variantes_producto vp ON vi.variante_id = vp.id
            JOIN productos p ON vp.producto_id = p.id
            WHERE vi.venta_id = ?
        """, (v["id"],))
        productos = " | ".join(
            f"{i['cantidad']}x {i['nombre']} ({i['talle'] or '-'}/{i['color'] or '-'})"
            for i in cursor.fetchall()
        )
        filas.append([
            v["codigo"] or "",
            _fecha_local(v["fecha"]),
            v["cliente"] or "",
            productos,
            NOMBRES_METODO_PAGO.get(v["metodo_pago"], v["metodo_pago"] or ""),
            v["tipo_tarjeta"] or "",
            "Devolución" if v["estado"] == "devolucion" else "Realizada",
            "Sí" if v["tiene_cambio"] else "No",
            _numero(v["total"]),
            _numero(v["ganancia"]),
        ])
    conn.close()

    return _respuesta_csv(
        f"ventas_{desde}_a_{hasta}.csv",
        ["Código", "Fecha", "Cliente", "Productos", "Medio de pago", "Tarjeta",
         "Estado", "Tuvo cambio", "Total", "Ganancia"],
        filas,
    )


@exportar_bp.get("/stock.csv")
def exportar_stock():
    """Exporta el stock actual, una fila por variante, a CSV."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.nombre, p.codigo AS producto_codigo, t.nombre AS tipo,
               vp.codigo, vp.talle, vp.color, vp.cantidad_por_unidad,
               vp.stock_actual, vp.costo, vp.precio
        FROM variantes_producto vp
        JOIN productos p ON vp.producto_id = p.id
        LEFT JOIN tipos_prenda t ON p.tipo_id = t.id
        ORDER BY p.nombre, vp.codigo
    """)
    filas = [
        [
            r["nombre"], r["producto_codigo"], r["tipo"] or "",
            r["codigo"], r["talle"] or "", r["color"] or "", r["cantidad_por_unidad"] or 1,
            r["stock_actual"] or 0,
            _numero(r["costo"]), _numero(r["precio"]),
            _numero((r["stock_actual"] or 0) * (r["costo"] or 0)),
        ]
        for r in cursor.fetchall()
    ]
    conn.close()

    hoy = (datetime.now(timezone.utc) - timedelta(hours=OFFSET_ARGENTINA_HORAS)).strftime("%Y-%m-%d")
    return _respuesta_csv(
        f"stock_{hoy}.csv",
        ["Producto", "Código producto", "Tipo", "Código variante", "Talle", "Color",
         "Pack", "Stock", "Costo", "Precio", "Valor del stock (a costo)"],
        filas,
    )
