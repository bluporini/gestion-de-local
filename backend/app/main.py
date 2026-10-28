import os
import sys
from flask import Flask, jsonify, send_from_directory
from datetime import datetime, timezone

from app.database import init_db, cerrar_conexiones
from app.routes.productos import productos_bp
from app.routes.ventas import ventas_bp
from app.routes.tipos import tipos_bp
from app.routes.dashboard import dashboard_bp
from app.routes.backup import backup_bp
from app.routes.cambios import cambios_bp
from app.routes.update import update_bp
from app.routes.configuracion import configuracion_bp
from app.routes.exportar import exportar_bp
from app.routes.estadisticas import estadisticas_bp
from app.routes.notas import notas_bp
from app.routes.envios import envios_bp


def _frontend_dir() -> str:
    """
    Ubicación de la carpeta frontend/, tanto en desarrollo como empaquetado
    con PyInstaller (--onefile). En el exe, los archivos agregados con
    --add-data quedan extraídos en sys._MEIPASS al arrancar.
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
        return os.path.join(base, "frontend")
    # backend/app/main.py -> subir dos niveles y entrar a frontend/
    return os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


def create_app():
    app = Flask(__name__, static_folder=_frontend_dir(), static_url_path="")
    # Inicializa la base de datos SQLite local al arrancar la aplicación
    init_db()
    app.teardown_appcontext(cerrar_conexiones)
    # Tope para archivos subidos (restaurar un respaldo).
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

    app.register_blueprint(productos_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(tipos_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(cambios_bp)
    app.register_blueprint(update_bp)
    app.register_blueprint(configuracion_bp)
    app.register_blueprint(exportar_bp)
    app.register_blueprint(estadisticas_bp)
    app.register_blueprint(notas_bp)
    app.register_blueprint(envios_bp)

    @app.get("/")
    def index():
        # Sirve el frontend (index.html) en la raíz.
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/status")
    def status():
        return jsonify({
            "ok": True,
            "servicio": "stock-app-backend",
            "hora": datetime.now(timezone.utc).isoformat(),
            # True en la demo web (backend/demo.py): el frontend muestra un cartel.
            "demo": bool(os.environ.get("DEMO")),
        })

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Ruta no encontrada"}), 404

    @app.errorhandler(Exception)
    def handle_error(e):
        app.logger.error(f"Error no controlado: {e}")
        return jsonify({"error": str(e)}), 500

    return app