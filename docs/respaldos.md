# Respaldos en Supabase

La app sube copias comprimidas de la base (`stock_local.db`) al bucket `backups` de Supabase.

## Cómo funciona

- **Automático:** al abrir y al cerrar la app (solo en el ejecutable, nunca en desarrollo), si la base cambió desde el último respaldo. Al cerrar espera como máximo 30 segundos; lo que no llegue a subirse (por ejemplo, sin internet) se sube en el próximo arranque.
- **Manual:** botón "Guardar respaldo" en Configuración.
- Cada respaldo tiene un nombre único: `backup-YYYY-MM-DD_HHMMSS.db.gz`. La copia se hace con la API de backup de SQLite, así que es consistente aunque la app esté escribiendo.
- El estado del último respaldo se guarda en `estado_backup.json`, junto a la base.

## Carpetas del bucket

```
backups/
├── clienta/       Respaldos de la app instalada en la PC de la clienta
├── desarrollo/    Respaldos hechos corriendo la app desde el código
└── (raíz)         Respaldos de versiones anteriores a las carpetas (mezclados)
```

- La carpeta se elige sola (`ruta_en_bucket()` en `backend/app/supabase_backup.py`, según `sys.frozen`): la app compilada sube a `clienta/` y `python backend/wsgi.py` / `python launcher.py` suben a `desarrollo/`. No hay que configurar nada.
- La separación evita que una prueba local se mezcle con los respaldos de la clienta o altere su retención: la regla conserva **el más nuevo de cada mes**, y si una prueba quedara como "el más nuevo" de un mes, se borraría el respaldo real de ese mes.
- La política del bucket permite subir a cualquier carpeta, así que no hubo que cambiar nada en Supabase.

### Ordenar la raíz vieja (una sola vez)

Hasta la versión 1.5.1 la app compilada subía a la raíz, y hasta antes de la separación también lo hacían las pruebas locales. La limpieza **ya no toca la raíz** (solo informa cuántos quedan), porque ahí no se puede distinguir automáticamente qué es de quién. Para ordenarla desde el panel de Supabase (Storage → `backups`):

- **Sin hora en el nombre** (`backup-2026-10-12.db.gz`): de versiones anteriores a la 1.3.0, que la clienta nunca tuvo → son de pruebas, se pueden borrar.
- **Anteriores al día en que la clienta instaló la app** → son de pruebas.
- **Tamaño:** los de la base de ejemplo del generador pesan ~1 MB; los de la clienta, que arrancó de cero, son más chicos al principio.
- Los que sean de la clienta se pueden **mover** a `clienta/` (opción *Move* del panel); los demás, borrar.

Cuando la clienta tenga instalada una versión con carpetas, la raíz deja de recibir respaldos.

## Seguridad: quién puede hacer qué

| Clave | Dónde está | Qué puede hacer en el bucket |
|---|---|---|
| `anon` (`SUPABASE_KEY`) | Embebida en `GestionDeLocal.exe` (y en el `.env` del `.deb`) | **Solo subir** archivos nuevos |
| `service_role` (`SUPABASE_SERVICE_KEY`) | Solo en el secret de GitHub Actions | Todo (la usa la limpieza) |

Cualquiera con el instalador puede extraer la clave anon. Por eso las políticas del bucket solo le permiten subir: no puede listar, descargar, sobrescribir ni borrar respaldos.

## Configuración en Supabase (una sola vez)

En el panel de Supabase → **SQL Editor**:

```sql
-- 1. El bucket tiene que ser privado.
update storage.buckets set public = false where id = 'backups';

-- 2. Ver las políticas actuales sobre los archivos.
select policyname, cmd, roles, qual, with_check
from pg_policies
where schemaname = 'storage' and tablename = 'objects';
```

Borrar todas las políticas que le den a `anon` (o a `public`) permisos de `SELECT`, `UPDATE`, `DELETE` o `ALL` sobre el bucket `backups`:

```sql
drop policy "<nombre de la politica>" on storage.objects;
```

Y crear la única que necesita la app:

```sql
create policy "La app solo sube respaldos"
on storage.objects for insert
to anon
with check (bucket_id = 'backups');
```

**Verificar:** con la app (o desde tu máquina con la clave anon), el botón "Guardar respaldo" tiene que funcionar. Si devuelve un error de permisos, falta la política de `insert`.

## Retención

La hace el workflow `.github/workflows/limpiar-backups.yml` todos los días, con `scripts/limpiar_backups.py`:

- **`clienta/`:**
  - Últimos 30 días: se conservan todos.
  - Hasta 12 meses atrás: el más nuevo de cada mes.
  - Lo anterior se borra.
  - Si quedarían menos de 5 respaldos, no borra nada.
- **`desarrollo/`:** se conservan los 10 más nuevos.
- **Raíz:** no se toca (ver "Ordenar la raíz vieja").

Para probarlo sin borrar nada: **Actions → Limpiar respaldos viejos → Run workflow** con "Solo mostrar qué se borraría" tildado (es el valor por defecto).

## Secrets necesarios en el repo de código

| Secret | Valor |
|---|---|
| `SUPABASE_URL` | URL del proyecto |
| `SUPABASE_KEY` | Clave **anon** (la que va en la app) |
| `SUPABASE_SERVICE_KEY` | Clave **service_role** (solo para la limpieza) |

## Restaurar un respaldo

La app no puede descargar respaldos (su clave solo sube), así que la restauración es en dos pasos:

1. **Descargar el respaldo:** panel de Supabase → **Storage** → `backups` → carpeta **`clienta/`** → descargar el `backup-....db.gz` elegido y hacérselo llegar a la clienta.
2. **Restaurarlo desde la app:** **Configuración → Restaurar desde archivo**, elegir el `.db.gz` (o un `.db` sin comprimir) y confirmar.

La app (`backend/app/restaurar.py`):

- Valida el archivo antes de tocar nada: que sea SQLite, que pase `PRAGMA integrity_check` y que tenga las tablas de la app. Si no, muestra el error y **la base actual queda intacta**.
- Guarda una copia de la base actual en `%APPDATA%\GestionDeLocal\restauraciones\antes_de_restaurar_<fecha>.db` (conserva las últimas 5).
- Reemplaza los datos con la API de backup de SQLite (funciona con la app abierta) y corre las migraciones, así un respaldo de una versión anterior queda al día.

**Para volver atrás** después de una restauración: restaurar el archivo `antes_de_restaurar_<fecha>.db` de esa carpeta, de la misma forma.
