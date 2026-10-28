from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify

from app.database import get_db
from app.routes.ventas import OFFSET_ARGENTINA_HORAS

estadisticas_bp = Blueprint("estadisticas", __name__, url_prefix="/api/estadisticas")

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
CANTIDAD_MESES = 12


def _mes_local(fecha_utc_str):
    """'YYYY-MM-DD HH:MM:SS' (UTC) -> (año, mes) en hora de Argentina, o None."""
    try:
        texto = str(fecha_utc_str)
        if "T" in texto:
            dt = datetime.fromisoformat(texto.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            dt = datetime.strptime(texto.split(".")[0], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None
    local = dt - timedelta(hours=OFFSET_ARGENTINA_HORAS)
    return local.year, local.month


def _ultimos_meses(hoy, cantidad):
    """Lista de (año, mes) de los últimos `cantidad` meses, del más viejo al actual."""
    meses = []
    anio, mes = hoy.year, hoy.month
    for _ in range(cantidad):
        meses.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(meses))


@estadisticas_bp.get("/mensual")
def estadisticas_mensuales():
    """Ingresos, ganancia y cantidad de ventas de los últimos 12 meses.

    Usa las mismas reglas que el dashboard:

    - Solo ventas ``realizada`` (las devoluciones no cuentan), con sus
      valores originales (``total_base``/``ganancia_base``).
    - Los cambios suman su ``monto_diferencia`` y su ``ganancia`` en el mes
      en que se hicieron (no en el de la venta original).

    La cantidad de ventas se separa además por canal (``ventas_local`` y
    ``ventas_virtual``); los cambios no la afectan.

    Returns
    -------
    flask.Response
        ``{"meses": [{"mes": "2026-10", "etiqueta": "oct 26", "ingresos",
        "ganancia", "ventas", "ventas_local", "ventas_virtual"}, ...]}`` del mes más viejo al actual, incluido
        el mes en curso.
    """
    hoy = (datetime.now(timezone.utc) - timedelta(hours=OFFSET_ARGENTINA_HORAS)).date()
    meses = _ultimos_meses(hoy, CANTIDAD_MESES)
    datos = {
        m: {"ingresos": 0.0, "ganancia": 0.0, "ventas": 0, "ventas_local": 0, "ventas_virtual": 0}
        for m in meses
    }

    # Un día de margen: la fecha se compara contra 'fecha' guardada en UTC.
    desde = (date(*meses[0], 1) - timedelta(days=1)).isoformat()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fecha, total, ganancia, total_base, ganancia_base, canal FROM ventas
        WHERE fecha >= ? AND estado = 'realizada'
    """, (desde,))
    for v in cursor.fetchall():
        mes = _mes_local(v["fecha"])
        if mes in datos:
            datos[mes]["ingresos"] += v["total_base"] if v["total_base"] is not None else (v["total"] or 0)
            datos[mes]["ganancia"] += v["ganancia_base"] if v["ganancia_base"] is not None else (v["ganancia"] or 0)
            datos[mes]["ventas"] += 1
            datos[mes]["ventas_virtual" if v["canal"] == "virtual" else "ventas_local"] += 1

    cursor.execute("SELECT fecha, monto_diferencia, ganancia FROM cambios WHERE fecha >= ?", (desde,))
    for c in cursor.fetchall():
        mes = _mes_local(c["fecha"])
        if mes in datos:
            datos[mes]["ingresos"] += c["monto_diferencia"] or 0
            datos[mes]["ganancia"] += c["ganancia"] or 0

    conn.close()

    return jsonify({"meses": [
        {
            "mes": f"{anio}-{mes:02d}",
            "etiqueta": f"{MESES[mes - 1]} {str(anio)[2:]}",
            "ingresos": round(datos[(anio, mes)]["ingresos"], 2),
            "ganancia": round(datos[(anio, mes)]["ganancia"], 2),
            "ventas": datos[(anio, mes)]["ventas"],
            "ventas_local": datos[(anio, mes)]["ventas_local"],
            "ventas_virtual": datos[(anio, mes)]["ventas_virtual"],
        }
        for anio, mes in meses
    ]})
