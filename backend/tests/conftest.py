"""
Fixtures y helpers compartidos por los tests.

Cada test usa una base SQLite nueva en una carpeta temporal: se crea con
el mismo `init_db()` que usa la app (schema.sql + migraciones), así que
los tests corren contra el esquema real.
"""

import pytest

import app.database as database
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "stock_test.db"))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def crear_producto(client):
    """Crea un producto con variantes y devuelve el JSON de la respuesta.

    Cada variante es un dict con al menos `stock`, `costo` y `precio`.
    """
    contador = {"n": 0}

    def _crear(variantes, nombre=None):
        contador["n"] += 1
        res = client.post("/api/productos", json={
            "nombre": nombre or f"Producto {contador['n']}",
            "codigo": f"TEST{contador['n']:03d}",
            "variantes": variantes,
        })
        assert res.status_code == 201, res.get_json()
        return res.get_json()

    return _crear


@pytest.fixture
def vender(client):
    """Registra una venta en efectivo (pagando justo) y devuelve el JSON."""

    def _vender(items, metodo_pago="efectivo", **extra):
        body = {"metodo_pago": metodo_pago, "items": items, **extra}
        if metodo_pago == "efectivo" and "monto_pagado" not in extra:
            body["monto_pagado"] = 10_000_000
        res = client.post("/api/ventas", json=body)
        assert res.status_code == 201, res.get_json()
        return res.get_json()

    return _vender


def stock_variante(variante_id):
    conn = database.get_db()
    fila = conn.execute(
        "SELECT stock_actual FROM variantes_producto WHERE id = ?", (variante_id,)
    ).fetchone()
    conn.close()
    return fila["stock_actual"]


def venta(venta_id):
    conn = database.get_db()
    fila = conn.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,)).fetchone()
    conn.close()
    return dict(fila) if fila else None


def assert_stock_consistente():
    """El stock de cada producto tiene que ser la suma del de sus variantes."""
    conn = database.get_db()
    filas = conn.execute("""
        SELECT p.id, p.stock_actual,
               COALESCE((SELECT SUM(v.stock_actual) FROM variantes_producto v
                         WHERE v.producto_id = p.id), 0) AS suma
        FROM productos p
    """).fetchall()
    conn.close()
    for f in filas:
        assert f["stock_actual"] == f["suma"], (
            f"Producto {f['id']}: stock_actual={f['stock_actual']} "
            f"pero la suma de variantes es {f['suma']}"
        )
