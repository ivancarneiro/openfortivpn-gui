# Technical Research: VPN-GNA Dual SSL / IPSec

**Feature**: `specs/001-dual-vpn-gna/spec.md`  
**Date**: 2026-10-14  

---

## 1. Integración y Ciclo de Vida de strongSwan (`swanctl`)

### Decisión
Utilizar la interfaz de línea de comandos de `swanctl` con archivos de configuración efímeros en RAM (`/run/user/<uid>/vpn-gna/swanctl_tmp_<id>.conf`, permisos `0600`).
1. **Carga**: `sudo -n /usr/sbin/swanctl --load-all --file <temp_path>`
2. **Limpieza inmediata**: Se elimina el archivo temporal de RAM inmediatamente después de haber sido cargado en el espacio de memoria de `charon-systemd`.
3. **Inicio del túnel**: `sudo -n /usr/sbin/swanctl --initiate -c <conn_name> --timeout 30`
4. **Desconexión**: `sudo -n /usr/sbin/swanctl --terminate -c <conn_name>` y `sudo -n /usr/sbin/swanctl --unload-conn -c <conn_name>`

### Justificación
- Cumple estrictamente con el **Principio I de la Constitución (Zero Plaintext Secrets)**: las credenciales nunca tocan el disco no volátil.
- Se integra de manera estándar con el demonio nativo `charon-systemd` (`strongswan.service`) activo en Ubuntu/Debian.
- Utiliza la regla de elevación de privilegios en `sudoers` (`/usr/sbin/swanctl`), manteniendo la aplicación en espacio de usuario (**Principio II**).

### Alternativas Consideradas
- **Archivos estáticos en `/etc/swanctl/conf.d/`**: Descartado por requerir permisos de escritura permanentes en `/etc/` y persistir secretos en disco.
- **Librería directa Python `vici` por socket UNIX (`/run/charon.vici`)**: Descartado por la preferencia del usuario por la automatización vía CLI `swanctl` con reglas de sudoers explícitas.

---

## 2. Autenticación IKEv2 EAP en FortiGate y 2FA/OTP

### Decisión
Implementar autenticación IKEv2 con EAP (`eap-mschapv2`) y concatenación automática del token de segundo factor (`contraseña + OTP`) en el campo de secreto EAP:
- Configuración generada en `swanctl.conf`:
  ```ini
  connections {
      vpn-gna-ipsec {
          remote_addrs = <gateway_host>
          vips = 0.0.0.0
          local {
              auth = eap-mschapv2
              eap_id = <username>
          }
          remote {
              auth = pubkey
              id = %any
          }
          children {
              net {
                  remote_ts = 0.0.0.0/0
                  updown = /usr/lib/strongswan/_updown iptables
              }
          }
      }
  }
  secrets {
      eap-<username> {
          id = <username>
          secret = "<password><otp>"
      }
  }
  ```

### Justificación
- Estándar de la arquitectura FortiOS Dialup IPSec con servidor RADIUS / FortiAuthenticator.
- La aplicación maneja la captura interactiva del OTP en un diálogo seguro en memoria sin persistencia en disco ni logs.

### Alternativas Consideradas
- **EAP-GTC interactivo**: No requerido por el concentrador de GNA.
- **Autenticación por Certificados PKI**: Descartado por el usuario, ya que los usuarios remotos usan credenciales de dominio + token OTP.

---

## 3. Monitoreo de Tráfico y Estadísticas de Sesión (RX / TX)

### Decisión
Extraer métricas de tráfico en tiempo real mediante sondeo asíncrono no bloqueante ejecutando periódicamente:
```bash
sudo -n /usr/sbin/swanctl --list-sas --raw
```
o analizando la salida estructurada de `swanctl --list-sas -c <conn_name>`.
- Campos extraídos: `bytes-in` (RX) y `bytes-out` (TX) de la asociación de seguridad secundaria (`CHILD_SA net`).
- Emisión periódica (cada 1s) a través de la señal Qt `traffic_stats_updated(rx, tx)`.

### Justificación
- No requiere crear interfaces XFRM dedicadas (`ipsec0`), evitando configurar dispositivos de red virtuales ni reglas adicionales de ruteo de kernel.
- Se desacopla perfectamente en el panel gráfico existente (`src/stats_panel.py`), el cual ya consume `rx_bytes` y `tx_bytes`.

### Alternativas Consideradas
- **Interfaz virtual XFRM (`ipsec0`) con lectura de `/sys/class/net/ipsec0/statistics`**: Añade complejidad de scripts updown y dependencias de kernel adicionales sin ventaja operativa apreciable.

---

## 4. Resolución de Nombres y Split-DNS

### Decisión
Reutilizar la orquestación de `resolvectl` para registrar los dominios institucionales (`gna`, `gna.gob.ar`, `gendarmeria.gob.ar`) asociados a la interfaz o túnel provisto por strongSwan (`/etc/resolv.conf` / `systemd-resolved`):
- Si strongSwan recibe atributos DNS en el Configuration Payload (CP), `charon` los instala mediante el plugin `resolve`.
- En caso complementario o perfiles con dominios split definidos, el backend invoca `sudo -n resolvectl domain` sin pedir contraseña.

---

## 5. Estrategia de Migración y Rebranding a VPN-GNA

### Decisión
1. **Directorio de Configuración**: Migrar `~/.config/ofvpn-gui/` a `~/.config/vpn-gna/`.
   - Si existe `~/.config/ofvpn-gui/profiles.json` y no existe `~/.config/vpn-gna/`, copiar y migrar el esquema agregando `"vpn_type": "ssl"` a los perfiles antiguos.
2. **Llavero del Sistema (Keyring)**:
   - Migrar entradas del servicio `openfortivpn-gui` al nuevo servicio `vpn-gna`.
3. **Lanzador de Escritorio**:
   - `~/.local/share/applications/vpn-gna.desktop` con `Name=VPN GNA`, `Exec=.../main.py`.
4. **Reglas de Sudoers**:
   - Archivo: `/etc/sudoers.d/vpn-gna`.
   - Binarios autorizados: `/usr/bin/openfortivpn`, `/usr/bin/killall openfortivpn`, `/usr/bin/resolvectl`, `/usr/sbin/swanctl`.
