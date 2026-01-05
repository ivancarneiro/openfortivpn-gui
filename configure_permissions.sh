#!/bin/bash
# Script para habilitar el uso de openfortivpn sin contraseña en openfortivpn-gui

USER_NAME=$(whoami)
SUDOERS_FILE="/etc/sudoers.d/openfortivpn-gui"

echo "=== Configuración de Sudo Sin Contraseña para OpenFortiVPN GUI ==="
echo "Usuario actual: $USER_NAME"
echo "Archivo destino: $SUDOERS_FILE"
echo ""
echo "Este script creará una regla en sudoers que permite ejecutar:"
echo "1. /usr/bin/openfortivpn"
echo "2. /usr/bin/killall openfortivpn"
echo "Sin solicitar contraseña."
echo ""
echo "Se requerirá su contraseña de sudo una última vez para aplicar los cambios."
echo ""
read -p "¿Desea continuar? (s/n): " confirm
if [[ $confirm != "s" && $confirm != "S" ]]; then
    echo "Operación cancelada."
    exit 1
fi

# Definir la regla
RULE="$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/openfortivpn, /usr/bin/killall openfortivpn"

# Crear archivo temporal
TMP_FILE=$(mktemp)
echo "$RULE" > "$TMP_FILE"

# Validar sintaxis
if visudo -cf "$TMP_FILE"; then
    echo "Sintaxis verificada. Aplicando..."
    sudo install -m 0440 "$TMP_FILE" "$SUDOERS_FILE"
    echo "¡Listo! Ahora puede usar openfortivpn-gui sin contraseña."
else
    echo "Error: La regla generada no es válida. No se aplicaron cambios."
fi

rm "$TMP_FILE"
