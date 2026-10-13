import re

import pytest

from conftest import assert_stock_consistente, stock_variante, venta


@pytest.fixture
def variantes(crear_producto):
    """Dos variantes: A (stock 5, costo 1000, precio 2500) y B (stock 2, costo 500, precio 1000)."""
    producto = crear_producto([
        {"talle": "A", "stock": 5, "costo": 1000, "precio": 2500},
        {"talle": "B", "stock": 2, "costo": 500, "precio": 1000},
    ])
    a, b = producto["variantes_producto"]
    return a["id"], b["id"]


# ---------- Crear venta ----------

def test_venta_descuenta_stock_y_calcula_totales(variantes, vender):
    a, b = variantes

    v = vender([{"variante_id": a, "cantidad": 2}, {"variante_id": b, "cantidad": 1}],
               monto_pagado=10000)

    assert stock_variante(a) == 3
    assert stock_variante(b) == 1
    assert v["total"] == 2 * 2500 + 1000
    assert v["ganancia"] == 2 * (2500 - 1000) + (1000 - 500)
    assert v["vuelto"] == 10000 - 6000
    assert v["total_base"] == v["total"]
    assert v["estado"] == "realizada"
    assert_stock_consistente()


def test_codigo_de_venta_tiene_formato_ddmmyy_nnn_V(variantes, vender):
    a, _ = variantes
    v1 = vender([{"variante_id": a, "cantidad": 1}])
    v2 = vender([{"variante_id": a, "cantidad": 1}])

    assert re.fullmatch(r"\d{6}\d{3}V", v1["codigo"])
    assert int(v2["codigo"][6:9]) == int(v1["codigo"][6:9]) + 1


def test_venta_con_tarjeta_no_guarda_monto_ni_vuelto(variantes, vender):
    a, _ = variantes
    v = vender([{"variante_id": a, "cantidad": 1}],
               metodo_pago="tarjeta_debito", tipo_tarjeta="Visa")

    assert v["monto_pagado"] is None
    assert v["vuelto"] is None
    assert v["tipo_tarjeta"] == "Visa"


@pytest.mark.parametrize("body, motivo", [
    ({"metodo_pago": "efectivo", "items": []}, "sin items"),
    ({"metodo_pago": "efectivo", "items": [{"variante_id": 1, "cantidad": 1}]}, "efectivo sin monto"),
    ({"metodo_pago": "tarjeta_credito", "items": [{"variante_id": 1, "cantidad": 1}]}, "tarjeta sin tipo"),
    ({"metodo_pago": "efectivo", "monto_pagado": 1, "items": [{"variante_id": 1, "cantidad": 1}]}, "paga menos que el total"),
    ({"metodo_pago": "efectivo", "monto_pagado": 99999, "items": [{"variante_id": 1, "cantidad": 0}]}, "cantidad cero"),
    ({"metodo_pago": "efectivo", "monto_pagado": 99999, "items": [{"variante_id": 999, "cantidad": 1}]}, "variante inexistente"),
])
def test_venta_invalida_da_400_y_no_toca_stock(client, variantes, body, motivo):
    a, _ = variantes
    res = client.post("/api/ventas", json=body)

    assert res.status_code == 400, motivo
    assert stock_variante(a) == 5


def test_venta_sin_stock_suficiente_da_400(client, variantes):
    _, b = variantes
    res = client.post("/api/ventas", json={
        "metodo_pago": "efectivo", "monto_pagado": 99999,
        "items": [{"variante_id": b, "cantidad": 3}],
    })

    assert res.status_code == 400
    assert stock_variante(b) == 2


def test_misma_variante_en_dos_items_no_puede_dejar_stock_negativo(client, variantes):
    # Stock de B = 2. Cada ítem por separado pasa la validación (2 <= 2),
    # pero juntos piden 4.
    _, b = variantes
    res = client.post("/api/ventas", json={
        "metodo_pago": "efectivo", "monto_pagado": 99999,
        "items": [{"variante_id": b, "cantidad": 2}, {"variante_id": b, "cantidad": 2}],
    })

    assert res.status_code == 400
    assert stock_variante(b) == 2


# ---------- Borrar venta / devolución ----------

def test_borrar_venta_repone_stock(client, variantes, vender):
    a, b = variantes
    v = vender([{"variante_id": a, "cantidad": 2}, {"variante_id": b, "cantidad": 1}])

    res = client.delete(f"/api/ventas/{v['id']}")

    assert res.status_code == 200
    assert stock_variante(a) == 5
    assert stock_variante(b) == 2
    assert venta(v["id"]) is None
    assert_stock_consistente()


def test_devolucion_repone_stock_y_cambia_estado(client, variantes, vender):
    a, _ = variantes
    v = vender([{"variante_id": a, "cantidad": 2}])

    res = client.post(f"/api/ventas/{v['id']}/devolucion")

    assert res.status_code == 200
    assert res.get_json()["estado"] == "devolucion"
    assert stock_variante(a) == 5
    assert_stock_consistente()


def test_devolucion_dos_veces_da_400_y_no_repone_de_nuevo(client, variantes, vender):
    a, _ = variantes
    v = vender([{"variante_id": a, "cantidad": 2}])
    client.post(f"/api/ventas/{v['id']}/devolucion")

    res = client.post(f"/api/ventas/{v['id']}/devolucion")

    assert res.status_code == 400
    assert stock_variante(a) == 5


def test_borrar_venta_ya_devuelta_no_repone_stock_otra_vez(client, variantes, vender):
    a, _ = variantes
    v = vender([{"variante_id": a, "cantidad": 2}])
    client.post(f"/api/ventas/{v['id']}/devolucion")

    client.delete(f"/api/ventas/{v['id']}")

    assert stock_variante(a) == 5


def test_editar_venta_solo_cambia_cliente_y_metodo(client, variantes, vender):
    a, _ = variantes
    v = vender([{"variante_id": a, "cantidad": 1}])

    res = client.patch(f"/api/ventas/{v['id']}",
                       json={"cliente": "Ana", "metodo_pago": "transferencia", "total": 1})

    actualizada = res.get_json()
    assert actualizada["cliente"] == "Ana"
    assert actualizada["metodo_pago"] == "transferencia"
    assert actualizada["total"] == v["total"]


def test_falla_a_mitad_de_una_venta_no_deja_nada_a_medias_ni_la_base_bloqueada(client, variantes):
    import sqlite3
    import app.database as database

    a, _ = variantes
    # Hace fallar el INSERT de los ítems, después de que ya se insertó la venta.
    conn = database.get_db()
    conn.execute("""
        CREATE TRIGGER falla_items BEFORE INSERT ON venta_items
        BEGIN SELECT RAISE(ABORT, 'falla simulada'); END
    """)
    conn.commit()
    conn.close()

    res = client.post("/api/ventas", json={
        "metodo_pago": "efectivo", "monto_pagado": 99999,
        "items": [{"variante_id": a, "cantidad": 1}],
    })

    assert res.status_code == 500
    # La base no quedó bloqueada: otra conexión puede escribir enseguida.
    otra = sqlite3.connect(database.DB_PATH, timeout=0.5)
    otra.execute("DROP TRIGGER falla_items")
    otra.commit()
    assert otra.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 0
    otra.close()
    assert stock_variante(a) == 5
