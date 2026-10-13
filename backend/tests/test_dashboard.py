def test_resumen_cuenta_ventas_realizadas_y_excluye_devoluciones(client, crear_producto, vender):
    producto = crear_producto([{"stock": 10, "costo": 1000, "precio": 2500}])
    a = producto["variantes_producto"][0]["id"]

    vender([{"variante_id": a, "cantidad": 2}])           # 5000, ganancia 3000
    devuelta = vender([{"variante_id": a, "cantidad": 1}])
    client.post(f"/api/ventas/{devuelta['id']}/devolucion")

    resumen = client.get("/api/dashboard/resumen").get_json()

    assert resumen["ventas_hoy"] == 1
    assert resumen["ingresos_hoy"] == 5000
    assert resumen["ganancia_mes"] == 3000
