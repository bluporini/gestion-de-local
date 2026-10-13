"""
updater.py
==========
Updater para la aplicación, basado en Releases de GitHub.

Los releases se publican en un repo privado aparte que solo contiene
binarios. El instalador deja junto a este ejecutable un updater_config.json
con el nombre de ese repo y un token de SOLO LECTURA sobre él, que no da
acceso al repo de código.

Flujo:
  1. Lee la versión local desde version.json (en la raíz del proyecto/instalación).
  2. Consulta la API de GitHub para obtener el último release publicado.
  3. Si el tag del release es más nuevo que la versión local, descarga el
     asset adjunto al release.
  4. Hace backup de lo que va a reemplazar.
  5. Cierra la app (si está corriendo), aplica la actualización, y vuelve a
     lanzar la app.

Modos de actualización (se elige automáticamente según los assets del release):
  - MODO EXE (onefile, el que usa este proyecto): el release trae un asset
    con el mismo nombre que app_executable (GestionDeLocal.exe). Se exige
    match exacto para no confundirlo con el instalador, que también es un
    .exe adjunto al release. El updater hace backup del exe actual
    (GestionDeLocal_backup_<timestamp>.exe) y lo reemplaza directo.
  - MODO ZIP (fallback, por si algún día también hay que tocar archivos
    sueltos aparte del exe, como schema.sql o version.json): el release
    trae un .zip que se descomprime y se copia por encima de install_dir.

Requisitos del lado del repo:
  - Cada Release debe tener un tag tipo "v1.2.3" (o "1.2.3").
  - Cada Release debe tener un asset llamado exactamente GestionDeLocal.exe
    o, en su defecto, un .zip.

Configuración (owner y ejecutable tienen valores por defecto; repo_name no):
  - Archivo updater_config.json junto a este script (lo genera el workflow):
      {
        "github_token": "github_pat_xxx (solo lectura del repo de releases)",
        "repo_owner": "bluporini",
        "repo_name": "<repo de releases>",
        "install_dir": "C:/ruta/a/la/instalacion",
        "app_executable": "GestionDeLocal.exe"
      }
  - O variables de entorno REPO_OWNER, REPO_NAME, UPDATER_GITHUB_TOKEN
    (útil para probar a mano).

Uso:
  python updater.py            -> chequea y actualiza si hay una versión nueva
  python updater.py --check    -> solo informa si hay actualización disponible
"""

import os
import sys
import json
import time
import shutil
import zipfile
import tempfile
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

import urllib.request
import urllib.error

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

CONFIG_FILENAME = "updater_config.json"
VERSION_FILENAME = "version.json"
BACKUP_DIR_PREFIX = "backup_"

DEFAULT_REPO_OWNER = "bluporini"
# Sin valor por defecto: viene de updater_config.json (variable RELEASES_REPO
# del workflow) o de la variable de entorno REPO_NAME.
DEFAULT_REPO_NAME = ""
DEFAULT_APP_EXECUTABLE = "GestionDeLocal.exe"

# Carpetas/archivos que NUNCA se tocan al actualizar (datos del usuario, DB, etc.)
PROTECTED_PATHS = {
    "stock_local.db",
    "backend/venv",
    "backend/app/__pycache__",
    ".env",
}


