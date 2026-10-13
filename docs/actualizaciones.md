# Sistema de actualizaciones

La app se actualiza mediante **GitHub Releases**. El código vive en este repo, y los releases se publican en otro repo, también **privado**, que solo contiene binarios (el "repo de releases").

¿Por qué dos repos? Para descargar de un repo privado, el updater necesita un token en la máquina del cliente, y cualquiera con acceso a esa máquina podría extraerlo. GitHub no permite limitar un token a "solo releases": si los releases estuvieran en este repo, ese token también podría leer todo el código. Con un repo aparte, el token solo alcanza binarios que el cliente ya tiene instalados.

## Cómo funciona (resumen técnico)

1. Al abrir la app, `launcher.py` lanza `updater.exe --check` en segundo plano, sin bloquear el arranque.
2. `updater.exe --check`:
   - Lee `version.json` (versión instalada localmente).
   - Consulta `GET /repos/<owner>/<repo>/releases/latest` del repo de releases con el token de solo lectura de `updater_config.json`.
   - Compara la versión local contra el `tag_name` del último release.
   - Escribe el resultado en `update_status.json`, en la carpeta de instalación. No descarga nada en este modo.
3. El backend expone ese archivo en `GET /api/update/status` (`backend/app/routes/update.py`).
4. El frontend (`frontend/js/update-banner.js`) consulta ese endpoint al cargar la página y cada 5 minutos, y muestra un banner si `update_available` es `true`.
5. El banner le pide al usuario que cierre y vuelva a abrir la app. **Al reabrirla**, `launcher.py` ve que `update_status.json` indica una versión nueva, borra ese archivo, lanza `updater.exe` (sin `--check`) y se cierra. El updater descarga `GestionDeLocal.exe` del release, hace backup del actual (`GestionDeLocal_backup_<fecha>.exe`, conserva los últimos 3), lo reemplaza, actualiza `version.json` y vuelve a abrir la app.

Si la actualización falla, el próximo arranque es normal (el status ya se borró) y el `--check` vuelve a avisar.

### ¿Por qué no se actualiza sin reabrir?

`GestionDeLocal.exe` es un ejecutable *onefile*: mientras el proceso está corriendo, Windows no permite sobreescribir ese archivo. Por eso el reemplazo ocurre cuando la app no está corriendo.

### Modos de actualización que soporta `updater.py`

| Modo | Cuándo se usa | Qué hace |
|---|---|---|
| **exe** (el que usa este proyecto) | El release tiene un asset llamado **exactamente** `GestionDeLocal.exe` | Backup del exe actual y reemplazo directo |
| **zip** (fallback) | El release no tiene ese `.exe` pero sí un `.zip` | Descomprime y copia el contenido sobre la carpeta de instalación, respetando archivos protegidos (`stock_local.db`, `.env`, etc.) |

El updater **no** toma "cualquier `.exe`": el release también trae el instalador, que no debe reemplazar a la app.

## Cómo publicar una nueva versión

1. **Actualizar el código** y probarlo en local (ver [`desarrollo.md`](./desarrollo.md)).
2. **Actualizar `version.json`** con el número de versión nuevo (ej: `1.2.0`) y commitearlo.
3. **Crear y pushear el tag** `v1.2.0` (tiene que coincidir con `version.json`, con la `v` adelante):
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
4. El workflow `build-windows.yml` compila todo y publica el release en el repo de releases con dos assets: `GestionDeLocal.exe` (para el updater) y `GestionDeLocal_Setup_1.2.0.exe` (para instalaciones nuevas).
5. **Verificar**: en una instalación existente, abrir la app, esperar el banner, cerrarla y volver a abrirla; tiene que quedar en la versión nueva.

`updater.py` solo consulta el último release *publicado* (no borradores ni pre-releases).

## Configuración necesaria (una sola vez)

- Repo **privado** de releases creado **con al menos un commit** (por ejemplo, un README). Si está vacío, GitHub no puede crear el tag del release y la publicación falla con "Repository is empty".
- Una variable de repositorio (Settings → Secrets and variables → Actions → **Variables**) `RELEASES_REPO` con el nombre del repo de releases en formato `owner/repo`. El workflow la usa para publicar y la escribe en `updater_config.json`.
- Dos secrets en este repo, ambos fine-grained PAT con acceso **solo** al repo de releases:

| Secret | Permiso | Dónde termina |
|---|---|---|
| `RELEASES_REPO_TOKEN` | `Contents: read and write` | Solo en GitHub Actions (publica los releases) |
| `RELEASES_READ_TOKEN` | `Contents: read-only` | Dentro del instalador, en `updater_config.json` junto a `updater.exe` |

**Nunca** darle a `RELEASES_READ_TOKEN` acceso al repo de código: ese token lo puede extraer cualquiera que tenga el instalador.

Los clientes no configuran nada. El instalador también borra la variable de entorno `GITHUB_TOKEN` que dejaban las versiones anteriores, y el updater la ignora.

**Vencimiento del token de lectura:** cuando venza (o si hay que rotarlo), el updater de los clientes deja de poder chequear. Hay que actualizar el secret y que el cliente instale a mano el instalador nuevo. Conviene crearlo con el vencimiento más largo posible y anotar la fecha.

`repo_name` no tiene valor por defecto: sale de `updater_config.json` (lo genera el workflow desde `RELEASES_REPO`). Los demás valores por defecto (`repo_owner`, `app_executable`) están en `installer/updater/updater.py`. Todo se puede sobreescribir con las variables `REPO_OWNER`, `REPO_NAME`, `UPDATER_GITHUB_TOKEN` o con `updater_config.json`.

## Probar el updater manualmente

```bash
cd installer/updater
REPO_NAME="<repo-de-releases>" UPDATER_GITHUB_TOKEN="github_pat_..." python updater.py --check
cat update_status.json
```

Si `update_status.json` muestra `"update_available": true` con la versión esperada, el release está bien armado.
