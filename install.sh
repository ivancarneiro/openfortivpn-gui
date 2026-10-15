#!/bin/bash
set -e

APP_NAME="vpn-gna"
OLD_APP_NAME="openfortivpn-gui"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_PATH="$APP_DIR/assets/vpn_gna_icon.png"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"

echo "=== Instalador VPN GNA (Dual SSL / IPSec) ==="

# 1. Verificar dependencias del sistema (openfortivpn y strongswan/charon)
PACKAGES_TO_INSTALL=""
if ! command -v openfortivpn &> /dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL openfortivpn"
fi
if ! command -v swanctl &> /dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL strongswan strongswan-swanctl"
fi

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "[*] Instalando dependencias del sistema necesarias:$PACKAGES_TO_INSTALL (requiere sudo)..."
    sudo apt update && sudo apt install -y $PACKAGES_TO_INSTALL
fi

# 2. Verificar e instalar uv automáticamente
if ! command -v uv &> /dev/null; then
    echo "[*] 'uv' no encontrado. Instalando automáticamente..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Cargar uv en la sesión actual del script
    source $HOME/.cargo/env 2>/dev/null || true
fi

# 3. Crear entorno y dependencias con uv
echo "[*] Configurando entorno de Python optimizado..."
uv venv --quiet
source .venv/bin/activate
uv pip install -r requirements.txt --quiet

# 4. Crear lanzador de escritorio
echo "[*] Creando lanzador $APP_NAME.desktop..."
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=VPN GNA
Comment=Cliente Gráfico Dual SSL e IPSec (Gendarmería Nacional Argentina)
Exec=$APP_DIR/.venv/bin/python $APP_DIR/src/main.py
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Network;VPN;Security;
EOF

chmod +x "$DESKTOP_FILE"

# Limpiar lanzador anterior si existiese
rm -f "$HOME/.local/share/applications/$OLD_APP_NAME.desktop"

chmod +x update.sh configure_permissions.sh 2>/dev/null || true

echo ""
echo "=== Instalación Completa ==="
echo "Lanzador registrado como 'VPN GNA' en el menú de aplicaciones."
echo "Para habilitar conexiones VPN sin solicitud reiterada de contraseña sudo,"
echo "ejecute: sudo ./configure_permissions.sh"