def script_dir() -> Path:
    """Carpeta donde vive este script (o el ejecutable empaquetado)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def load_config() -> dict:
    """Carga configuración desde archivo y/o variables de entorno."""
    cfg = {
        # No se usa GITHUB_TOKEN a propósito: instalaciones viejas lo tienen
        # definido con un token ya revocado, y mandarlo daría 401 aunque el
        # repo de releases sea público.
        "github_token": os.environ.get("UPDATER_GITHUB_TOKEN", ""),
        "repo_owner": os.environ.get("REPO_OWNER", DEFAULT_REPO_OWNER),
        "repo_name": os.environ.get("REPO_NAME", DEFAULT_REPO_NAME),
        "install_dir": str(script_dir()),
        "app_executable": DEFAULT_APP_EXECUTABLE,
    }

    config_path = script_dir() / CONFIG_FILENAME
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            cfg.update({k: v for k, v in file_cfg.items() if v})
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] No se pudo leer {CONFIG_FILENAME}: {e}")

    missing = [k for k in ("repo_owner", "repo_name") if not cfg[k]]
    if missing:
        raise SystemExit(
            f"[ERROR] Faltan datos de configuración: {', '.join(missing)}.\n"
            f"Definilos por variable de entorno o en {CONFIG_FILENAME}."
        )
    return cfg


# --------------------------------------------------------------------------
# Versionado
# --------------------------------------------------------------------------

def parse_version(v: str) -> tuple:
    """Convierte 'v1.2.3' o '1.2.3' en (1, 2, 3) para comparar."""
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def get_local_version(install_dir: Path) -> str:
    version_file = install_dir / VERSION_FILENAME
    if not version_file.exists():
        print(f"[WARN] No existe {VERSION_FILENAME}, asumiendo versión 0.0.0")
        return "0.0.0"
    with open(version_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("version", "0.0.0")


def set_local_version(install_dir: Path, version: str):
    version_file = install_dir / VERSION_FILENAME
    data = {}
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["version"] = version
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# GitHub API
# --------------------------------------------------------------------------

def github_request(url: str, token: str, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        # Se devuelve abierta: el llamador la usa con `with` y la cierra.
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("[ERROR] Token de GitHub inválido o sin permisos.")
        if e.code == 404:
            raise SystemExit("[ERROR] Repo o release no encontrado (revisá owner/repo/privacidad).")
        raise


def get_latest_release(cfg: dict) -> dict:
    url = f"https://api.github.com/repos/{cfg['repo_owner']}/{cfg['repo_name']}/releases/latest"
    with github_request(url, cfg["github_token"]) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_update_asset(release: dict, app_executable: str) -> dict:
    """
    Busca el asset a descargar, priorizando:
      1) Un asset cuyo nombre sea exactamente el ejecutable (GestionDeLocal.exe)
         -> reemplazo directo de onefile.
      2) Un asset .zip (modo carpeta completa, con overlay de archivos).

    No se toma "cualquier .exe": el release también trae el instalador
    (GestionDeLocal_Setup_x.y.z.exe) y no debe reemplazar a la app.
    """
    assets = release.get("assets", [])

    if app_executable:
        for asset in assets:
            if asset["name"] == app_executable:
                return {"asset": asset, "mode": "exe"}

    for asset in assets:
        if asset["name"].lower().endswith(".zip"):
            return {"asset": asset, "mode": "zip"}

    raise SystemExit(
        f"[ERROR] El release más reciente no tiene el asset {app_executable} ni un .zip adjunto."
    )


def download_asset(asset: dict, token: str, dest_path: Path):
    """Descarga un asset vía la API (Accept: application/octet-stream).
    Funciona tanto en repos públicos (sin token) como privados (con token)."""
    url = asset["url"]  # url de la API, no browser_download_url (ese no sirve en repos privados)
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/octet-stream")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    print(f"[INFO] Descargando {asset['name']} ({asset['size'] / 1024:.0f} KB)...")
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        shutil.copyfileobj(resp, out)
    print(f"[INFO] Descarga completa -> {dest_path}")


# --------------------------------------------------------------------------
# Reemplazo directo de ejecutable onefile
# --------------------------------------------------------------------------

def backup_exe(install_dir: Path, app_executable: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current = install_dir / app_executable
    backup_path = install_dir / f"{current.stem}_backup_{timestamp}{current.suffix}"
    if current.exists():
        print(f"[INFO] Backup del ejecutable actual -> {backup_path}")
        shutil.copy2(current, backup_path)
    return backup_path


def replace_exe(install_dir: Path, app_executable: str, new_exe_path: Path):
    """
    Reemplaza el .exe actual por el nuevo. Como el proceso que corre este
    updater (updater.exe) es distinto del proceso de la app (GestionDeLocal.exe),
    no hay problema en sobreescribir mientras el updater corre; solo hay
    que asegurarse de que la app esté cerrada (stop_app ya se llamó antes).
    """
    target = install_dir / app_executable
    print(f"[INFO] Reemplazando {target} ...")
    # Justo después del taskkill, Windows puede tardar un momento en
    # liberar el archivo: reintentar unos segundos antes de rendirse.
    for intento in range(10):
        try:
            shutil.copy2(new_exe_path, target)
            break
        except PermissionError:
            if intento == 9:
                raise
            time.sleep(1)
    # En Linux/Mac, asegurar permiso de ejecución
    if os.name != "nt":
        target.chmod(target.stat().st_mode | 0o111)


def cleanup_old_backups(install_dir: Path, app_executable: str, keep: int = 3):
    """Borra backups viejos del exe, dejando solo los últimos `keep`."""
    stem = Path(app_executable).stem
    backups = sorted(
        install_dir.glob(f"{stem}_backup_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Backup y aplicación de la actualización (modo carpeta / zip)
# --------------------------------------------------------------------------

def is_protected(rel_path: Path) -> bool:
    rel_str = rel_path.as_posix()
    return any(rel_str == p or rel_str.startswith(p + "/") for p in PROTECTED_PATHS)


def backup_current(install_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = install_dir / f"{BACKUP_DIR_PREFIX}{timestamp}"
    backup_dir.mkdir(exist_ok=True)

    print(f"[INFO] Creando backup en {backup_dir} ...")
    for item in install_dir.iterdir():
        if item.name.startswith(BACKUP_DIR_PREFIX) or item == backup_dir:
            continue
        rel = item.relative_to(install_dir)
        if is_protected(rel):
            continue
        dest = backup_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    return backup_dir


def extract_update(zip_path: Path, extract_to: Path):
    print(f"[INFO] Extrayendo actualización...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)


def apply_update(extracted_dir: Path, install_dir: Path):
    """Copia el contenido extraído sobre install_dir, respetando PROTECTED_PATHS."""
    print(f"[INFO] Aplicando actualización sobre {install_dir} ...")

    # Si el zip tiene una única carpeta raíz (patrón típico de GitHub), entrar en ella
    entries = list(extracted_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        extracted_dir = entries[0]

    for root, dirs, files in os.walk(extracted_dir):
        root_path = Path(root)
        rel_root = root_path.relative_to(extracted_dir)

        # No descender en carpetas protegidas
        dirs[:] = [d for d in dirs if not is_protected(rel_root / d)]

        target_root = install_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)

        for filename in files:
            rel_file = rel_root / filename
            if is_protected(rel_file):
                continue
            shutil.copy2(root_path / filename, install_dir / rel_file)

    print("[INFO] Actualización aplicada.")


# --------------------------------------------------------------------------
# Control de la app (cerrar / reabrir)
# --------------------------------------------------------------------------

def stop_app(app_executable: str):
    if not app_executable:
        return
    print(f"[INFO] Cerrando {app_executable} si está en ejecución...")
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/IM", app_executable, "/F"],
                capture_output=True, check=False,
            )
        else:
            subprocess.run(["pkill", "-f", app_executable], capture_output=True, check=False)
    except Exception as e:
        print(f"[WARN] No se pudo cerrar la app automáticamente: {e}")


def start_app(install_dir: Path, app_executable: str):
    if not app_executable:
        return
    exe_path = install_dir / app_executable
    if not exe_path.exists():
        print(f"[WARN] No se encontró {exe_path}, no se relanza la app.")
        return
    print(f"[INFO] Reabriendo {exe_path} ...")
    if os.name == "nt":
        os.startfile(str(exe_path))  # noqa: S606 (uso intencional en Windows)
    else:
        subprocess.Popen([str(exe_path)])


# --------------------------------------------------------------------------
# Flujo principal
# --------------------------------------------------------------------------

STATUS_FILENAME = "update_status.json"


def write_status_file(install_dir: Path, needs_update: bool, local_version: str,
                       remote_version: str = "", error: str = ""):
    """
    Escribe un archivo de estado que el backend (Flask) puede leer y
    exponer al frontend, para mostrarle un aviso al usuario en el navegador.
    """
    status = {
        "update_available": needs_update,
        "current_version": local_version,
        "latest_version": remote_version,
        "error": error,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    status_path = install_dir / STATUS_FILENAME
    try:
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[WARN] No se pudo escribir {STATUS_FILENAME}: {e}")


def check_for_update(cfg: dict, install_dir: Path):
    local_version = get_local_version(install_dir)
    try:
        release = get_latest_release(cfg)
    except SystemExit as e:
        # No tirar la app abajo por un chequeo fallido (sin internet, token
        # vencido, etc.) — solo dejarlo registrado en el status file.
        write_status_file(install_dir, needs_update=False, local_version=local_version,
                           error=str(e))
        raise

    remote_version = release["tag_name"]

    print(f"[INFO] Versión local: {local_version}")
    print(f"[INFO] Última versión en GitHub: {remote_version}")

    needs_update = parse_version(remote_version) > parse_version(local_version)
    write_status_file(install_dir, needs_update, local_version, remote_version)
    return needs_update, release, local_version, remote_version


def run_update(cfg: dict, release: dict):
    install_dir = Path(cfg["install_dir"])
    app_executable = cfg.get("app_executable", "")
    found = find_update_asset(release, app_executable)
    asset, mode = found["asset"], found["mode"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        downloaded_path = tmp_path / asset["name"]
        download_asset(asset, cfg["github_token"], downloaded_path)

        stop_app(app_executable)

        if mode == "exe":
            # Reemplazo directo del ejecutable onefile.
            if not app_executable:
                raise SystemExit(
                    "[ERROR] Falta 'app_executable' en la config para reemplazar el .exe."
                )
            backup_exe(install_dir, app_executable)
            replace_exe(install_dir, app_executable, downloaded_path)
            cleanup_old_backups(install_dir, app_executable)
        else:
            # Modo carpeta completa (zip con estructura de archivos).
            extract_dir = tmp_path / "extracted"
            extract_dir.mkdir()
            extract_update(downloaded_path, extract_dir)
            backup_current(install_dir)
            apply_update(extract_dir, install_dir)

        set_local_version(install_dir, release["tag_name"])
        start_app(install_dir, app_executable)

    print("[OK] Actualización completada con éxito.")


def main():
    parser = argparse.ArgumentParser(description="Updater vía GitHub Releases")
    parser.add_argument(
        "--check", action="store_true",
        help="Solo verifica si hay una actualización disponible, sin aplicarla.",
    )
    args = parser.parse_args()

    cfg = load_config()
    install_dir = Path(cfg["install_dir"])

    try:
        needs_update, release, local_v, remote_v = check_for_update(cfg, install_dir)
    except SystemExit:
        if args.check:
            # Modo --check corre en segundo plano al arrancar la app: no
            # queremos que un error de red/token lo tire con código de
            # error ruidoso. Ya quedó registrado en update_status.json.
            print("[WARN] No se pudo chequear actualizaciones (ver update_status.json).")
            return
        raise

    if not needs_update:
        print("[OK] Ya tenés la última versión instalada.")
        return

    print(f"[INFO] Hay una actualización disponible: {local_v} -> {remote_v}")

    if args.check:
        print("[INFO] Modo --check: no se aplica la actualización.")
        return

    run_update(cfg, release)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Fallo inesperado durante la actualización: {e}")
        sys.exit(1)