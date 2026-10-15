# Contrato de Plantilla de Configuración Efímera: `swanctl.conf`

**Feature**: `specs/001-dual-vpn-gna/spec.md`  
**Date**: 2026-10-14  

---

## 1. Plantilla de Generación en RAM (`/run/user/<uid>/vpn-gna/`)

Cada intento de conexión IPSec genera un archivo temporal único con permisos `0600` (`-rw-------`) propiedad del usuario en el sistema de archivos de memoria (tmpfs):

```ini
connections {
    {connection_id} {
        version = 2
        remote_addrs = {gateway_host}
        vips = 0.0.0.0
        proposals = aes256gcm16-prfsha384-ecp384,aes256-sha256-modp2048,default
        
        local {
            auth = eap-mschapv2
            eap_id = "{username}"
        }
        
        remote {
            auth = pubkey
            id = %any
        }
        
        children {
            {child_name} {
                remote_ts = 0.0.0.0/0
                esp_proposals = aes256gcm16,aes256-sha256,default
                dpd_action = clear
                close_action = none
            }
        }
    }
}

secrets {
    eap-{connection_id} {
        id = "{username}"
        secret = "{full_secret}"
    }
}
```

---

## 2. Parámetros de Sustitución

| Variable | Tipo | Descripción | Regla de Sanitización |
| :--- | :--- | :--- | :--- |
| `{connection_id}` | String | Identificador alfanumérico seguro (ej. `vpngna_7d1aa030`) | Sin espacios ni caracteres especiales |
| `{gateway_host}` | String | Dirección IP o FQDN del concentrador Fortinet | Validado sintácticamente |
| `{username}` | String | Identidad del usuario para EAP | Escape de comillas dobles si las hubiera |
| `{full_secret}` | String | Contraseña combinada (`password + otp` si OTP activo) | Escape estricto de comillas y barras invertidas |
| `{child_name}` | String | Identificador del SA secundario (ej. `net`) | Alfanumérico simple |

---

## 3. Protocolo de Ejecución y Borrado Seguro

1. **Creación**: Se genera en memoria y se escribe en `/run/user/<uid>/vpn-gna/swanctl_<id>.conf`.
2. **Carga**: Se invoca `sudo -n /usr/sbin/swanctl --load-all --file <path>`.
3. **Borrado Inmediato**: Se ejecuta `os.remove(<path>)` inmediatamente después del comando anterior, asegurando que el secreto no permanezca en disco ni un instante después de estar en memoria del demonio.
4. **Activación**: Se invoca `sudo -n /usr/sbin/swanctl --initiate -c {connection_id} --child {child_name} --timeout 30`.
5. **Finalización**: Al desconectar, se invoca `sudo -n /usr/sbin/swanctl --terminate -c {connection_id}` y luego `sudo -n /usr/sbin/swanctl --unload-conn -c {connection_id}` para no dejar configuraciones cargadas en el demonio.
