import os
import gzip
import json
import shutil
import sqlite3
import sys
import tempfile

from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client, Client

from app.database import get_db_path


# Carga las variables de entorno.
#
# En desarrollo:
#   backend/.env
#
# En la aplicación empaquetada:
#   1. .env junto al ejecutable (opcional, sirve para sobreescribir).
#   2. supabase.env embebido en el ejecutable (lo genera el workflow de
#      build desde los secrets SUPABASE_URL/SUPABASE_KEY). Va adentro del
#      exe para que llegue también con cada actualización automática,
#      que solo reemplaza el .exe.
#
# load_dotenv no pisa variables ya definidas, así que gana el primero
# que las defina.

if getattr(sys, "frozen", False):
    load_dotenv(os.path.join(os.path.dirname(sys.executable), ".env"))
    load_dotenv(os.path.join(sys._MEIPASS, "supabase.env"))  # type: ignore[attr-defined]
else:
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    load_dotenv(os.path.join(BASE_DIR, ".env"))


BUCKET_NAME = "backups"

# Carpetas del bucket: los respaldos de la app instalada en la PC de la
# clienta van a "clienta/" y los hechos en desarrollo (app sin compilar)
# a "desarrollo/". Así una prueba local nunca se mezcla con sus respaldos
# ni altera su retención (scripts/limpiar_backups.py).
CARPETA_CLIENTA = "clienta"
CARPETA_DESARROLLO = "desarrollo"

# Archivo junto a la base con el estado del último respaldo. Se guarda
# fuera de la base a propósito: escribir en la base cambia su fecha de
# modificación y haría parecer que siempre hay cambios sin respaldar.
ESTADO_FILENAME = "estado_backup.json"


def ruta_en_bucket(nombre_archivo):
    """Ruta dentro del bucket: ``clienta/`` en la app compilada, o
    ``desarrollo/`` si se está corriendo el código sin compilar."""
    carpeta = CARPETA_CLIENTA if getattr(sys, "frozen", False) else CARPETA_DESARROLLO
    return f"{carpeta}/{nombre_archivo}"


def _get_supabase() -> Client:
    """Crea y devuelve un cliente de Supabase a partir de la configuración.

    Las credenciales se obtienen de las variables de entorno
    ``SUPABASE_URL`` y ``SUPABASE_KEY``.

    Returns
    -------
    Client
        Cliente de Supabase configurado con la URL y la clave obtenidas
        de las variables de entorno.

    Raises
    ------
    RuntimeError
        Si no están definidas ``SUPABASE_URL`` o ``SUPABASE_KEY``.
    """

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Faltan las variables SUPABASE_URL y SUPABASE_KEY "
            "en el archivo .env."
        )

    return create_client(url, key)


def supabase_configurado() -> bool:
    """Indica si hay credenciales de Supabase disponibles."""
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))


def _ruta_estado() -> str:
    return os.path.join(os.path.dirname(get_db_path()), ESTADO_FILENAME)


def _leer_estado() -> dict:
    try:
        with open(_ruta_estado(), "r", encoding="utf-8") as f:
            estado = json.load(f)
        return estado if isinstance(estado, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _guardar_estado(db_mtime: float):
    """Registra la fecha del último respaldo exitoso y la fecha de
    modificación que tenía la base en ese momento."""
    estado = {
        "ultimo_backup": datetime.now().isoformat(timespec="seconds"),
        "db_mtime": db_mtime,
    }
    try:
        with open(_ruta_estado(), "w", encoding="utf-8") as f:
            json.dump(estado, f, indent=2)
    except OSError:
        pass


def _crear_backup_comprimido(carpeta: str):
    """Crea una copia comprimida y consistente de la base de datos SQLite.

    Usa la API de backup de SQLite (en vez de copiar el archivo) para que
    la copia sea consistente aunque la app esté escribiendo en ese momento.

    Parameters
    ----------
    carpeta : str
        Carpeta temporal donde se generan los archivos.

    Returns
    -------
    tuple[str, str]
        ``(ruta_archivo, nombre_archivo)`` del backup comprimido.

    Raises
    ------
    FileNotFoundError
        Si no se encuentra el archivo de la base de datos SQLite.

    Notes
    -----
    El nombre tiene el formato ``backup-YYYY-MM-DD_HHMMSS.db.gz``: es único
    por respaldo, así nunca hace falta sobrescribir un archivo existente
    (la clave de la app solo tiene permiso para subir, no para modificar).
    """

    db_path = get_db_path()

    if not os.path.exists(db_path):
        raise FileNotFoundError(
            "No se encontró la base de datos local."
        )

    nombre_archivo = f"backup-{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db.gz"
    ruta_copia = os.path.join(carpeta, "copia.db")
    ruta_backup = os.path.join(carpeta, nombre_archivo)

    origen = sqlite3.connect(db_path)
    destino = sqlite3.connect(ruta_copia)
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()

    with open(ruta_copia, "rb") as f_origen:
        with gzip.open(ruta_backup, "wb") as f_destino:
            shutil.copyfileobj(f_origen, f_destino)

    return ruta_backup, nombre_archivo


def hacer_backup_ahora():
    """Crea un backup de la base de datos y lo sube a Supabase.

    Returns
    -------
    dict
        Resultado de la operación con las siguientes claves:

        - ``ok`` : ``True`` si el backup se completó correctamente.
        - ``archivo`` : ruta del archivo subido dentro del bucket
          (``clienta/...`` o ``desarrollo/...``, ver ``ruta_en_bucket``).
        - ``ok`` : ``False`` y ``error`` con el mensaje de la excepción si
          alguna etapa del proceso falla.

    Notes
    -----
    La app solo sube archivos nuevos: no lista, no sobrescribe ni borra
    nada del bucket. La retención (qué respaldos viejos se borran) la hace
    el workflow ``limpiar-backups.yml`` con una clave aparte.
    """

    try:
        supabase = _get_supabase()

        # Se toma antes de copiar: si la base cambia durante el respaldo,
        # el próximo chequeo lo detecta como cambio pendiente.
        db_mtime = os.path.getmtime(get_db_path())

        with tempfile.TemporaryDirectory() as carpeta:
            ruta_backup, nombre_archivo = _crear_backup_comprimido(carpeta)

            ruta = ruta_en_bucket(nombre_archivo)
            with open(ruta_backup, "rb") as archivo:
                supabase.storage.from_(BUCKET_NAME).upload(
                    ruta,
                    archivo,
                    {"content-type": "application/gzip"},
                )

        _guardar_estado(db_mtime)

        return {
            "ok": True,
            "archivo": ruta,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def hay_cambios_sin_respaldar() -> bool:
    """Indica si la base cambió desde el último respaldo exitoso."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return False

    db_mtime_respaldado = _leer_estado().get("db_mtime")
    if db_mtime_respaldado is None:
        return True

    return os.path.getmtime(db_path) > db_mtime_respaldado


def hacer_backup_si_hay_cambios():
    """Respaldo automático: solo sube si hay credenciales y la base cambió
    desde el último respaldo. Pensado para correr al abrir y al cerrar la
    app sin llenar el bucket de copias idénticas.

    Returns
    -------
    dict | None
        El resultado de ``hacer_backup_ahora()``, o ``None`` si no hizo falta.
    """
    if not supabase_configurado() or not hay_cambios_sin_respaldar():
        return None
    return hacer_backup_ahora()
