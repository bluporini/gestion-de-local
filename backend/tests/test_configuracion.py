import pytest


def _nombres_stock_bajo(client):
    resumen = client.get("/api/dashboard/resumen").get_json()
    return sorted(v["talle"] for v in resumen["productos_stock_bajo"])


@pytest.fixture
def variantes_con_poco_stock(crear_producto):
    # Talles con stock 0, 1, 2, 3 y 10.
    crear_producto([
        {"talle": f"S{n}", "stock": n, "costo": 1, "precio": 2}
        for n in (0, 1, 2, 3, 10)
    ])


def test_umbral_por_defecto_es_1_como_antes(client, variantes_con_poco_stock):
    assert client.get("/api/configuracion").get_json() == {"stock_bajo_umbral": 1}
    assert _nombres_stock_bajo(client) == ["S1"]


def test_cambiar_umbral_cambia_el_stock_bajo_del_dashboard(client, variantes_con_poco_stock):
    res = client.put("/api/configuracion", json={"stock_bajo_umbral": 3})

    assert res.status_code == 200
    assert client.get("/api/configuracion").get_json() == {"stock_bajo_umbral": 3}
    # El stock en 0 nunca es "stock bajo" (es "sin stock").
    assert _nombres_stock_bajo(client) == ["S1", "S2", "S3"]


def test_endpoint_stock_bajo_usa_el_mismo_umbral(client, variantes_con_poco_stock):
    client.put("/api/configuracion", json={"stock_bajo_umbral": 2})

    talles = sorted(v["talle"] for v in client.get("/api/productos/stock-bajo").get_json())
    assert talles == ["S1", "S2"]


@pytest.mark.parametrize("valor", [0, -1, 1001, "3", 2.5, True, None])
def test_umbral_invalido_da_400_y_no_cambia_nada(client, valor):
    res = client.put("/api/configuracion", json={"stock_bajo_umbral": valor})

    assert res.status_code == 400
    assert client.get("/api/configuracion").get_json() == {"stock_bajo_umbral": 1}
