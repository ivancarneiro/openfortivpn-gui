#!/bin/bash
set -e

APP_NAME="openfortivpn-gui"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_PATH="$APP_DIR/assets/openfortivpn_isologo.png"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"

echo "=== Instalador de OpenFortiVPN GUI v1.2 ==="

# 1. Verificar dependencias del sistema
echo "[*] Verificando openfortivpn..."
if ! command -v openfortivpn &> /dev/null; then
    echo "openfortivpn no encontrado. Intentando instalar..."
    if [ -x "$(command -v apt)" ]; then
        sudo apt update && sudo apt install -y openfortivpn
    else
        echo "Error: No se puede instalar openfortivpn automáticamente. Por favor instálelo manualmente."
        exit 1
    fi
else
    echo "openfortivpn ya está instalado."
fi

# 2. Configurar entorno Python
echo "[*] Configurando entorno virtual Python..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

# 3. Crear lanzador de escritorio
echo "[*] Creando lanzador de escritorio..."
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=OpenFortiVPN GUI
Comment=Cliente Gráfico para OpenFortiVPN
Exec=$APP_DIR/.venv/bin/python $APP_DIR/src/main.py
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Network;
EOF

chmod +x "$DESKTOP_FILE"
echo "Lanzador creado en: $DESKTOP_FILE"

echo ""
echo "=== Instalación Completa ==="
echo "Puede iniciar la aplicación desde su menú de aplicaciones o ejecutando:"
echo "$APP_DIR/.venv/bin/python src/main.py"
