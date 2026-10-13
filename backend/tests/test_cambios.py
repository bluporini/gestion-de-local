import pytest

from conftest import assert_stock_consistente, stock_variante, venta


@pytest.fixture
def escenario(crear_producto, vender):
    """Venta de 2 unidades de A. B queda disponible para llevarse en un cambio.

    A: stock 5 -> 3 tras la venta, costo 1000, precio 2500.
    B: stock 4, costo 1500, precio 3000.
    """
    producto = crear_producto([
        {"talle": "A", "stock": 5, "costo": 1000, "precio": 2500},
        {"talle": "B", "stock": 4, "costo": 1500, "precio": 3000},
    ])
    a, b = (v["id"] for v in producto["variantes_producto"])
    v = vender([{"variante_id": a, "cantidad": 2}])
    return {"a": a, "b": b, "venta": v}


def _cambio(client, venta_id, devueltos=(), nuevos=(), monto=0, metodo="efectivo"):
    return client.post("/api/cambios", json={
        "venta_id": venta_id,
        "items_devueltos": [{"variante_id": v, "cantidad": c} for v, c in devueltos],
        "items_nuevos": [{"variante_id": v, "cantidad": c} for v, c in nuevos],
        "monto_diferencia": monto,
        "metodo_pago": metodo if monto else None,
    })


def test_cambio_mueve_stock_y_ajusta_la_venta(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]

    # Devuelve 1 A (2500) y se lleva 1 B (3000): paga 500 de diferencia.
    res = _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500)

    assert res.status_code == 201
    assert stock_variante(a) == 4
    assert stock_variante(b) == 3

    actualizada = venta(v["id"])
    assert actualizada["total"] == v["total"] + 500
    # Ganancia: +1500 (B) - 1500 (A devuelto) = 0 de diferencia.
    assert actualizada["ganancia"] == v["ganancia"]
    assert actualizada["tiene_cambio"] == 1
    # total_base guarda el valor original de la venta.
    assert actualizada["total_base"] == v["total"]
    assert_stock_consistente()


def test_no_se_puede_devolver_mas_de_lo_comprado(client, escenario):
    a, v = escenario["a"], escenario["venta"]

    assert _cambio(client, v["id"], devueltos=[(a, 3)]).status_code == 400
    assert stock_variante(a) == 3


def test_lo_devuelto_en_cambios_anteriores_se_descuenta_del_disponible(client, escenario):
    a, v = escenario["a"], escenario["venta"]

    assert _cambio(client, v["id"], devueltos=[(a, 2)]).status_code == 201
    assert _cambio(client, v["id"], devueltos=[(a, 1)]).status_code == 400
    assert stock_variante(a) == 5


def test_misma_variante_en_dos_items_se_puede_devolver_completa(client, crear_producto, vender):
    # La venta tiene A dos veces (1 + 1). El disponible para devolver
    # tiene que ser 2, no solo la cantidad del último ítem.
    producto = crear_producto([{"stock": 5, "costo": 1000, "precio": 2500}])
    a = producto["variantes_producto"][0]["id"]
    v = vender([{"variante_id": a, "cantidad": 1}, {"variante_id": a, "cantidad": 1}])

    res = _cambio(client, v["id"], devueltos=[(a, 2)])

    assert res.status_code == 201
    assert stock_variante(a) == 5


def test_no_se_puede_devolver_una_variante_que_no_estaba_en_la_venta(client, escenario):
    b, v = escenario["b"], escenario["venta"]
    assert _cambio(client, v["id"], devueltos=[(b, 1)]).status_code == 400


def test_diferencia_de_dinero_sin_metodo_de_pago_da_400(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    res = client.post("/api/cambios", json={
        "venta_id": v["id"],
        "items_devueltos": [{"variante_id": a, "cantidad": 1}],
        "items_nuevos": [{"variante_id": b, "cantidad": 1}],
        "monto_diferencia": 500,
    })
    assert res.status_code == 400


def test_borrar_cambio_deja_todo_como_antes(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    cambio = _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500).get_json()

    res = client.delete(f"/api/cambios/{cambio['id']}")

    assert res.status_code == 200
    assert stock_variante(a) == 3
    assert stock_variante(b) == 4
    actualizada = venta(v["id"])
    assert actualizada["total"] == v["total"]
    assert actualizada["ganancia"] == v["ganancia"]
    assert actualizada["tiene_cambio"] == 0
    assert_stock_consistente()


def test_editar_cambio_revierte_el_anterior_y_aplica_el_nuevo(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    cambio = _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500).get_json()

    # Ahora devuelve las 2 A y se lleva 2 B: diferencia 2 * (3000 - 2500) = 1000.
    res = client.patch(f"/api/cambios/{cambio['id']}", json={
        "items_devueltos": [{"variante_id": a, "cantidad": 2}],
        "items_nuevos": [{"variante_id": b, "cantidad": 2}],
        "monto_diferencia": 1000,
        "metodo_pago": "efectivo",
    })

    assert res.status_code == 200
    assert stock_variante(a) == 5
    assert stock_variante(b) == 2
    actualizada = venta(v["id"])
    assert actualizada["total"] == v["total"] + 1000
    assert actualizada["ganancia"] == v["ganancia"]  # 2*1500 - 2*1500
    assert_stock_consistente()


def test_editar_cambio_invalido_no_deja_el_cambio_a_medias(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    cambio = _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500).get_json()

    res = client.patch(f"/api/cambios/{cambio['id']}", json={
        "items_devueltos": [{"variante_id": a, "cantidad": 99}],
    })

    assert res.status_code == 400
    # Sigue vigente el cambio original.
    assert stock_variante(a) == 4
    assert stock_variante(b) == 3
    assert venta(v["id"])["total"] == v["total"] + 500


def test_devolucion_total_de_venta_con_cambio_deja_el_stock_como_antes_de_vender(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500)

    res = client.post(f"/api/ventas/{v['id']}/devolucion")

    assert res.status_code == 200
    assert stock_variante(a) == 5
    assert stock_variante(b) == 4
    actualizada = venta(v["id"])
    assert actualizada["total"] == v["total"]
    assert actualizada["tiene_cambio"] == 0
    assert_stock_consistente()


def test_borrar_venta_con_cambio_deja_el_stock_como_antes_de_vender(client, escenario):
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    _cambio(client, v["id"], devueltos=[(a, 1)], nuevos=[(b, 1)], monto=500)

    client.delete(f"/api/ventas/{v['id']}")

    assert stock_variante(a) == 5
    assert stock_variante(b) == 4
    assert_stock_consistente()


def test_misma_variante_repetida_en_items_nuevos_no_deja_stock_negativo(client, escenario):
    # Stock de B = 4: dos ítems de 3 piden 6.
    a, b, v = escenario["a"], escenario["b"], escenario["venta"]
    res = client.post("/api/cambios", json={
        "venta_id": v["id"],
        "items_devueltos": [{"variante_id": a, "cantidad": 1}],
        "items_nuevos": [{"variante_id": b, "cantidad": 3}, {"variante_id": b, "cantidad": 3}],
        "monto_diferencia": 0,
    })

    assert res.status_code == 400
    assert stock_variante(b) == 4


def test_misma_variante_repetida_en_items_devueltos_no_devuelve_de_mas(client, escenario):
    # Se compraron 2 A: dos ítems devueltos de 2 piden 4.
    a, v = escenario["a"], escenario["venta"]

    res = _cambio(client, v["id"], devueltos=[(a, 2), (a, 2)])

    assert res.status_code == 400
    assert stock_variante(a) == 3
