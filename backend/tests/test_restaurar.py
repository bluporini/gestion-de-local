import gzip
import io
import os
import sqlite3

import pytest

import app.database as database


def _snapshot_gz(tmp_path):
    """Respaldo de la base actual en el mismo formato que sube la app (.db.gz)."""
    copia = tmp_path / "copia.db"
    src = sqlite3.connect(database.DB_PATH)
    dst = sqlite3.connect(copia)
    src.backup(dst)
    dst.close()
    src.close()
    return gzip.compress(copia.read_bytes()), copia


def _restaurar(client, contenido, nombre="backup.db.gz"):
    return client.post("/api/backup/restaurar",
                       data={"archivo": (io.BytesIO(contenido), nombre)},
                       content_type="multipart/form-data")


def _nombres_productos():
    conn = database.get_db()
    nombres = sorted(r["nombre"] for r in conn.execute("SELECT nombre FROM productos"))
    conn.close()
    return nombres


@pytest.fixture
def respaldo_con_un_producto(client, crear_producto, tmp_path):
    crear_producto([{"stock": 3, "costo": 1, "precio": 2}], nombre="Antes")
    contenido, copia = _snapshot_gz(tmp_path)
    crear_producto([{"stock": 1, "costo": 1, "precio": 2}], nombre="Después")
    return contenido, copia


def test_restaurar_db_gz_vuelve_a_los_datos_del_respaldo(client, respaldo_con_un_producto):
    contenido, _ = respaldo_con_un_producto

    res = _restaurar(client, contenido)

    assert res.status_code == 200, res.get_json()
    assert _nombres_productos() == ["Antes"]
    # Se guardó una copia de la base anterior (con "Después").
    copia = os.path.join(os.path.dirname(database.DB_PATH), "restauraciones", res.get_json()["copia_anterior"])
    conn = sqlite3.connect(copia)
    assert {r[0] for r in conn.execute("SELECT nombre FROM productos")} == {"Antes", "Después"}
    conn.close()


def test_restaurar_db_sin_comprimir(client, respaldo_con_un_producto):
    _, copia = respaldo_con_un_producto
    res = _restaurar(client, copia.read_bytes(), nombre="backup.db")

    assert res.status_code == 200
    assert _nombres_productos() == ["Antes"]


def test_restaurar_respaldo_viejo_lo_migra(client, respaldo_con_un_producto, tmp_path):
    # Respaldo de antes de los triggers de stock.
    _, copia = respaldo_con_un_producto
    conn = sqlite3.connect(copia)
    conn.execute("DROP TRIGGER trg_stock_producto_update")
    conn.commit()
    conn.close()

    assert _restaurar(client, copia.read_bytes(), nombre="viejo.db").status_code == 200

    conn = database.get_db()
    triggers = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
    conn.close()
    assert "trg_stock_producto_update" in triggers


@pytest.mark.parametrize("contenido, nombre", [
    (b"esto no es una base", "foto.jpg"),
    (gzip.compress(b"tampoco"), "x.db.gz"),
    (b"\x1f\x8b roto", "roto.db.gz"),
])
def test_archivo_invalido_da_400_y_no_toca_la_base(client, crear_producto, contenido, nombre):
    crear_producto([{"stock": 1, "costo": 1, "precio": 2}], nombre="Intacto")

    res = _restaurar(client, contenido, nombre)

    assert res.status_code == 400
    assert _nombres_productos() == ["Intacto"]


def test_base_sqlite_de_otra_app_da_400(client, crear_producto, tmp_path):
    crear_producto([{"stock": 1, "costo": 1, "precio": 2}], nombre="Intacto")
    otra = tmp_path / "otra.db"
    conn = sqlite3.connect(otra)
    conn.execute("CREATE TABLE clientes (id INTEGER)")
    conn.commit()
    conn.close()

    res = _restaurar(client, otra.read_bytes(), "otra.db")

    assert res.status_code == 400
    assert "faltan tablas" in res.get_json()["message"]
    assert _nombres_productos() == ["Intacto"]


def test_restaurar_sin_archivo_da_400(client):
    assert client.post("/api/backup/restaurar").status_code == 400
