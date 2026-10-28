import csv
import io
from datetime import datetime, timedelta, timezone

import pytest


def _hoy_local():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d")


def _leer_csv(res):
    texto = res.get_data(as_text=True)
    assert texto.startswith("﻿"), "falta el BOM (Excel mostraría mal los acentos)"
    return list(csv.reader(io.StringIO(texto[1:]), delimiter=";"))


@pytest.fixture
def con_ventas(client, crear_producto, vender):
    producto = crear_producto([
        {"talle": "M", "color": "Negro", "stock": 10, "costo": 1000, "precio": 2500.5},
    ], nombre="Body \"Clásico\"")
    a = producto["variantes_producto"][0]["id"]
    vender([{"variante_id": a, "cantidad": 2}], cliente="Ana; García")
    devuelta = vender([{"variante_id": a, "cantidad": 1}])
    client.post(f"/api/ventas/{devuelta['id']}/devolucion")


def test_exportar_ventas_del_dia(client, con_ventas):
    hoy = _hoy_local()
    res = client.get(f"/api/exportar/ventas.csv?desde={hoy}&hasta={hoy}")

    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"]
    filas = _leer_csv(res)
    encabezado, datos = filas[0], filas[1:]
    assert encabezado[0] == "Código" and encabezado[-2:] == ["Total", "Ganancia"]
    assert len(datos) == 2

    primera = dict(zip(encabezado, datos[0]))
    assert primera["Cliente"] == "Ana; García"           # el ';' no rompe las columnas
    assert primera["Productos"] == '2x Body "Clásico" (M/Negro)'
    assert primera["Total"] == "5001,00"                  # coma decimal
    assert primera["Estado"] == "Realizada"
    assert dict(zip(encabezado, datos[1]))["Estado"] == "Devolución"


def test_exportar_ventas_fuera_de_rango_viene_vacio(client, con_ventas):
    res = client.get("/api/exportar/ventas.csv?desde=2000-01-01&hasta=2000-01-31")
    assert len(_leer_csv(res)) == 1  # solo el encabezado


@pytest.mark.parametrize("query", ["", "?desde=2026-01-01", "?desde=hola&hasta=2026-01-01",
                                   "?desde=2026-02-01&hasta=2026-01-01"])
def test_exportar_ventas_con_fechas_invalidas_da_400(client, query):
    assert client.get(f"/api/exportar/ventas.csv{query}").status_code == 400


def test_exportar_stock(client, con_ventas):
    res = client.get("/api/exportar/stock.csv")

    assert res.status_code == 200
    filas = _leer_csv(res)
    fila = dict(zip(filas[0], filas[1]))
    # 10 - 2 vendidas (la devolución repuso la otra).
    assert fila["Stock"] == "8"
    assert fila["Valor del stock (a costo)"] == "8000,00"
