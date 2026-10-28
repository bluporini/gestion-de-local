import os

from flask import Blueprint, jsonify, request
from app.supabase_backup import hacer_backup_ahora
from app.restaurar import RespaldoInvalido, restaurar_desde_archivo

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


@backup_bp.route("/backup/restaurar", methods=["POST"])
def restaurar_backup():
    """Reemplaza la base local por la de un archivo de respaldo.

    Recibe el archivo en el campo ``archivo`` (multipart/form-data): un
    ``.db.gz`` descargado de Supabase o un ``.db``. Antes de reemplazar,
    guarda una copia de la base actual en ``restauraciones/``.

    Returns
    -------
    flask.Response
        ``ok=True`` y el nombre de la copia de la base anterior. HTTP 400
        si no se envió archivo o no es un respaldo válido (la base actual
        no se toca). HTTP 403 en la demo web.
    """
    if os.environ.get("DEMO"):
        return jsonify({
            "ok": False,
            "message": "Restaurar respaldos está deshabilitado en la demo."
        }), 403

    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return jsonify({"ok": False, "message": "No se eligió ningún archivo."}), 400

    try:
        copia = restaurar_desde_archivo(archivo)
    except RespaldoInvalido as e:
        return jsonify({"ok": False, "message": str(e)}), 400

    return jsonify({
        "ok": True,
        "message": "¡Respaldo restaurado correctamente!",
        "copia_anterior": os.path.basename(copia),
    })
