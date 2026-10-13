from conftest import assert_stock_consistente


def test_crear_producto_suma_el_stock_de_las_variantes(crear_producto):
    producto = crear_producto([
        {"talle": "S", "stock": 3, "costo": 1000, "precio": 2000},
        {"talle": "M", "stock": 5, "costo": 1000, "precio": 2000},
    ])

    assert producto["stock_actual"] == 8
    assert len(producto["variantes_producto"]) == 2
    assert_stock_consistente()


def test_precio_se_calcula_desde_costo_y_porcentaje_si_no_viene(crear_producto):
    producto = crear_producto([{"stock": 1, "costo": 1000, "porcentaje_ganancia": 50}])

    variante = producto["variantes_producto"][0]
    # La API devuelve costo/precio renombrados como precio_costo/precio_venta.
    assert variante["precio_venta"] == 1500


def test_codigos_de_variantes_son_unicos(crear_producto):
    producto = crear_producto([
        {"talle": "S", "color": "Negro", "stock": 1, "costo": 1, "precio": 2},
        {"talle": "S", "color": "Negro", "stock": 1, "costo": 1, "precio": 2},
    ])

    codigos = [v["codigo"] for v in producto["variantes_producto"]]
    assert len(set(codigos)) == 2


def test_crear_producto_sin_nombre_da_400(client):
    res = client.post("/api/productos", json={"variantes": []})
    assert res.status_code == 400


# ---------- Stock del producto = suma de variantes ----------

def _stock_producto(client, producto_id):
    import app.database as database
    conn = database.get_db()
    fila = conn.execute("SELECT stock_actual FROM productos WHERE id = ?", (producto_id,)).fetchone()
    conn.close()
    return fila["stock_actual"]


def test_agregar_variante_suma_al_stock_del_producto(client, crear_producto):
    producto = crear_producto([{"stock": 3, "costo": 1, "precio": 2}])

    res = client.post(f"/api/productos/{producto['id']}/variantes",
                      json={"talle": "XL", "stock": 4, "costo": 1, "precio": 2})

    assert res.status_code == 201
    assert _stock_producto(client, producto["id"]) == 7
    assert_stock_consistente()


def test_ajustar_stock_de_variante_actualiza_el_producto(client, crear_producto):
    producto = crear_producto([{"stock": 3, "costo": 1, "precio": 2}])
    variante_id = producto["variantes_producto"][0]["id"]

    client.patch(f"/api/productos/variantes/{variante_id}/stock", json={"cantidad": 5})
    assert _stock_producto(client, producto["id"]) == 8

    client.patch(f"/api/productos/variantes/{variante_id}/stock", json={"cantidad": -2})
    assert _stock_producto(client, producto["id"]) == 6
    assert_stock_consistente()


def test_borrar_variante_resta_su_stock_del_producto(client, crear_producto):
    producto = crear_producto([
        {"talle": "S", "stock": 3, "costo": 1, "precio": 2},
        {"talle": "M", "stock": 4, "costo": 1, "precio": 2},
    ])
    variante_id = producto["variantes_producto"][0]["id"]

    res = client.delete(f"/api/productos/variantes/{variante_id}")

    assert res.status_code == 200
    assert _stock_producto(client, producto["id"]) == 4
    assert_stock_consistente()


def test_editar_datos_de_variante_no_cambia_el_stock(client, crear_producto):
    producto = crear_producto([{"stock": 3, "costo": 1, "precio": 2}])
    variante_id = producto["variantes_producto"][0]["id"]

    client.patch(f"/api/productos/variantes/{variante_id}", json={"color": "Rojo", "precio_venta": 5})

    assert _stock_producto(client, producto["id"]) == 3
    assert_stock_consistente()


def test_trigger_actualiza_el_producto_aunque_no_pase_por_la_api(client, crear_producto):
    import app.database as database
    producto = crear_producto([{"stock": 3, "costo": 1, "precio": 2}])
    variante_id = producto["variantes_producto"][0]["id"]

    conn = database.get_db()
    conn.execute("UPDATE variantes_producto SET stock_actual = 10 WHERE id = ?", (variante_id,))
    conn.commit()
    conn.close()

    assert _stock_producto(client, producto["id"]) == 10


def test_init_db_corrige_bases_viejas_sin_triggers(client, crear_producto):
    # Simula una base de antes de los triggers, con el total desincronizado.
    import app.database as database
    producto = crear_producto([{"stock": 3, "costo": 1, "precio": 2}])
    conn = database.get_db()
    for trigger in ("trg_stock_producto_insert", "trg_stock_producto_update", "trg_stock_producto_delete"):
        conn.execute(f"DROP TRIGGER {trigger}")
    conn.execute("UPDATE productos SET stock_actual = 99 WHERE id = ?", (producto["id"],))
    conn.commit()
    conn.close()

    database.init_db()

    assert _stock_producto(client, producto["id"]) == 3
    conn = database.get_db()
    triggers = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
    conn.close()
    assert {"trg_stock_producto_insert", "trg_stock_producto_update", "trg_stock_producto_delete"} <= triggers
