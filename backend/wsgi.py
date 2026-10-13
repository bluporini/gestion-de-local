import os
import sys
import threading
import time
import subprocess
import webbrowser

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    env_path = os.path.join(
        os.path.dirname(sys.executable),
        ".env"
    )
else:
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".env"
    )

load_dotenv(env_path)
from app.main import create_app

app = create_app()

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", 5000))

# Cuando la app está empaquetada con PyInstaller, sys.frozen es True.
# En ese caso, debug siempre apagado (no queremos el reloader ni el
# debugger de Werkzeug expuesto en la app final del cliente).
IS_FROZEN = getattr(sys, "frozen", False)
DEBUG = False if IS_FROZEN else os.environ.get("FLASK_DEBUG", "false").lower() == "true"


def open_browser():
    # Pequeña espera para darle tiempo al servidor a levantar antes de abrir la pestaña.
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")


def check_for_updates():
    """
    Lanza updater.exe --check en segundo plano, sin bloquear el arranque
    de la app. Solo informa si hay una versión nueva (no la aplica sola;
    eso queda a criterio del usuario/flujo de updater.py).
    """
    if not IS_FROZEN:
        # En desarrollo (corriendo con `python wsgi.py`) no tiene sentido
        # buscar el updater.exe empaquetado.
        return

    exe_dir = os.path.dirname(sys.executable)
    updater_path = os.path.join(exe_dir, "updater.exe")

    if not os.path.exists(updater_path):
        return

    try:
        subprocess.Popen(
            [updater_path, "--check"],
            cwd=exe_dir,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as e:
        print(f"[WARN] No se pudo lanzar el chequeo de actualizaciones: {e}")


if __name__ == "__main__":
    # Evita abrir el navegador dos veces si Flask usa el auto-reloader
    # (solo relevante en desarrollo, con DEBUG=True).
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Thread(target=open_browser, daemon=True).start()
        threading.Thread(target=check_for_updates, daemon=True).start()

    app.run(host=HOST, port=PORT, debug=DEBUG)