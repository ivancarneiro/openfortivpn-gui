import os
import re
import signal
import subprocess
import time
from PySide6.QtCore import QObject, Signal, QThread, QTimer
try:
    from backends import BaseVPNBackend, OpenFortiBackend, StrongSwanBackend
except ImportError:
    from src.backends import BaseVPNBackend, OpenFortiBackend, StrongSwanBackend


class VPNManager(QObject):
    """
    Orquestador polimórfico de conexiones VPN para VPN-GNA.
    Gestiona la fábrica de backends (SSL e IPSec), failover multi-gateway y
    expone una interfaz unificada de señales para la GUI.
    """

    state_changed = Signal(str)                  # "connected", "disconnected", "connecting", "failover"
    log_message = Signal(str)
    connection_failed = Signal(str)              # Motivo del fallo
    cert_trust_needed = Signal(str)              # Hash SHA256 (solo SSL)
    connection_details_received = Signal(dict)   # {username, interface, local_ip, remote_ip, gateway_ip, dns}
    traffic_stats_updated = Signal(int, int)     # (rx_bytes, tx_bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_backend: BaseVPNBackend | None = None
        self.current_profile: dict | None = None
        self.connection_queue = []               # Lista de gateways para failover
        self.current_attempt_index = 0
        self.is_user_disconnected = False
        self.current_password = ""
        self.current_otp = None
        self.current_dns_domain = ""

        # Sesión actual
        self.session_data = {
            "username": "N/A",
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A",
            "dns": "N/A"
        }

        # Soporte para modo heredado (config_paths de openfortivpn)
        self.legacy_config_queue = []

    def get_connected_username(self) -> str:
        """
        Retorna el nombre del usuario conectado en la sesión actual.
        """
        user = self.session_data.get("username")
        if user and user != "N/A":
            return user
        if self.current_profile:
            return self.current_profile.get("username", "")
        return ""

    def get_session_data(self) -> dict:
        return self.session_data

    def is_connected(self) -> bool:
        return self.active_backend is not None and self.active_backend.is_running()

    def connect_vpn(self, target, password: str = "", otp: str = None, dns_domain: str = ""):
        """
        Inicia la conexión. Acepta:
        1. target = dict (perfil de conexión completo con 'vpn_type', 'gateways', etc.)
        2. target = list (rutas de archivo .conf de openfortivpn para retrocompatibilidad)
        """
        if self.active_backend and self.active_backend.is_running():
            return

        self.is_user_disconnected = False
        self.current_attempt_index = 0
        self._reset_session_data()

        if isinstance(target, dict):
            # Modo unificado y moderno de perfiles
            self.current_profile = target
            self.current_password = password
            self.current_otp = otp
            self.current_dns_domain = dns_domain or target.get("dns_domain", "")
            self.connection_queue = target.get("gateways", [])
            self.legacy_config_queue = []

            if not self.connection_queue:
                self.connection_failed.emit("El perfil no contiene ningún gateway configurado.")
                self.state_changed.emit("disconnected")
                return

            self._start_profile_attempt()

        elif isinstance(target, list):
            # Modo retrocompatible para listas de archivos temporales
            self.legacy_config_queue = target
            self.current_dns_domain = dns_domain
            self.current_profile = {
                "vpn_type": "ssl",
                "username": "openforti",
                "dns_domain": dns_domain,
                "gateways": [{"host": "gateway", "port": 443}] * len(target)
            }
            self._start_legacy_attempt()

    def _start_profile_attempt(self):
        if self.current_attempt_index >= len(self.connection_queue):
            self.state_changed.emit("disconnected")
            self.connection_failed.emit("Todos los gateways del perfil fallaron.")
            return

        gw = self.connection_queue[self.current_attempt_index]
        host = gw.get("host", "")
        port = gw.get("port", 443)
        vpn_type = self.current_profile.get("vpn_type", "ssl")

        self.state_changed.emit("connecting" if self.current_attempt_index == 0 else "failover")
        self.log_message.emit(f"Conectando a {host}:{port} vía {vpn_type.upper()} (Intento #{self.current_attempt_index + 1})...")

        # Limpiar backend anterior si existiera
        if self.active_backend:
            try:
                self.active_backend.disconnect_backend()
            except Exception:
                pass
            self.active_backend = None

        # Instanciar el backend correspondiente mediante Factory
        if vpn_type == "ipsec":
            self.active_backend = StrongSwanBackend(self)
        else:
            self.active_backend = OpenFortiBackend(self)

        # Conectar señales del backend
        self.active_backend.state_changed.connect(self._on_backend_state_changed)
        self.active_backend.log_message.connect(self.log_message.emit)
        self.active_backend.connection_failed.connect(self._on_backend_failed)
        self.active_backend.connection_details_received.connect(self._on_backend_details)
        self.active_backend.traffic_stats_updated.connect(self.traffic_stats_updated.emit)
        self.active_backend.cert_trust_needed.connect(self.cert_trust_needed.emit)

        extra_params = {
            "trusted_cert": self.current_profile.get("trusted_cert", ""),
            "preshared_key": self.current_profile.get("preshared_key", "")
        }

        self.active_backend.connect_backend(
            gateway=host,
            port=port,
            username=self.current_profile.get("username", ""),
            password=self.current_password,
            otp=self.current_otp,
            dns_domain=self.current_dns_domain,
            extra_params=extra_params
        )

    def _start_legacy_attempt(self):
        if self.current_attempt_index >= len(self.legacy_config_queue):
            self.state_changed.emit("disconnected")
            self.connection_failed.emit("Todos los gateways fallaron.")
            return

        config_path = self.legacy_config_queue[self.current_attempt_index]
        self.state_changed.emit("connecting" if self.current_attempt_index == 0 else "failover")
        self.log_message.emit(f"Intentando conectar con gateway #{self.current_attempt_index + 1}...")

        self.active_backend = OpenFortiBackend(self)
        self.active_backend.temp_config_path = config_path
        self.active_backend.current_dns_domain = self.current_dns_domain

        self.active_backend.state_changed.connect(self._on_backend_state_changed)
        self.active_backend.log_message.connect(self.log_message.emit)
        self.active_backend.connection_failed.connect(self._on_backend_failed)
        self.active_backend.connection_details_received.connect(self._on_backend_details)
        self.active_backend.traffic_stats_updated.connect(self.traffic_stats_updated.emit)
        self.active_backend.cert_trust_needed.connect(self.cert_trust_needed.emit)

        # Iniciar runner usando OpenFortiRunner
        from backends.openforti_backend import OpenFortiRunner
        self.active_backend.runner = OpenFortiRunner(config_path)
        self.active_backend.runner.output_received.connect(self.active_backend._on_output)
        self.active_backend.runner.process_finished.connect(self.active_backend._on_finished)
        self.active_backend.runner.cert_error_detected.connect(self.cert_trust_needed.emit)
        self.active_backend.runner.start()

    def disconnect_vpn(self):
        self.is_user_disconnected = True
        if self.active_backend:
            self.active_backend.disconnect_backend()
        self.state_changed.emit("disconnected")

    def blocking_stop(self):
        """Detiene y espera al backend antes de cerrar la app."""
        self.disconnect_vpn()
        if self.active_backend and hasattr(self.active_backend, "runner") and self.active_backend.runner:
            self.active_backend.runner.wait(1500)

    def _on_backend_state_changed(self, state: str):
        self.state_changed.emit(state)

    def _on_backend_details(self, details: dict):
        if self.current_profile:
            details["username"] = self.current_profile.get("username", details.get("username", "N/A"))
        self.session_data.update(details)
        self.connection_details_received.emit(self.session_data)

    def _on_backend_failed(self, reason: str):
        if self.is_user_disconnected:
            return

        total_gateways = len(self.connection_queue) if self.connection_queue else len(self.legacy_config_queue)
        if self.current_attempt_index + 1 < total_gateways:
            self.current_attempt_index += 1
            self.log_message.emit(f"Gateway falló: {reason}. Iniciando failover al siguiente...")
            self.state_changed.emit("failover")
            if self.connection_queue:
                self._start_profile_attempt()
            else:
                self._start_legacy_attempt()
        else:
            self.connection_failed.emit(reason)
            self.state_changed.emit("disconnected")

    def _reset_session_data(self):
        username = self.current_profile.get("username", "N/A") if self.current_profile else "N/A"
        self.session_data = {
            "username": username,
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A",
            "dns": "N/A"
        }
        self.traffic_stats_updated.emit(0, 0)
