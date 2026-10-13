# Instalación

Esta guía es para instalar la aplicación en la PC donde se va a usar (punto de venta, depósito, oficina, etc.).

## Requisitos

- Windows 10 o superior (64 bits).
- Conexión a internet para las actualizaciones automáticas y los respaldos. El uso diario de la app **no** requiere internet: todo funciona en local, y lo que no se pudo respaldar se sube la próxima vez que haya conexión.
- No hace falta tener Python instalado. El instalador incluye todo lo necesario.

## Cómo conseguir el instalador

El instalador (`GestionDeLocal_Setup_<version>.exe`) está en el repositorio privado de releases. El usuario final no tiene acceso: hay que descargarlo y hacérselo llegar (Drive, WhatsApp, pendrive, etc.).

Solo hace falta para la **primera instalación**. Después la app se actualiza sola.

## Pasos

1. **Ejecutar el instalador**: doble clic en `GestionDeLocal_Setup_<version>.exe`. Si Windows muestra "Windows protegió su PC", hacer clic en *Más información* → *Ejecutar de todas formas*.
2. **Elegir carpeta de instalación**: se puede dejar la opción por defecto. No pide permisos de administrador.
3. **Finalizar la instalación**: se crean accesos directos en el Escritorio y en el Menú Inicio. Al terminar, el instalador ofrece abrir la app.

No hay que configurar nada: lo necesario para las actualizaciones y los respaldos ya viene incluido.

## Uso diario

Al abrir la app se muestra una ventana con tres botones:

- **Abrir en el navegador**: abre la aplicación en `http://127.0.0.1:5000/`.
- **Cerrar aplicación**: guarda un respaldo (si hubo cambios) y cierra todo. Conviene cerrar siempre con este botón.
- **Sobre el autor**.

Mientras la ventana esté abierta, la app funciona. Si se cierra la ventana, el navegador deja de mostrar datos.

## Dónde quedan los datos

La base de datos está en `%APPDATA%\GestionDeLocal\stock_local.db` (se puede pegar esa ruta en la barra del Explorador). Desinstalar o actualizar la app **no** la borra.

## Avisos de actualización

Cada vez que se abre la app, se verifica en segundo plano si hay una versión nueva disponible. Si la hay, aparece un cartel arriba de la pantalla:

> Hay una nueva versión disponible (v1.x.x). Cerrá y volvé a abrir la app para actualizar.

Al cerrar y volver a abrir la aplicación, la actualización se aplica sola: la ventana desaparece unos segundos y la app se vuelve a abrir en la versión nueva.

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| El navegador muestra un error | El puerto 5000 está ocupado por otra aplicación | Cerrar la otra aplicación y volver a abrir GestionDeLocal |
| El banner de actualización nunca aparece | No hay internet, o el token de lectura del instalador venció | Revisar la conexión; si persiste, instalar a mano el instalador de la última versión |
| El respaldo manual da error | No hay internet, o falta la configuración de Supabase | Revisar la conexión; ver [`respaldos.md`](./respaldos.md) |

Para detalles técnicos, ver [`actualizaciones.md`](./actualizaciones.md) y [`respaldos.md`](./respaldos.md).
