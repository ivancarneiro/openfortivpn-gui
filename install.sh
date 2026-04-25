#!/bin/bash
set -e

APP_NAME="openfortivpn-gui"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_PATH="$APP_DIR/assets/openfortivpn_isologo.png"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"

echo "=== Instalador OpenFortiVPN GUI (Autogestionado) ==="

# 1. Verificar openfortivpn
if ! command -v openfortivpn &> /dev/null; then
    echo "[*] Instalando openfortivpn (requiere sudo)..."
    sudo apt update && sudo apt install -y openfortivpn
fi

# 2. Verificar e instalar uv automáticamente
if ! command -v uv &> /dev/null; then
    echo "[*] 'uv' no encontrado. Instalando automáticamente..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Cargar uv en la sesión actual del script
    source $HOME/.cargo/env
fi

# 3. Crear entorno y dependencias con uv
echo "[*] Configurando entorno de Python optimizado..."
uv venv --quiet
source .venv/bin/activate
uv pip install -r requirements.txt --quiet

# 4. Crear lanzador de escritorio
echo "[*] Creando lanzador..."
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
chmod +x update.sh configure_permissions.sh 2>/dev/null || true

echo ""
echo "=== Instalación Completa ==="
echo "Ya puede iniciar la aplicación desde su menú de inicio."
