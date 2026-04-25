#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=== Actualizador OpenFortiVPN GUI (Autogestionado) ==="

# 1. Sincronizar código
if [ -d ".git" ]; then
    echo "[*] Descargando actualizaciones..."
    git pull
fi

# 2. Verificar e instalar uv si falta
if ! command -v uv &> /dev/null; then
    echo "[*] Instalando motor de paquetes 'uv'..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# 3. Sincronizar entorno virtual
echo "[*] Sincronizando dependencias..."
uv venv --quiet
source .venv/bin/activate
uv pip install -r requirements.txt --quiet

# 4. Asegurar permisos
chmod +x install.sh update.sh configure_permissions.sh 2>/dev/null || true

echo ""
echo "=== Aplicación Actualizada con Éxito ==="
