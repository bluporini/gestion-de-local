import pytest

ENVIO = {
    "fecha": "2026-10-15",
    "empresa": "Correo Argentino",
    "numero_seguimiento": " CP123456789AR ",
    "destinatario": "Ana García",
    "telefono": "11 5555-5555",
    "direccion": "Av. Siempre Viva 742",
    "localidad": "Rosario",
    "provincia": "Santa Fe",
    "codigo_postal": "2000",
    "costo": 4500,
    "paga": "cliente",
}


@pytest.fixture
def venta(crear_producto, vender):
    producto = crear_producto([{"stock": 5, "costo": 1, "precio": 2}])
    return vender([{"variante_id": producto["variantes_producto"][0]["id"], "cantidad": 1}],
                  cliente="Ana García")


def test_crear_envio_completo(client):
    res = client.post("/api/envios", json=ENVIO)

    assert res.status_code == 201
    envio = res.get_json()
    assert envio["numero_seguimiento"] == "CP123456789AR"
    assert envio["estado"] == "por_preparar"
    assert envio["costo"] == 4500
    assert envio["venta_id"] is None


def test_crear_envio_minimo(client):
    res = client.post("/api/envios", json={"fecha": "2026-10-15", "empresa": "Andreani", "destinatario": "Juan"})
    assert res.status_code == 201
    assert res.get_json()["costo"] == 0 and res.get_json()["paga"] == "cliente"


@pytest.mark.parametrize("cambio", [
    {"empresa": ""}, {"destinatario": "  "}, {"fecha": "15/10/2026"}, {"fecha": None},
    {"costo": -1}, {"costo": "mucho"}, {"paga": "nadie"}, {"estado": "perdido"},
    {"venta_id": "1"}, {"venta_id": 999},
])
def test_envio_invalido_da_400(client, cambio):
    assert client.post("/api/envios", json={**ENVIO, **cambio}).status_code == 400
    assert client.get("/api/envios").get_json() == []


def test_vincular_a_una_venta(client, venta):
    envio = client.post("/api/envios", json={**ENVIO, "venta_id": venta["id"]}).get_json()

    assert envio["venta_id"] == venta["id"]
    assert envio["venta_codigo"] == venta["codigo"]
    assert envio["venta_cliente"] == "Ana García"


def test_borrar_la_venta_deja_el_envio_sin_vincular(client, venta):
    envio = client.post("/api/envios", json={**ENVIO, "venta_id": venta["id"]}).get_json()

    client.delete(f"/api/ventas/{venta['id']}")

    assert client.get(f"/api/envios/{envio['id']}").get_json()["venta_id"] is None


def test_avanzar_estado_y_editar(client):
    envio = client.post("/api/envios", json=ENVIO).get_json()

    res = client.patch(f"/api/envios/{envio['id']}", json={"estado": "despachado"})
    assert res.status_code == 200 and res.get_json()["estado"] == "despachado"

    res = client.patch(f"/api/envios/{envio['id']}", json={"localidad": "Funes", "costo": 5000})
    actualizado = res.get_json()
    assert (actualizado["localidad"], actualizado["costo"], actualizado["destinatario"]) == ("Funes", 5000, "Ana García")

    assert client.patch(f"/api/envios/{envio['id']}", json={}).status_code == 400
    assert client.patch(f"/api/envios/{envio['id']}", json={"destinatario": ""}).status_code == 400
    assert client.patch("/api/envios/999", json={"estado": "entregado"}).status_code == 404


def test_filtrar_por_estado_y_buscar(client, venta):
    a = client.post("/api/envios", json={**ENVIO, "destinatario": "Ana", "localidad": "Rosario"}).get_json()
    client.post("/api/envios", json={**ENVIO, "destinatario": "Beto", "localidad": "Salta",
                                     "numero_seguimiento": "XYZ", "venta_id": venta["id"]})
    client.patch(f"/api/envios/{a['id']}", json={"estado": "entregado"})

    assert [e["destinatario"] for e in client.get("/api/envios?estado=entregado").get_json()] == ["Ana"]
    assert [e["destinatario"] for e in client.get("/api/envios?q=salta").get_json()] == ["Beto"]
    assert [e["destinatario"] for e in client.get("/api/envios?q=xyz").get_json()] == ["Beto"]
    assert [e["destinatario"] for e in client.get(f"/api/envios?q={venta['codigo']}").get_json()] == ["Beto"]
    assert len(client.get("/api/envios").get_json()) == 2


def test_borrar_envio(client):
    envio = client.post("/api/envios", json=ENVIO).get_json()
    assert client.delete(f"/api/envios/{envio['id']}").status_code == 200
    assert client.delete(f"/api/envios/{envio['id']}").status_code == 404


def test_un_problema_se_puede_marcar_resuelto(client):
    envio = client.post("/api/envios", json=ENVIO).get_json()
    client.patch(f"/api/envios/{envio['id']}", json={"estado": "problema"})

    res = client.patch(f"/api/envios/{envio['id']}", json={"estado": "resuelto"})

    assert res.status_code == 200 and res.get_json()["estado"] == "resuelto"
    assert [e["id"] for e in client.get("/api/envios?estado=resuelto").get_json()] == [envio["id"]]
    assert client.get("/api/envios?estado=problema").get_json() == []
