# Gestión de Local · Alba Ropa Íntima

[![Tests](https://github.com/bluporini/gestion-de-local/actions/workflows/tests.yml/badge.svg)](https://github.com/bluporini/gestion-de-local/actions/workflows/tests.yml)

Sistema de gestión desarrollado para **Alba Ropa Íntima**, un comercio de indumentaria que lo usa en su día a día: **stock por variantes, ventas, cambios y devoluciones, caja diaria y respaldos automáticos en la nube**. Es una aplicación de escritorio que se instala en Windows y se actualiza sola.

Este repositorio es la versión pública para portfolio (publicada con autorización del cliente). La demo usa **datos ficticios**, no información real del comercio.

**[▶ Probar la demo online](https://gestiondelocal-bluporini.onrender.com)** · datos de ejemplo, podés usarla libremente (la primera carga puede tardar unos segundos si el servidor estaba dormido).

![Dashboard](docs/capturas/dashboard.png)
![Nueva venta](docs/capturas/venta.png)

---

## Qué hace

- **Productos con variantes** (talle, color, pack), cada una con su stock, costo, precio y margen. Códigos generados automáticamente.
- **Ventas** con carrito, efectivo (calcula el vuelto) o tarjeta, y códigos de venta por día.
- **Cambios y devoluciones parciales**: devolver una prenda y llevarse otra, con la diferencia de dinero y el impacto en stock y ganancia. Editables y reversibles.
- **Dashboard y caja diaria**: ingresos y ganancia del día, semana y mes, stock bajo, y un resumen de caja listo para enviar por WhatsApp o exportar a PDF.
- **Respaldos automáticos** en Supabase al abrir y cerrar la app.
- **Actualizaciones automáticas**: avisa cuando hay versión nueva y se actualiza al reabrirla.

## Requerimientos del cliente

Los requerimientos se definieron en reuniones con el cliente a lo largo del desarrollo. Además de lo central, la **gestión de stock y de ventas**, surgieron necesidades propias de cómo trabaja el local:

- **Identidad visual:** una interfaz con **fondo rosa**, acorde a la imagen del comercio.
- **Resumen de caja para WhatsApp:** al cierre del día, la app arma un **texto con las ventas, los cambios y los totales por medio de pago**, listo para copiar y pegar en WhatsApp con un clic (también se puede exportar a PDF).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python, Flask, SQLite (sin ORM) |
| Frontend | HTML, CSS y JavaScript puro (ES modules, sin build) |
| Escritorio | Tkinter (ventana de control) + PyInstaller (ejecutable único) |
| Instalador | Inno Setup (Windows), `.deb` (Linux) |
| Nube | Supabase Storage (respaldos), GitHub Releases (actualizaciones) |
| CI/CD | GitHub Actions: tests, build del `.exe` e instalador, publicación de releases |
| Tests | pytest |

## Arquitectura

```mermaid
flowchart LR
    subgraph PC["PC del comercio"]
        L["launcher.py<br/>(ventana Tkinter)"] --> F["Flask<br/>API + frontend"]
        F --> DB[("SQLite<br/>%APPDATA%")]
        B["Navegador"] <--> F
        U["updater.exe"]
    end

    subgraph GH["GitHub"]
        CI["Actions<br/>tests → build → release"]
        R["Repo de releases<br/>(solo binarios)"]
    end

    S[("Supabase Storage<br/>respaldos")]

    CI -->|publica .exe| R
    U -->|token de solo lectura| R
    L -->|al abrir/cerrar:<br/>solo subida| S
    CI -->|limpieza diaria<br/>service_role| S
```

La app corre localmente: `launcher.py` levanta Flask en un hilo y el navegador se conecta a `127.0.0.1`. Funciona sin internet; los respaldos y las actualizaciones se hacen cuando hay conexión.

## Correr localmente

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements-dev.txt

python test/generar_db.py      # base de ejemplo (~2 años de ventas)
python backend/wsgi.py         # abre http://127.0.0.1:5000

python -m pytest -q            # tests
```

## Demo online

La demo web usa el mismo código, servido con gunicorn (`backend/demo.py`): genera la base de ejemplo con fecha de hoy al arrancar, muestra un cartel de demo y deshabilita los respaldos. Se despliega en Render con `render.yaml` (plan gratuito). El disco es efímero, así que los datos se reinician solos cuando el servidor se reinicia.

## Estructura

```text
backend/app/        API Flask (un blueprint por área), base de datos y respaldos
backend/tests/      Tests (pytest) sobre una SQLite temporal
backend/demo.py     Punto de entrada de la demo web
frontend/           Interfaz (HTML/CSS/JS sin build)
installer/          Instalador de Windows, .deb y updater
scripts/            Limpieza de respaldos (GitHub Actions)
launcher.py         Punto de entrada del ejecutable
schema.sql          Esquema + triggers
docs/               Instalación, desarrollo, actualizaciones y respaldos
```

## Cómo se desarrolló

Diseñé y desarrollé el backend del sistema, incluyendo el modelo de datos, la lógica de ventas, cambios y devoluciones, la gestión de caja y las operaciones de stock.

Para el frontend, trabajé con Claude Code como asistente de programación, utilizándolo para implementar la interfaz y realizar ajustes durante el desarrollo. También lo utilicé en la etapa final para reforzar el sistema de actualizaciones, los respaldos en Supabase, los tests automatizados y la integración continua (CI).

Las decisiones de arquitectura, la integración de los componentes y la revisión de los cambios quedaron a mi cargo.

---

Desarrollado por **Brian Luporini**
