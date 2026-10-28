"""
Respaldos a Supabase: dónde se sube cada respaldo y qué conserva la
limpieza. Sin red: el cliente de Supabase se reemplaza por uno falso.
"""

import os
import sys
from datetime import date, timedelta

import pytest

import app.supabase_backup as respaldo

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import limpiar_backups  # noqa: E402


class StorageFalso:
    """Imita supabase.storage.from_(bucket): guarda rutas en memoria."""

    def __init__(self, rutas=()):
        self.rutas = set(rutas)
        self.borradas = []

    def upload(self, ruta, archivo, opciones):
        self.rutas.add(ruta)

    def list(self, carpeta, opciones):
        prefijo = f"{carpeta}/" if carpeta else ""
        nombres = set()
        for ruta in self.rutas:
            if not ruta.startswith(prefijo):
                continue
            resto = ruta[len(prefijo):]
            # Las subcarpetas aparecen como una entrada con su nombre.
            nombres.add(resto.split("/")[0])
        pagina = sorted(nombres)[opciones["offset"]:opciones["offset"] + opciones["limit"]]
        return [{"name": n} for n in pagina]

    def remove(self, rutas):
        self.borradas += rutas
        self.rutas -= set(rutas)


class ClienteFalso:
    def __init__(self, storage):
        self.storage = self
        self._storage = storage

    def from_(self, bucket):
        assert bucket == "backups"
        return self._storage


# ---------- Subida ----------

@pytest.fixture
def storage(client, monkeypatch):
    falso = StorageFalso()
    monkeypatch.setattr(respaldo, "_get_supabase", lambda: ClienteFalso(falso))
    return falso


def test_en_desarrollo_el_respaldo_va_a_la_carpeta_desarrollo(client, storage):
    res = client.post("/api/backup/supabase")

    assert res.status_code == 200
    (ruta,) = storage.rutas
    assert ruta.startswith("desarrollo/backup-") and ruta.endswith(".db.gz")
    assert res.get_json()["archivo"] == ruta


def test_en_la_app_compilada_el_respaldo_va_a_la_carpeta_clienta(client, storage, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    resultado = respaldo.hacer_backup_ahora()

    assert resultado["ok"]
    (ruta,) = storage.rutas
    assert ruta.startswith("clienta/backup-") and ruta.endswith(".db.gz")


# ---------- Limpieza ----------

def _nombre(dias_atras, hora="120000"):
    return f"backup-{(date.today() - timedelta(days=dias_atras)).isoformat()}_{hora}.db.gz"


def _correr_limpieza(monkeypatch, storage, *args):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "x")
    monkeypatch.setattr(limpiar_backups, "create_client", lambda url, key: ClienteFalso(storage))
    monkeypatch.setattr(sys, "argv", ["limpiar_backups.py", *args])
    limpiar_backups.main()


def test_retencion_de_la_clienta_en_su_carpeta(monkeypatch):
    recientes = [f"clienta/{_nombre(d)}" for d in range(0, 10)]
    # Dos del mismo mes viejo: se conserva solo el más nuevo.
    mes_viejo = [f"clienta/{_nombre(60, '090000')}", f"clienta/{_nombre(60, '180000')}"]
    anio_pasado = [f"clienta/{_nombre(500)}"]
    storage = StorageFalso([*recientes, *mes_viejo, *anio_pasado])

    _correr_limpieza(monkeypatch, storage)

    assert sorted(storage.borradas) == sorted([mes_viejo[0], *anio_pasado])
    assert all(r in storage.rutas for r in recientes)


def test_los_respaldos_de_desarrollo_no_afectan_a_los_de_la_clienta(monkeypatch):
    # Un respaldo de desarrollo más nuevo, del mismo día que el único de la
    # clienta de ese mes viejo: antes de separar en carpetas, el de
    # desarrollo era el "más nuevo del mes" y se borraba el de la clienta.
    clienta_vieja = f"clienta/{_nombre(60, '090000')}"
    recientes = [f"clienta/{_nombre(d)}" for d in range(0, 6)]
    desarrollo = [f"desarrollo/{_nombre(60, '230000')}"]
    storage = StorageFalso([clienta_vieja, *recientes, *desarrollo])

    _correr_limpieza(monkeypatch, storage)

    assert storage.borradas == []


def test_de_desarrollo_se_conservan_solo_los_ultimos(monkeypatch):
    clienta = [f"clienta/{_nombre(d)}" for d in range(0, 6)]
    desarrollo = [f"desarrollo/{_nombre(d)}" for d in range(0, 15)]
    storage = StorageFalso([*clienta, *desarrollo])

    _correr_limpieza(monkeypatch, storage)

    quedan = sorted(r for r in storage.rutas if r.startswith("desarrollo/"))
    assert quedan == sorted(desarrollo)[-limpiar_backups.DESARROLLO_A_CONSERVAR:]
    assert all(r in storage.rutas for r in clienta)


def test_la_raiz_vieja_no_se_toca(monkeypatch, capsys):
    # Respaldos de antes de las carpetas (mezclados): muchos y viejos, que
    # con la regla de la clienta se borrarían casi todos.
    raiz = [_nombre(d) for d in range(0, 400, 3)] + ["backup-2025-01-01.db.gz"]
    storage = StorageFalso([*raiz, *[f"clienta/{_nombre(d)}" for d in range(6)]])

    _correr_limpieza(monkeypatch, storage)

    assert storage.borradas == []
    assert f"En la raíz quedan {len(raiz)} respaldos viejos" in capsys.readouterr().out


def test_dry_run_no_borra_nada(monkeypatch):
    desarrollo = [f"desarrollo/{_nombre(d)}" for d in range(0, 15)]
    clienta = [f"clienta/{_nombre(d)}" for d in range(0, 6)] + [f"clienta/{_nombre(500)}"]
    storage = StorageFalso([*clienta, *desarrollo])

    _correr_limpieza(monkeypatch, storage, "--dry-run")

    assert storage.borradas == []
