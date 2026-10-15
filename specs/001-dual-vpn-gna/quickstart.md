# Quickstart & Validation Guide: VPN-GNA Dual SSL / IPSec

**Feature**: `specs/001-dual-vpn-gna/spec.md`  
**Date**: 2026-10-14  

---

## 1. Prerrequisitos del Entorno

1. **Paquetes instalados**:
   - `openfortivpn` (motor SSL)
   - `strongswan` y `strongswan-swanctl` (motor IPSec)
   - `systemd-resolved` con `resolvectl` (gestión de DNS)
2. **Permisos en sudoers**:
   Ejecutar `./configure_permissions.sh` para autorizar:
   - `/usr/bin/openfortivpn`
   - `/usr/bin/killall openfortivpn`
   - `/usr/bin/resolvectl`
   - `/usr/sbin/swanctl`
3. **Entorno Python**:
   - Python 3.8+ con dependencias de `requirements.txt` (PySide6, keyring, etc.).

---

## 2. Escenarios de Prueba de Validación Rápida

### Escenario 1: Migración Automática de OpenFortiVPN-GUI a VPN-GNA
- **Comando**: Iniciar la aplicación:
  ```bash
  .venv/bin/python src/main.py
  ```
- **Resultado esperado**:
  - Se crea automáticamente `~/.config/vpn-gna/`.
  - Los perfiles preexistentes en `~/.config/ofvpn-gui/profiles.json` se importan con tipo `ssl`.
  - La ventana principal exhibe el título "VPN GNA".
  - Las contraseñas en Keyring son accesibles bajo el nuevo espacio de nombres.

### Escenario 2: Creación de Perfil IPSec
1. Abrir diálogo de "Configuración de Perfiles".
2. Hacer clic en "Nuevo Perfil".
3. En el selector de tipo de VPN, elegir **IPSec (strongSwan)**.
4. Constatar que se oculta el campo de "Trusted Cert" de SSL y se muestran los campos de Gateway, Usuario y Split-DNS.
5. Asignar Gateway de prueba, usuario institucional y tildar "Doble Factor (2FA/OTP)".
6. Guardar perfil y verificar su persistencia en `~/.config/vpn-gna/profiles.json` validado contra [profile-schema.json](file:///home/ciex/openfortivpn-gui/specs/001-dual-vpn-gna/contracts/profile-schema.json).

### Escenario 3: Conexión y Monitoreo IPSec
1. Seleccionar el perfil IPSec en el combobox principal.
2. Hacer clic en "Conectar".
3. En el cuadro de diálogo emergente, ingresar el código OTP de 6 dígitos.
4. Verificar en el panel de logs:
   - Generación y carga de configuración efímera en `/run/user/<uid>/vpn-gna/`.
   - Invocación de `swanctl --initiate`.
   - Establecimiento de la SA (`IKE_SA established`, `CHILD_SA established`).
   - Estado pasa a `Conectado` en verde.
   - El temporizador inicia y el panel de estadísticas muestra RX/TX en tiempo real.
5. Hacer clic en "Desconectar" y verificar:
   - Invocación de `swanctl --terminate`.
   - Limpieza inmediata del estado.
   - Retorno a `Desconectado` en menos de 2 segundos.
