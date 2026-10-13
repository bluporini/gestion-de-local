"""
Punto de entrada de la DEMO WEB (por ejemplo, en Render).

La app real es de escritorio (launcher.py). Esta variante la sirve en la
web con datos de ejemplo:

  - Genera una base sintética (~2 años de ventas, con fecha de hoy) con
    test/generar_db.py si todavía no existe.
  - Activa DEMO=1: la interfaz muestra un cartel de demo y los respaldos
    a Supabase quedan deshabilitados.

El disco de los servicios gratuitos es efímero: cuando el servidor se
reinicia (por ejemplo, tras un rato sin visitas) la base se vuelve a
generar, así que los datos de la demo se reinician solos.

Uso:
    gunicorn --chdir backend demo:app --workers 1
"""

import os
import runpy
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DEMO = os.environ.get("APP_DB_PATH") or os.path.join(tempfile.gettempdir(), "gestion_de_local_demo.db")

os.environ["DEMO"] = "1"
os.environ["APP_DB_PATH"] = DB_DEMO

if not os.path.exists(DB_DEMO):
    os.environ["DEMO_DB_PATH"] = DB_DEMO
    runpy.run_path(os.path.join(RAIZ, "test", "generar_db.py"), run_name="__main__")

from app.main import create_app  # noqa: E402  (después de fijar APP_DB_PATH)

app = create_app()
