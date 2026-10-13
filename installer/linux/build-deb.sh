#!/bin/bash

set -e

APP_NAME="GestionDeLocal"
VERSION=$(python3 -c "import json; print(json.load(open('version.json'))['version'])")

BUILD_DIR="/tmp/gestiondelocal-build"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller"
DEB_DIR="$BUILD_DIR/${APP_NAME}_${VERSION}_amd64"
OUTPUT="$BUILD_DIR/${APP_NAME}-${VERSION}.deb"

ENV_FILE="$BUILD_DIR/.env"

rm -rf "$BUILD_DIR"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/opt/$APP_NAME"
mkdir -p "$DEB_DIR/usr/share/applications"

echo "Compilando $APP_NAME para Linux..."

# NOTA: el punto de entrada pasó de backend/wsgi.py (consola, pensado
# para desarrollo) a launcher.py en la raíz del repo (ventana gráfica
# con botones para abrir/cerrar la app). Como launcher.py ya está en la
# raíz, las rutas de --add-data ("frontend:frontend", "schema.sql:.")
# no cambiaron porque este script ya se corre con $(pwd) apuntando a la
# raíz del repo.
#
# --paths backend: launcher.py hace `from app.main import create_app`,
# y `app` vive en backend/app. PyInstaller analiza los imports desde
# donde se corre este script (raíz del repo), no desde el sys.path que
# se arma en tiempo de ejecución dentro de launcher.py, así que sin este
# flag no encuentra el paquete `app` y el binario final falla con
# "ModuleNotFoundError: No module named 'app'".
#
# launcher.py usa tkinter, que en Ubuntu NO viene junto con el Python
# base: hace falta el paquete de sistema "python3-tk" instalado ANTES
# de correr pyinstaller (agregarlo en build-linux.yml, junto al paso
# donde se instala dpkg), si no la compilación falla o el binario final
# no puede abrir la ventana.
pyinstaller \
    --onefile \
    --name "$APP_NAME" \
    --distpath "$PYINSTALLER_DIR/dist" \
    --workpath "$PYINSTALLER_DIR/build" \
    --specpath "$PYINSTALLER_DIR" \
    --paths backend \
    --add-data "$(pwd)/frontend:frontend" \
    --add-data "$(pwd)/schema.sql:." \
    launcher.py

echo "Copiando archivos..."

cp "$PYINSTALLER_DIR/dist/$APP_NAME" \
   "$DEB_DIR/opt/$APP_NAME/$APP_NAME"

cp "version.json" \
   "$DEB_DIR/opt/$APP_NAME/version.json"

cp "installer/linux/$APP_NAME.desktop" \
   "$DEB_DIR/usr/share/applications/$APP_NAME.desktop"

cp "installer/linux/$APP_NAME.png" \
   "$DEB_DIR/opt/$APP_NAME/$APP_NAME.png"

chmod 755 "$DEB_DIR/opt/$APP_NAME/$APP_NAME"

# Crear configuración de Supabase
if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_KEY:-}" ]; then
    cat > "$ENV_FILE" <<EOF
SUPABASE_URL=$SUPABASE_URL
SUPABASE_KEY=$SUPABASE_KEY
EOF

    cp "$ENV_FILE" "$DEB_DIR/opt/$APP_NAME/.env"
    chmod 644 "$DEB_DIR/opt/$APP_NAME/.env"

    echo "Configuración de Supabase incluida."
else
    echo "ERROR: faltan SUPABASE_URL o SUPABASE_KEY."
    exit 1
fi

cat > "$DEB_DIR/DEBIAN/control" <<EOF
Package: gestiondelocal
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Brian Luporini
Description: Gestión de Local
 Aplicación de gestión de stock, ventas y caja.
EOF

dpkg-deb --build "$DEB_DIR" "$OUTPUT"

echo ""
echo "========================================"
echo "Paquete generado:"
echo "$OUTPUT"
echo "========================================"