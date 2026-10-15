# Contrato de Interfaz: Motor VPN Unificado (`BaseVPNBackend`)

**Feature**: `specs/001-dual-vpn-gna/spec.md`  
**Date**: 2026-10-14  

---

## 1. Definición de la Clase Base Abstracta

Todos los motores de conexión (`OpenFortiBackend` para SSL y `StrongSwanBackend` para IPSec) deben heredar de `BaseVPNBackend` (subclase de `QObject`), garantizando el desacoplamiento total de la interfaz gráfica respecto a los detalles de los binarios de red.

```python
from abc import abstractmethod
from PySide6.QtCore import QObject, Signal

class BaseVPNBackend(QObject):
    """
    Contrato base estandarizado para los motores VPN en VPN-GNA.
    """
    # Señales obligatorias para comunicación con la GUI
    state_changed = Signal(str)                  # "connecting", "connected", "disconnected", "failover"
    log_message = Signal(str)                    # Texto para el panel de logs en tiempo real
    connection_failed = Signal(str)              # Motivo del fallo legible para el usuario
    connection_details_received = Signal(dict)   # {"local_ip", "remote_ip", "gateway_ip", "dns", "interface"}
    traffic_stats_updated = Signal(int, int)     # (rx_bytes, tx_bytes) acumulados
    cert_trust_needed = Signal(str)              # Hash SHA256 (solo SSL, no-op en IPSec)

    @abstractmethod
    def connect_backend(self, gateway: str, port: int, username: str, 
                        password: str, otp: str | None, dns_domain: str | None,
                        extra_params: dict) -> None:
        """
        Inicia el proceso asíncrono de establecimiento de conexión.
        Debe ejecutarse en segundo plano sin bloquear el hilo principal de Qt.
        """
        pass

    @abstractmethod
    def disconnect_backend(self) -> None:
        """
        Finaliza de inmediato la sesión VPN y limpia cualquier archivo
        temporal o subproceso activo.
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """
        Devuelve True si el motor tiene un túnel activo o en proceso de conexión.
        """
        pass

    @abstractmethod
    def is_passwordless_sudo_ready(self) -> bool:
        """
        Verifica si los comandos específicos del motor cuentan con permiso sudo sin contraseña.
        - SSL: openfortivpn
        - IPSec: swanctl
        """
        pass
```

---

## 2. Invariantes del Contrato

1. **Garantía Asíncrona**: Ninguna llamada a `connect_backend()` o `disconnect_backend()` puede bloquear por más de 50 milisegundos el hilo de la GUI.
2. **Ciclo de Vida de Limpieza**: Siempre que se invoque `disconnect_backend()`, el backend debe garantizar la liberación de la interfaz, el restablecimiento de DNS y el borrado seguro de cualquier archivo efímero en `/run/user/<uid>/`.
3. **Manejo de Errores Limpio**: En caso de error (credenciales incorrectas, host caído, timeout), el backend debe emitir `connection_failed(razon)` y terminar indefectiblemente en el estado `disconnected`.
