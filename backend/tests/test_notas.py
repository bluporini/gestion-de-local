import sqlite3

import pytest

import app.database as database


def _crear(client, texto, etiquetas=None):
    body = {"texto": texto}
    if etiquetas is not None:
        body["etiquetas"] = etiquetas
    res = client.post("/api/notas", json=body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def _textos(client, query=""):
    return [n["texto"] for n in client.get(f"/api/notas{query}").get_json()]


def test_crear_nota_sin_etiquetas(client):
    nota = _crear(client, "  Llamar a Juan  ")

    assert nota["texto"] == "Llamar a Juan"
    assert nota["hecha"] == 0 and nota["fecha"]
    assert nota["etiquetas"] == []


def test_etiquetas_se_limpian_y_no_se_repiten(client):
    nota = _crear(client, "Pedir corpiños", [" Proveedores ", "#urgente", "proveedores", "", "  "])
    assert nota["etiquetas"] == ["Proveedores", "urgente"]

    # También acepta texto separado por comas. "Urgente" reusa la etiqueta
    # "urgente" que ya existía (con su nombre original), no crea otra.
    nota = _crear(client, "Otra", "ideas, #Urgente")
    assert nota["etiquetas"] == ["ideas", "urgente"]

    # "urgente" y "Urgente" son la misma etiqueta.
    etiquetas = {e["nombre"].lower(): e["total"] for e in client.get("/api/notas/etiquetas").get_json()}
    assert etiquetas == {"ideas": 1, "proveedores": 1, "urgente": 2}


@pytest.mark.parametrize("body", [{}, {"texto": ""}, {"texto": "   "}, {"texto": 5},
                                  {"texto": "x", "etiquetas": [1, 2]}, {"texto": "x", "etiquetas": 3}])
def test_nota_invalida_da_400(client, body):
    assert client.post("/api/notas", json=body).status_code == 400
    assert client.get("/api/notas").get_json() == []


def test_tachar_editar_y_orden(client):
    n1 = _crear(client, "Llamar a Juan", ["proveedores"])
    n2 = _crear(client, "Pedir talle 90", ["proveedores"])

    client.patch(f"/api/notas/{n1['id']}", json={"hecha": True})
    res = client.patch(f"/api/notas/{n2['id']}", json={"texto": "Pedir talle 95", "etiquetas": ["pedidos"]})

    assert res.get_json()["etiquetas"] == ["pedidos"]
    # Pendientes primero.
    assert _textos(client) == ["Pedir talle 95", "Llamar a Juan"]


def test_filtros_por_etiqueta_texto_y_ocultar_hechas(client):
    a = _crear(client, "Llamar a Juan", ["proveedores", "urgente"])
    _crear(client, "Vidriera de verano", ["ideas"])
    _crear(client, "Pagar la luz")
    client.patch(f"/api/notas/{a['id']}", json={"hecha": True})

    assert _textos(client, "?etiqueta=proveedores") == ["Llamar a Juan"]
    assert _textos(client, "?etiqueta=PROVEEDORES") == ["Llamar a Juan"]
    assert _textos(client, "?q=vidriera") == ["Vidriera de verano"]
    assert sorted(_textos(client, "?ocultar_hechas=1")) == ["Pagar la luz", "Vidriera de verano"]
    assert _textos(client, "?etiqueta=proveedores&ocultar_hechas=1") == []

    etiquetas = {e["nombre"]: (e["total"], e["pendientes"]) for e in client.get("/api/notas/etiquetas").get_json()}
    assert etiquetas == {"ideas": (1, 1), "proveedores": (1, 0), "urgente": (1, 0)}


def test_etiquetas_sin_uso_desaparecen(client):
    a = _crear(client, "Una", ["vieja"])
    b = _crear(client, "Otra", ["temporal"])

    client.patch(f"/api/notas/{a['id']}", json={"etiquetas": []})
    client.delete(f"/api/notas/{b['id']}")

    assert client.get("/api/notas/etiquetas").get_json() == []


@pytest.mark.parametrize("body", [{}, {"texto": ""}, {"hecha": "si"}, {"etiquetas": 7}])
def test_editar_nota_invalida_da_400(client, body):
    nota = _crear(client, "x")
    assert client.patch(f"/api/notas/{nota['id']}", json=body).status_code == 400


def test_nota_inexistente_da_404(client):
    assert client.patch("/api/notas/999", json={"hecha": True}).status_code == 404
    assert client.delete("/api/notas/999").status_code == 404


def test_migra_notas_con_bloques_a_etiquetas(client, tmp_path):
    # Base con el formato viejo (bloques), como la que pudo quedar en desarrollo.
    conn = sqlite3.connect(database.DB_PATH)
    conn.executescript("""
        DROP TABLE nota_etiquetas;
        DROP TABLE etiquetas;
        DROP TABLE notas;
        CREATE TABLE notas_bloques (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, creado TIMESTAMP);
        CREATE TABLE notas (id INTEGER PRIMARY KEY, bloque_id INTEGER NOT NULL, texto TEXT NOT NULL,
                            hecha INTEGER NOT NULL DEFAULT 0, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO notas_bloques (id, nombre) VALUES (1, 'Proveedores'), (2, 'Ideas');
        INSERT INTO notas (bloque_id, texto, hecha) VALUES (1, 'Llamar a Juan', 1), (2, 'Vidriera', 0);
    """)
    conn.commit()
    conn.close()

    database.init_db()

    notas = {n["texto"]: (n["etiquetas"], n["hecha"]) for n in client.get("/api/notas").get_json()}
    assert notas == {"Llamar a Juan": (["Proveedores"], 1), "Vidriera": (["Ideas"], 0)}
    conn = sqlite3.connect(database.DB_PATH)
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(notas)")}
    conn.close()
    assert "notas_bloques" not in tablas and "bloque_id" not in columnas
    # Y se pueden seguir creando notas.
    assert _crear(client, "Nueva", ["ideas"])["etiquetas"] == ["Ideas"]
