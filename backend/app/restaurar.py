"""
Restauración de la base desde un archivo de respaldo.

La app no puede descargar respaldos de Supabase (su clave solo puede
subir, a propósito: ver docs/respaldos.md). Para restaurar, el archivo se
descarga del panel de Supabase y se elige desde la pantalla de
Configuración.
"""

import gzip
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

from app.database import get_db_path, init_db

CABECERA_SQLITE = b"SQLite format 3\x00"
CABECERA_GZIP = b"\x1f\x8b"
TABLAS_REQUERIDAS = {"productos", "variantes_producto", "ventas", "venta_items"}
# Tope para el archivo descomprimido (evita que un .gz malicioso llene el disco).
TAMANIO_MAXIMO = 500 * 1024 * 1024
CARPETA_COPIAS = "restauraciones"
COPIAS_A_CONSERVAR = 5


class RespaldoInvalido(ValueError):
    """El archivo elegido no es un respaldo válido de la app."""


def _descomprimir_si_hace_falta(ruta_subida, ruta_destino):
    with open(ruta_subida, "rb") as f:
        es_gzip = f.read(2) == CABECERA_GZIP

    if not es_gzip:
        shutil.move(ruta_subida, ruta_destino)
        return

    escritos = 0
    try:
        with gzip.open(ruta_subida, "rb") as origen, open(ruta_destino, "wb") as destino:
            while bloque := origen.read(1024 * 1024):
                escritos += len(bloque)
                if escritos > TAMANIO_MAXIMO:
                    raise RespaldoInvalido("El respaldo es demasiado grande.")
                destino.write(bloque)
    except (OSError, EOFError) as e:
        raise RespaldoInvalido("El archivo .gz está dañado o incompleto.") from e


def _validar_base(ruta):
    with open(ruta, "rb") as f:
        if f.read(len(CABECERA_SQLITE)) != CABECERA_SQLITE:
            raise RespaldoInvalido("El archivo no es un respaldo de la app (no es una base SQLite).")

    conn = sqlite3.connect(ruta)
    try:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if resultado != "ok":
            raise RespaldoInvalido("El respaldo está dañado (falló la verificación de integridad).")
        tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        raise RespaldoInvalido("El respaldo está dañado.") from e
    finally:
        conn.close()

    faltantes = TABLAS_REQUERIDAS - tablas
    if faltantes:
        raise RespaldoInvalido(
            "El archivo no es un respaldo de la app (faltan tablas: " + ", ".join(sorted(faltantes)) + ")."
        )


def _copiar_base(origen, destino):
    """Copia una base SQLite con la API de backup (segura aunque esté en uso)."""
    src = sqlite3.connect(origen)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _guardar_copia_de_la_base_actual():
    """Guarda la base actual antes de reemplazarla y borra copias viejas."""
    db_path = get_db_path()
    carpeta = os.path.join(os.path.dirname(db_path), CARPETA_COPIAS)
    os.makedirs(carpeta, exist_ok=True)

    nombre = f"antes_de_restaurar_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db"
    ruta = os.path.join(carpeta, nombre)
    if os.path.exists(db_path):
        _copiar_base(db_path, ruta)

    copias = sorted(
        (os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.startswith("antes_de_restaurar_")),
        reverse=True,
    )
    for vieja in copias[COPIAS_A_CONSERVAR:]:
        try:
            os.remove(vieja)
        except OSError:
            pass
    return ruta


def restaurar_desde_archivo(archivo):
    """Reemplaza la base local por la del archivo de respaldo.

    Parameters
    ----------
    archivo : werkzeug.datastructures.FileStorage
        Respaldo ``.db.gz`` (tal como se descarga de Supabase) o ``.db``.

    Returns
    -------
    str
        Ruta de la copia de la base anterior (por si hay que volver atrás).

    Raises
    ------
    RespaldoInvalido
        Si el archivo no es un respaldo válido. En ese caso la base actual
        no se toca.
    """
    with tempfile.TemporaryDirectory() as carpeta_temp:
        ruta_subida = os.path.join(carpeta_temp, "subido")
        ruta_respaldo = os.path.join(carpeta_temp, "respaldo.db")
        archivo.save(ruta_subida)

        _descomprimir_si_hace_falta(ruta_subida, ruta_respaldo)
        _validar_base(ruta_respaldo)

        copia = _guardar_copia_de_la_base_actual()
        _copiar_base(ruta_respaldo, get_db_path())

    # Un respaldo de una versión anterior puede no tener columnas o
    # triggers nuevos: las migraciones lo ponen al día.
    init_db()
    return copia
