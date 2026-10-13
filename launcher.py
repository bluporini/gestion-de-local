"""
Punto de entrada alternativo a wsgi.py: en vez de una ventana de consola,
muestra una ventanita simple con botones para abrir la app, cerrarla,
y ver info del autor. El servidor Flask corre en un hilo de fondo.

Para compilarlo con PyInstaller (en vez de backend/wsgi.py):
    pyinstaller --onefile --windowed --name GestionDeLocal --add-data "frontend:frontend" launcher.py
    # En Windows, --add-data usa ; en vez de ':' -> "frontend;frontend"

--windowed oculta la consola negra (ya no hace falta, porque ahora
la interfaz es esta ventana).
"""

import os
import sys
import json
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import font as tkfont, messagebox

from dotenv import load_dotenv

# --- Mismo manejo de .env que wsgi.py ---
if getattr(sys, "frozen", False):
    env_path = os.path.join(os.path.dirname(sys.executable), ".env")
else:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

load_dotenv(env_path)

if not getattr(sys, "frozen", False):
    # En desarrollo (corriendo `python launcher.py` sin compilar), el
    # paquete `app` vive en backend/app, así que lo agregamos a sys.path.
    # En el ejecutable ya compilado esto NO hace falta ni corresponde:
    # el paquete `app` queda embebido en la raíz del bundle directamente
    # (ver --paths backend en el comando de PyInstaller), por eso el
    # import de abajo funciona igual en ambos casos sin tocar sys.path.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from app.main import create_app  # noqa: E402
from app.supabase_backup import hacer_backup_si_hay_cambios  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", 5000))
URL = f"http://{HOST}:{PORT}/"
IS_FROZEN = getattr(sys, "frozen", False)
UPDATE_STATUS_FILENAME = "update_status.json"

AUTOR_NOMBRE = "BriProducciones"
AUTOR_MENSAJE = (
    "Gestión de Local: stock, ventas, cambios y caja para comercios.\n\n"
    "Desarrollada por BriProducciones."
)


def run_server():
    """Levanta Flask en un hilo aparte. debug siempre en False acá:
    esta ventana reemplaza a la consola, no tiene sentido el reloader."""
    app = create_app()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


# Evita que el respaldo del arranque y el del cierre corran a la vez.
_backup_lock = threading.Lock()


def respaldo_automatico():
    """Sube un respaldo a Supabase si la base cambió desde el último.
    Solo empaquetado: en desarrollo no queremos subir la base de prueba
    al bucket real. Nunca levanta excepciones (no debe trabar la app)."""
    if not IS_FROZEN:
        return

    with _backup_lock:
        try:
            resultado = hacer_backup_si_hay_cambios()
        except Exception as e:  # noqa: BLE001
            resultado = {"ok": False, "error": str(e)}

    if resultado and not resultado.get("ok"):
        print(f"[WARN] No se pudo hacer el respaldo automático: {resultado.get('error')}")


def check_for_updates():
    """Idéntico a wsgi.py: dispara updater.exe --check sin bloquear,
    solo informa (no aplica nada). Solo tiene sentido empaquetado."""
    if not IS_FROZEN:
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


def apply_pending_update():
    """
    Si el último `updater.exe --check` dejó registrada una versión nueva,
    lanza updater.exe (sin --check) y devuelve True para que la app se
    cierre: el updater reemplaza GestionDeLocal.exe y la vuelve a abrir.

    update_status.json se borra ANTES de lanzar el updater: si la
    actualización falla, el próximo arranque es normal (no queda en loop)
    y el --check en segundo plano vuelve a avisar.
    """
    if not IS_FROZEN:
        return False

    exe_dir = os.path.dirname(sys.executable)
    updater_path = os.path.join(exe_dir, "updater.exe")
    status_path = os.path.join(exe_dir, UPDATE_STATUS_FILENAME)

    if not os.path.exists(updater_path):
        return False

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    if not isinstance(status, dict) or not status.get("update_available"):
        return False

    try:
        os.remove(status_path)
        subprocess.Popen(
            [updater_path],
            cwd=exe_dir,
            creationflags=(
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt" else 0
            ),
        )
    except OSError as e:
        print(f"[WARN] No se pudo lanzar la actualización: {e}")
        return False

    return True


def main():
    if apply_pending_update():
        return

    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=check_for_updates, daemon=True).start()
    # Cubre el caso de que la última vez la app no se haya cerrado con el
    # botón (PC apagada, cierre forzado): sube lo que haya quedado sin respaldar.
    threading.Thread(target=respaldo_automatico, daemon=True).start()

    root = tk.Tk()
    root.title("Gestión de Local")
    root.geometry("420x410")
    root.resizable(False, False)
    root.configure(bg="#fdf2f8")

    titulo_font = tkfont.Font(family="Segoe UI", size=17, weight="bold")
    texto_font = tkfont.Font(family="Segoe UI", size=10)
    boton_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    tk.Label(
        root, text="Gestión de Local", font=titulo_font, bg="#fdf2f8", fg="#be185d"
    ).pack(pady=(25, 5))

    tk.Label(
        root,
        text="Stock, ventas, cambios y caja\n"
             "de tu local, en tu computadora.",
        font=texto_font, bg="#fdf2f8", fg="#4b5563", justify="center",
    ).pack(pady=(0, 25))

    def abrir_navegador():
        webbrowser.open(URL)

    def cerrar_app():
        if IS_FROZEN:
            estado.config(text="Guardando respaldo, un momento...")
            root.config(cursor="watch")
            root.update()
            # Con tope de tiempo: sin internet no queremos que la app
            # quede colgada al cerrar. Lo que no se suba ahora se sube
            # en el próximo arranque.
            hilo = threading.Thread(target=respaldo_automatico, daemon=True)
            hilo.start()
            hilo.join(timeout=30)
        root.destroy()
        os._exit(0)  # corta también el hilo del servidor Flask

    def ver_autor():
        messagebox.showinfo(
            f"Sobre {AUTOR_NOMBRE}",
            f"{AUTOR_MENSAJE}",
        )

    tk.Button(
        root, text="🌐  Abrir en el navegador", font=boton_font,
        bg="#ec4899", fg="white", activebackground="#db2777",
        relief="flat", padx=10, pady=10, cursor="hand2",
        command=abrir_navegador,
    ).pack(pady=6, ipadx=10, fill="x", padx=40)

    tk.Button(
        root, text="Cerrar aplicación", font=texto_font,
        bg="#e5e7eb", fg="#374151", relief="flat", padx=10, pady=8,
        cursor="hand2", command=cerrar_app,
    ).pack(pady=6, fill="x", padx=60)

    tk.Button(
        root, text="ℹ️  Sobre el autor", font=texto_font,
        bg="#fdf2f8", fg="#9ca3af", relief="flat", cursor="hand2",
        command=ver_autor,
    ).pack(pady=(15, 0))

    estado = tk.Label(root, text="", font=texto_font, bg="#fdf2f8", fg="#6b7280")
    estado.pack(pady=(10, 0))

    root.protocol("WM_DELETE_WINDOW", cerrar_app)

    root.mainloop()


if __name__ == "__main__":
    main()