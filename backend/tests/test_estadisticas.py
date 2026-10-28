from datetime import datetime, timedelta, timezone

import pytest

import app.database as database


def _set_fecha(tabla, fila_id, fecha_utc):
    conn = database.get_db()
    conn.execute(f"UPDATE {tabla} SET fecha = ? WHERE id = ?", (fecha_utc, fila_id))
    conn.commit()
    conn.close()


def _meses(client):
    res = client.get("/api/estadisticas/mensual")
    assert res.status_code == 200
    return res.get_json()["meses"]


def _por_mes(client):
    return {m["mes"]: m for m in _meses(client)}


@pytest.fixture
def variante(crear_producto):
    producto = crear_producto([{"stock": 100, "costo": 1000, "precio": 2500}])
    return producto["variantes_producto"][0]["id"]


def test_devuelve_12_meses_terminando_en_el_actual(client):
    meses = _meses(client)
    ahora_local = datetime.now(timezone.utc) - timedelta(hours=3)

    assert len(meses) == 12
    assert meses[-1]["mes"] == ahora_local.strftime("%Y-%m")
    assert [m["mes"] for m in meses] == sorted(m["mes"] for m in meses)
    assert all(m["ingresos"] == 0 and m["ventas"] == 0 for m in meses)


def test_cuenta_ventas_realizadas_y_excluye_devoluciones(client, variante, vender):
    vender([{"variante_id": variante, "cantidad": 2}])               # 5000, ganancia 3000
    devuelta = vender([{"variante_id": variante, "cantidad": 1}])
    client.post(f"/api/ventas/{devuelta['id']}/devolucion")

    actual = _meses(client)[-1]

    assert actual["ventas"] == 1
    assert actual["ingresos"] == 5000
    assert actual["ganancia"] == 3000


def test_ubica_cada_venta_en_su_mes_local_y_descarta_las_de_hace_mas_de_un_anio(client, variante, vender):
    meses = [m["mes"] for m in _meses(client)]
    anio, mes = map(int, meses[-3].split("-"))
    v_mes = vender([{"variante_id": variante, "cantidad": 1}])
    v_borde = vender([{"variante_id": variante, "cantidad": 1}])
    v_vieja = vender([{"variante_id": variante, "cantidad": 1}])

    _set_fecha("ventas", v_mes["id"], f"{anio}-{mes:02d}-15 15:00:00")
    # 01:30 UTC del día 1 = 22:30 del día anterior en Argentina -> mes anterior.
    _set_fecha("ventas", v_borde["id"], f"{anio}-{mes:02d}-01 01:30:00")
    _set_fecha("ventas", v_vieja["id"], f"{anio - 2}-{mes:02d}-15 15:00:00")

    datos = _por_mes(client)

    assert datos[meses[-3]]["ventas"] == 1
    assert datos[meses[-4]]["ventas"] == 1
    assert sum(m["ventas"] for m in datos.values()) == 2


def test_los_cambios_suman_en_su_propio_mes(client, crear_producto, vender):
    producto = crear_producto([
        {"talle": "A", "stock": 10, "costo": 1000, "precio": 2500},
        {"talle": "B", "stock": 10, "costo": 1500, "precio": 3000},
    ])
    a, b = (v["id"] for v in producto["variantes_producto"])
    venta = vender([{"variante_id": a, "cantidad": 1}])
    meses = [m["mes"] for m in _meses(client)]
    anio, mes = map(int, meses[-2].split("-"))
    _set_fecha("ventas", venta["id"], f"{anio}-{mes:02d}-10 15:00:00")

    client.post("/api/cambios", json={
        "venta_id": venta["id"],
        "items_devueltos": [{"variante_id": a, "cantidad": 1}],
        "items_nuevos": [{"variante_id": b, "cantidad": 1}],
        "monto_diferencia": 500, "metodo_pago": "efectivo",
    })

    datos = _por_mes(client)
    # La venta queda en su mes con sus valores originales...
    assert datos[meses[-2]]["ingresos"] == 2500
    assert datos[meses[-2]]["ganancia"] == 1500
    # ...y el cambio (hecho hoy) suma en el mes actual.
    assert datos[meses[-1]]["ingresos"] == 500
    assert datos[meses[-1]]["ganancia"] == 0  # +1500 (B) - 1500 (A devuelto)
    assert datos[meses[-1]]["ventas"] == 0


def test_separa_la_cantidad_de_ventas_por_canal(client, variante, vender):
    vender([{"variante_id": variante, "cantidad": 1}])
    vender([{"variante_id": variante, "cantidad": 1}], canal="local")
    vender([{"variante_id": variante, "cantidad": 1}], canal="virtual")
    devuelta = vender([{"variante_id": variante, "cantidad": 1}], canal="virtual")
    client.post(f"/api/ventas/{devuelta['id']}/devolucion")

    actual = _meses(client)[-1]

    assert actual["ventas"] == 3
    assert actual["ventas_local"] == 2
    assert actual["ventas_virtual"] == 1
