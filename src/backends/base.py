from PySide6.QtCore import QObject, Signal


class BaseVPNBackend(QObject):
    """
    Contrato base estandarizado para motores VPN (SSL e IPSec) en VPN-GNA.
    Desacopla la lógica de procesos y protocolos de red de la interfaz gráfica.
    """

    # Señales Qt estándar para comunicación asíncrona con el orquestador y la GUI
    state_changed = Signal(str)                  # Estados: "connecting", "connected", "disconnected", "failover"
    log_message = Signal(str)                    # Registro textual para consola/diálogo de logs
    connection_failed = Signal(str)              # Motivo descriptivo del fallo
    connection_details_received = Signal(dict)   # {"username", "local_ip", "remote_ip", "gateway_ip", "dns", "interface"}
    traffic_stats_updated = Signal(int, int)     # (rx_bytes, tx_bytes) acumulados
    cert_trust_needed = Signal(str)              # Hash SHA256 detectado (requerido en SSL, no-op en IPSec)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_active = False

    def connect_backend(
        self,
        gateway: str,
        port: int,
        username: str,
        password: str,
        otp: str = None,
        dns_domain: str = None,
        extra_params: dict = None
    ) -> None:
        """
        Inicia el establecimiento asíncrono de la conexión.
        No debe bloquear el hilo principal de la interfaz gráfica.
        """
        raise NotImplementedError("Subclasses must implement connect_backend")

    def disconnect_backend(self) -> None:
        """
        Finaliza de inmediato la sesión activa y garantiza la limpieza de
        recursos, interfaces y archivos temporales en memoria.
        """
        raise NotImplementedError("Subclasses must implement disconnect_backend")

    def is_running(self) -> bool:
        """
        Indica si el motor se encuentra actualmente en ejecución o conectando.
        """
        raise NotImplementedError("Subclasses must implement is_running")

    def is_passwordless_sudo_ready(self) -> bool:
        """
        Verifica si los comandos del motor disponen de ejecución sudo sin contraseña.
        """
        raise NotImplementedError("Subclasses must implement is_passwordless_sudo_ready")
