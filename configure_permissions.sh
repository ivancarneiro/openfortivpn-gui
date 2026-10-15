#!/bin/bash
# Script para habilitar el uso sin contraseña en VPN-GNA (Dual SSL / IPSec)

if [ -n "$SUDO_USER" ]; then
    USER_NAME="$SUDO_USER"
else
    USER_NAME=$(whoami)
fi
SUDOERS_FILE="/etc/sudoers.d/vpn-gna"
LEGACY_SUDOERS_FILE="/etc/sudoers.d/openfortivpn-gui"

OPENFORTIVPN_BIN=$(command -v openfortivpn || echo "/usr/bin/openfortivpn")
KILLALL_BIN=$(command -v killall || echo "/usr/bin/killall")
RESOLVECTL_BIN=$(command -v resolvectl || echo "/usr/bin/resolvectl")
SWANCTL_BIN=$(command -v swanctl || echo "/usr/sbin/swanctl")

echo "=== Configuración de Sudo Sin Contraseña para VPN-GNA ==="
echo "Usuario actual: $USER_NAME"
echo "Archivo destino: $SUDOERS_FILE"
echo ""
echo "Este script creará una regla en sudoers que permite ejecutar:"
echo "1. $OPENFORTIVPN_BIN (Motor SSL)"
echo "2. $KILLALL_BIN openfortivpn"
echo "3. $RESOLVECTL_BIN (Split-DNS)"
echo "4. $SWANCTL_BIN (Motor IPSec strongSwan)"
echo "Sin solicitar contraseña."
echo ""
echo "Se requerirá su contraseña de sudo una última vez para aplicar los cambios."
echo ""
if [[ "$1" == "-y" || "$1" == "--yes" ]]; then
    confirm="s"
else
    read -p "¿Desea continuar? (s/n): " confirm
fi

if [[ $confirm != "s" && $confirm != "S" ]]; then
    echo "Operación cancelada."
    exit 1
fi

# Definir la regla con todos los binarios necesarios para modo dual
RULE="$USER_NAME ALL=(ALL) NOPASSWD: $OPENFORTIVPN_BIN, $KILLALL_BIN openfortivpn, $RESOLVECTL_BIN, $SWANCTL_BIN"

# Crear archivo temporal
TMP_FILE=$(mktemp)
echo "$RULE" > "$TMP_FILE"

# Validar sintaxis con visudo
if visudo -cf "$TMP_FILE"; then
    echo "Sintaxis verificada. Aplicando..."
    sudo install -m 0440 "$TMP_FILE" "$SUDOERS_FILE"
    if [ -f "$LEGACY_SUDOERS_FILE" ]; then
        echo "Limpiando regla heredada en $LEGACY_SUDOERS_FILE..."
        sudo rm -f "$LEGACY_SUDOERS_FILE" 2>/dev/null || true
    fi
    echo "Regla sudoers aplicada con éxito."
else
    echo "Error: La regla generada no es válida. No se aplicaron cambios."
    rm "$TMP_FILE"
    exit 1
fi
rm "$TMP_FILE"

# Configuración de perfil AppArmor para strongSwan (swanctl)
if command -v apparmor_parser >/dev/null 2>&1 && [ -d /etc/apparmor.d ]; then
    APPARMOR_LOCAL="/etc/apparmor.d/local/usr.sbin.swanctl"
    APPARMOR_PROFILE="/etc/apparmor.d/usr.sbin.swanctl"

    if [ -d "/etc/apparmor.d/local" ]; then
        echo "Configurando permisos de AppArmor para swanctl en $APPARMOR_LOCAL..."
        APPARMOR_TMP=$(mktemp)
        cat << 'EOF' > "$APPARMOR_TMP"
# Reglas añadidas por VPN-GNA para permitir la lectura de configuraciones efímeras en RAM (tmpfs)
capability dac_read_search,
/run/user/*/** r,
/run/vpn-gna/** r,
/tmp/** r,
EOF
        sudo install -m 0644 "$APPARMOR_TMP" "$APPARMOR_LOCAL"
        rm -f "$APPARMOR_TMP"

        if [ -f "$APPARMOR_PROFILE" ]; then
            echo "Recargando perfil de AppArmor de swanctl..."
            sudo apparmor_parser -r "$APPARMOR_PROFILE" 2>/dev/null || true
        fi
        echo "AppArmor para swanctl configurado correctamente."
    fi
fi

echo ""
echo "¡Listo! Ahora puede usar VPN-GNA (tanto SSL como IPSec) sin contraseña ni bloqueos de AppArmor."
