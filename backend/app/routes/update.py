import json
import os
import sys

from flask import Blueprint, jsonify

update_bp = Blueprint("update", __name__, url_prefix="/api/update")

STATUS_FILENAME = "update_status.json"


def _status_path():
    """
    Ubicación de update_status.json (lo escribe updater.exe --check).
    Empaquetado: junto al ejecutable. En desarrollo: raíz del repo,
    para poder probar el banner con un archivo armado a mano.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    return os.path.join(base, STATUS_FILENAME)


@update_bp.get("/status")
def status():
    """Devuelve el estado de actualización, o update_available=False si no hay info."""
    try:
        with open(_status_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return jsonify({"update_available": False})

    if not isinstance(data, dict):
        return jsonify({"update_available": False})
    return jsonify(data)
