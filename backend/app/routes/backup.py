import os

from flask import Blueprint, jsonify
from app.supabase_backup import hacer_backup_ahora

backup_bp = Blueprint("backup", __name__, url_prefix="/api")

@backup_bp.route("/backup/supabase", methods=["POST"])
def subir_backup_supabase():
    """Realiza un respaldo de la base de datos en Supabase.

    Ejecuta el proceso de respaldo y devuelve el resultado de la
    operación en formato JSON.

    Returns
    -------
    flask.Response
        Respuesta JSON con ``ok=True`` y el nombre del archivo generado
        si el respaldo se realizó correctamente.

        Si el respaldo falla, devuelve ``ok=False`` junto con el motivo
        del error y el código HTTP 500.

    Examples
    --------
    POST /backup/supabase

    Respuesta exitosa::

        {
            "ok": true,
            "message": "¡Respaldo realizado correctamente!",
            "archivo": "backup_2026-09-19.db"
        }

    Respuesta con error::

        {
            "ok": false,
            "message": "No se pudo realizar el respaldo."
        }
    """

    if os.environ.get("DEMO"):
        return jsonify({
            "ok": False,
            "message": "Los respaldos están deshabilitados en la demo."
        }), 403

    resultado = hacer_backup_ahora()

    if resultado.get("ok"):
        return jsonify({
            "ok": True,
            "message": "¡Respaldo realizado correctamente!",
            "archivo": resultado.get("archivo")
        })

    return jsonify({
        "ok": False,
        "message": resultado.get(
            "error",
            "No se pudo realizar el respaldo."
        )
    }), 500
