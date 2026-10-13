"""
limpiar_backups.py
==================
Retención de los respaldos del bucket "backups" de Supabase.

La app de la clienta solo puede SUBIR respaldos (su clave anon no puede
listar ni borrar), así que la limpieza se hace acá, desde GitHub Actions
(workflow limpiar-backups.yml), con la clave service_role guardada como
secret. Esa clave nunca va en la app ni en el instalador.

Política:
  - Últimos DIAS_COMPLETOS días: se conservan todos.
  - Hasta MESES_MENSUALES meses atrás: se conserva el más nuevo de cada mes.
  - Lo anterior se borra.
  - Nunca se borra nada si quedarían menos de MINIMO_A_CONSERVAR respaldos.

Uso:
  SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/limpiar_backups.py [--dry-run]
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

from supabase import create_client

BUCKET_NAME = "backups"
DIAS_COMPLETOS = 30
MESES_MENSUALES = 12
MINIMO_A_CONSERVAR = 5


def fecha_de(nombre: str):
    """Fecha de un respaldo a partir del nombre. Acepta el formato viejo
    (backup-YYYY-MM-DD.db.gz) y el nuevo (backup-YYYY-MM-DD_HHMMSS.db.gz).
    Devuelve None si el archivo no es un respaldo."""
    if not nombre.startswith("backup-") or not nombre.endswith(".db.gz"):
        return None
    try:
        return datetime.strptime(nombre[len("backup-"):len("backup-") + 10], "%Y-%m-%d").date()
    except ValueError:
        return None


def listar_respaldos(storage):
    nombres = []
    offset = 0
    while True:
        pagina = storage.list("", {"limit": 1000, "offset": offset,
                                   "sortBy": {"column": "name", "order": "asc"}})
        if not pagina:
            break
        nombres.extend(a["name"] for a in pagina if fecha_de(a.get("name", "")))
        offset += len(pagina)
    return nombres


def elegir_a_borrar(nombres, hoy: date):
    """Devuelve la lista de nombres a borrar según la política."""
    limite_completos = hoy - timedelta(days=DIAS_COMPLETOS)
    limite_mensuales = hoy - timedelta(days=MESES_MENSUALES * 31)

    # Orden descendente: el primero que aparece de cada mes es el más nuevo
    # (los nombres llevan fecha y hora, así que el orden alfabético sirve).
    conservar = set()
    meses_vistos = set()
    for nombre in sorted(nombres, reverse=True):
        fecha = fecha_de(nombre)
        if fecha >= limite_completos:
            conservar.add(nombre)
        elif fecha >= limite_mensuales:
            mes = (fecha.year, fecha.month)
            if mes not in meses_vistos:
                meses_vistos.add(mes)
                conservar.add(nombre)

    a_borrar = [n for n in nombres if n not in conservar]

    if len(nombres) - len(a_borrar) < MINIMO_A_CONSERVAR:
        print(f"[WARN] Quedarían menos de {MINIMO_A_CONSERVAR} respaldos; no se borra nada.")
        return []
    return a_borrar


def main():
    parser = argparse.ArgumentParser(description="Limpieza de respaldos viejos en Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra qué se borraría.")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        sys.exit("[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY.")

    storage = create_client(url, key).storage.from_(BUCKET_NAME)
    nombres = listar_respaldos(storage)
    a_borrar = elegir_a_borrar(nombres, date.today())

    print(f"[INFO] Respaldos: {len(nombres)}. A borrar: {len(a_borrar)}.")
    for nombre in a_borrar:
        print(f"  - {nombre}")

    if a_borrar and not args.dry_run:
        # De a tandas, para no armar requests enormes.
        for i in range(0, len(a_borrar), 100):
            storage.remove(a_borrar[i:i + 100])
        print("[OK] Limpieza completada.")


if __name__ == "__main__":
    main()
