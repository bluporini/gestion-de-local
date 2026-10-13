from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request
from app.database import get_db

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")

# Argentina es UTC-3 (sin horario de verano)
OFFSET_ARGENTINA_HORAS = 3

def _inicio_semana(hoy):
    """Obtiene la fecha del lunes de la semana de una fecha dada.

    Parameters
    ----------
    hoy : datetime.date
        Fecha a partir de la cual se calcula el inicio de la semana.

    Returns
    -------
    datetime.date
        Fecha correspondiente al lunes de esa semana.
    """
    
    return hoy - timedelta(days=hoy.weekday())


@dashboard_bp.get("/resumen")
def resumen():
    """Obtiene el resumen de ventas, ingresos, ganancias y stock del dashboard.

    Calcula indicadores correspondientes al día actual, la semana actual
    y el mes actual, utilizando la fecha local de Argentina.

    Las ventas se consideran únicamente si su estado es ``realizada``.
    Los cambios se contabilizan según la fecha en que se realizó el cambio,
    independientemente de la fecha de la venta original.

    El resumen incluye:

    - cantidad de ventas realizadas hoy, esta semana y este mes;
    - ingresos de hoy, esta semana y este mes;
    - ganancias de esta semana y este mes;
    - productos con stock bajo.

    Returns
    -------
    flask.Response
        Respuesta JSON con los indicadores del dashboard.

        Las claves de la respuesta son:

        ``ventas_hoy``
            Cantidad de ventas realizadas durante el día actual.

        ``ventas_semana``
            Cantidad de ventas realizadas desde el inicio de la semana.

        ``ventas_mes``
            Cantidad de ventas realizadas desde el inicio del mes.

        ``ingresos_hoy``
            Ingresos correspondientes al día actual, incluyendo el efecto
            económico de los cambios realizados durante ese día.

        ``ingresos_semana``
            Ingresos correspondientes a la semana actual.

        ``ingresos_mes``
            Ingresos correspondientes al mes actual.

        ``ganancia_semana``
            Ganancia acumulada durante la semana actual.

        ``ganancia_mes``
            Ganancia acumulada durante el mes actual.

        ``productos_stock_bajo``
            Lista de variantes cuyo stock actual es mayor que 0 y menor
            que 5 unidades.

    Notes
    -----
    Las fechas almacenadas en la base de datos se encuentran en UTC y se
    convierten a la fecha local de Argentina para determinar si una venta
    o cambio pertenece al día, semana o mes correspondiente.

    Los productos con stock igual a 0 no se consideran de ``stock bajo``;
    se consideran productos ``sin stock``.

    Examples
    --------
    GET /dashboard/resumen
    """
    
    ahora_local = datetime.now(timezone.utc) - timedelta(hours=OFFSET_ARGENTINA_HORAS)
    hoy = ahora_local.date()
    inicio_semana = _inicio_semana(hoy)
    inicio_mes = hoy.replace(day=1)

    # Se usa el mínimo entre inicio de semana e inicio de mes, porque cerca del
    # cambio de mes la semana calendario puede empezar en el mes anterior.
    # Restamos un día extra de margen porque el rango se compara contra 'fecha'
    # (guardada en UTC), y una fecha local "desde" puede corresponder a una
    # fecha UTC anterior.
    desde = (min(inicio_semana, inicio_mes) - timedelta(days=1)).isoformat()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ventas WHERE fecha >= ?", (desde,))
    ventas = [dict(row) for row in cursor.fetchall()]

    # Si la tabla no tiene 'estado', asumimos que todas están realizadas, o filtramos 
    # si el campo existe
    realizadas = [v for v in ventas if v.get("estado", "realizada") == "realizada"]

    def fecha_de(v):
        """Obtiene la fecha local de Argentina correspondiente a un registro.

        Convierte la fecha almacenada en UTC a la fecha local de Argentina.
        Admite fechas almacenadas con formato ISO 8601 y fechas con formato
        ``YYYY-MM-DD HH:MM:SS``.

        Parameters
        ----------
        v : dict
            Registro de venta o cambio que contiene el campo ``fecha``.

        Returns
        -------
        datetime.date | None
            Fecha local correspondiente al registro, o ``None`` si la fecha
            no puede interpretarse.
        """

        fecha_str = v.get("fecha", "")
        
        try:
            if "T" in fecha_str:
                dt_utc = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).replace(tzinfo=None)
            else:
                dt_utc = datetime.strptime(fecha_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
            dt_local = dt_utc - timedelta(hours=OFFSET_ARGENTINA_HORAS)
            return dt_local.date()
        
        except Exception:
            return None

    def en_rango(v, desde_fecha):
        """Indica si un registro pertenece al rango desde una fecha dada.

        Parameters
        ----------
        v : dict
            Registro de venta o cambio con campo ``fecha``.
        desde_fecha : datetime.date
            Fecha inicial del período, inclusive.

        Returns
        -------
        bool
            ``True`` si el registro tiene una fecha válida igual o posterior
            a ``desde_fecha``; en caso contrario, ``False``.
        """

        dt = fecha_de(v)
        return dt is not None and dt >= desde_fecha

    # Filtramos también por el mes actual, ya que la query trae desde antes si hace falta
    ventas_mes = [v for v in realizadas if en_rango(v, inicio_mes)]
    ventas_semana = [v for v in realizadas if en_rango(v, inicio_semana)]
    ventas_hoy = [v for v in realizadas if en_rango(v, hoy)]

    # Cambios: se cuentan por SU PROPIA fecha, no por la fecha de la
    # venta a la que pertenecen. Así un cambio de hoy sobre una venta
    # vieja se refleja en "hoy", no en el día de la venta original.
    cursor.execute("SELECT * FROM cambios WHERE fecha >= ?", (desde,))
    cambios = [dict(row) for row in cursor.fetchall()]

    cambios_mes = [c for c in cambios if en_rango(c, inicio_mes)]
    cambios_semana = [c for c in cambios if en_rango(c, inicio_semana)]
    cambios_hoy = [c for c in cambios if en_rango(c, hoy)]

    ingresos_mes = sum(v.get("total_base", v.get("total", 0)) for v in ventas_mes) \
        + sum(c.get("monto_diferencia", 0) for c in cambios_mes)
    ganancia_mes = sum(v.get("ganancia_base", v.get("ganancia", 0)) for v in ventas_mes) \
        + sum(c.get("ganancia", 0) for c in cambios_mes)
    ingresos_semana = sum(v.get("total_base", v.get("total", 0)) for v in ventas_semana) \
        + sum(c.get("monto_diferencia", 0) for c in cambios_semana)
    ganancia_semana = sum(v.get("ganancia_base", v.get("ganancia", 0)) for v in ventas_semana) \
        + sum(c.get("ganancia", 0) for c in cambios_semana)
    ingresos_hoy = sum(v.get("total_base", v.get("total", 0)) for v in ventas_hoy) \
        + sum(c.get("monto_diferencia", 0) for c in cambios_hoy)

    # Obtener productos con stock bajo: más de 0 pero menos de 2 unidades
    # (si está en 0 no es "stock bajo", es "sin stock")
    cursor.execute("""
        SELECT vp.*, p.nombre as producto_nombre 
        FROM variantes_producto vp
        JOIN productos p ON vp.producto_id = p.id
        WHERE vp.stock_actual > 0 AND vp.stock_actual < 2
    """)
    stock_bajo_rows = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "ventas_hoy": len(ventas_hoy),
        "ventas_semana": len(ventas_semana),
        "ventas_mes": len(ventas_mes),
        "ingresos_hoy": round(ingresos_hoy, 2),
        "ingresos_semana": round(ingresos_semana, 2),
        "ingresos_mes": round(ingresos_mes, 2),
        "ganancia_semana": round(ganancia_semana, 2),
        "ganancia_mes": round(ganancia_mes, 2),
        "productos_stock_bajo": stock_bajo_rows,
    })
