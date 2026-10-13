# Respaldos en Supabase

La app sube copias comprimidas de la base (`stock_local.db`) al bucket `backups` de Supabase.

## Cómo funciona

- **Automático:** al abrir y al cerrar la app (solo en el ejecutable, nunca en desarrollo), si la base cambió desde el último respaldo. Al cerrar espera como máximo 30 segundos; lo que no llegue a subirse (por ejemplo, sin internet) se sube en el próximo arranque.
- **Manual:** botón "Guardar respaldo" en Configuración.
- Cada respaldo tiene un nombre único: `backup-YYYY-MM-DD_HHMMSS.db.gz`. La copia se hace con la API de backup de SQLite, así que es consistente aunque la app esté escribiendo.
- El estado del último respaldo se guarda en `estado_backup.json`, junto a la base.

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

- Últimos 30 días: se conservan todos.
- Hasta 12 meses atrás: el más nuevo de cada mes.
- Lo anterior se borra.
- Si quedarían menos de 5 respaldos, no borra nada.

Para probarlo sin borrar nada: **Actions → Limpiar respaldos viejos → Run workflow** con "Solo mostrar qué se borraría" tildado (es el valor por defecto).

## Secrets necesarios en el repo de código

| Secret | Valor |
|---|---|
| `SUPABASE_URL` | URL del proyecto |
| `SUPABASE_KEY` | Clave **anon** (la que va en la app) |
| `SUPABASE_SERVICE_KEY` | Clave **service_role** (solo para la limpieza) |

## Restaurar un respaldo

Desde el panel de Supabase → **Storage** → `backups`: descargar el archivo, descomprimirlo (`gunzip backup-....db.gz`) y reemplazar `stock_local.db` en `%APPDATA%\GestionDeLocal\` con la app cerrada. Conviene renombrar la base actual en vez de borrarla, por si hace falta volver atrás.
