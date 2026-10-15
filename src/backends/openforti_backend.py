import os
import re
import signal
import subprocess
import tempfile
from PySide6.QtCore import QThread, Signal, QTimer
from .base import BaseVPNBackend


class OpenFortiRunner(QThread):
    """
    Hilo de ejecución en segundo plano para el proceso openfortivpn.
    """
    output_received = Signal(str)
    process_finished = Signal(int)
    cert_error_detected = Signal(str)

    def __init__(self, config_path: str):
        super().__init__()
        self.config_path = config_path
        self.process = None
        self._is_running = False
        self.cert_regex = re.compile(r"(?:--trusted-cert\s+|trusted-cert\s*=\s*)([a-f0-9]{64})")

    def _is_passwordless_sudo_ok(self) -> bool:
        try:
            return subprocess.call(
                ["sudo", "-n", "openfortivpn", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            ) == 0
        except Exception:
            return False

    def run(self):
        self._is_running = True

        if os.geteuid() == 0:
            cmd = ["openfortivpn", "-c", self.config_path]
        elif self._is_passwordless_sudo_ok():
            cmd = ["sudo", "openfortivpn", "-c", self.config_path]
        else:
            cmd = ["pkexec", "openfortivpn", "-c", self.config_path]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid
            )

            while self._is_running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    self.output_received.emit(line)
                    match = self.cert_regex.search(line)
                    if match:
                        self.cert_error_detected.emit(match.group(1))

            if self.process:
                return_code = self.process.wait()
                self.process_finished.emit(return_code)

        except Exception as e:
            self.output_received.emit(f"Internal Error: {e}")
            self.process_finished.emit(1)
        finally:
            self._is_running = False
            # Seguridad: borrar archivo de configuración efímero
            if os.path.exists(self.config_path):
                try:
                    os.remove(self.config_path)
                except OSError:
                    pass

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                    try:
                        self.process.wait(timeout=2.0)
                        return
                    except subprocess.TimeoutExpired:
                        pass
            except Exception:
                pass

            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                try:
                    if self._is_passwordless_sudo_ok():
                        subprocess.run(["sudo", "killall", "openfortivpn"],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                    else:
                        subprocess.run(["pkexec", "killall", "openfortivpn"],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                except Exception:
                    pass


class OpenFortiBackend(BaseVPNBackend):
    """
    Motor VPN para túneles SSL-VPN basado en openfortivpn.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = None
        self.temp_config_path = None
        self.vpn_interface = None
        self.current_dns_domain = ""
        self.session_data = {
            "username": "N/A",
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A",
            "dns": "N/A"
        }

        # Expresiones regulares para parseo de salida
        self.re_interface = re.compile(r"Using interface (ppp\d+|tun\d+)")
        self.re_local_ip = re.compile(r"local  IP address ([\d\.]+)")
        self.re_remote_ip = re.compile(r"remote IP address ([\d\.]+)")
        self.re_dns = re.compile(r"ns \[([\d\.,\s]+)\]")

        # Temporizador de estadísticas de tráfico
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self._read_traffic_stats)

    def is_passwordless_sudo_ready(self) -> bool:
        try:
            return subprocess.call(
                ["sudo", "-n", "openfortivpn", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            ) == 0
        except Exception:
            return False

    def is_running(self) -> bool:
        return self.runner is not None and self.runner.isRunning()

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
        if self.is_running():
            return

        self._reset_session_data(username, gateway)
        self.current_dns_domain = dns_domain or ""
        trusted_cert = (extra_params or {}).get("trusted_cert", "")

        # Generar archivo de configuración efímero en memoria RAM o /tmp con permisos 0600
        config_content = f"""host = {gateway}
port = {port or 443}
username = {username}
password = {password}
set-dns = 1
pppd-use-peerdns = 1
"""
        if trusted_cert:
            config_content += f"trusted-cert = {trusted_cert.strip()}\n"

        if otp:
            config_content += f"otp = {otp.strip()}\n"

        try:
            runtime_dir = f"/run/user/{os.getuid()}/vpn-gna"
            if not os.path.exists(runtime_dir):
                os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
            fd, self.temp_config_path = tempfile.mkstemp(prefix="vpngna_ssl_", suffix=".conf", dir=runtime_dir, text=True)
        except Exception:
            fd, self.temp_config_path = tempfile.mkstemp(prefix="vpngna_ssl_", suffix=".conf", text=True)

        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        os.chmod(self.temp_config_path, 0o600)

        self.state_changed.emit("connecting")
        self.runner = OpenFortiRunner(self.temp_config_path)
        self.runner.output_received.connect(self._on_output)
        self.runner.process_finished.connect(self._on_finished)
        self.runner.cert_error_detected.connect(self.cert_trust_needed.emit)
        self.runner.finished.connect(self._on_thread_finished)
        self.runner.start()

    def disconnect_backend(self) -> None:
        self.stats_timer.stop()
        if self.runner:
            self.runner.stop()
        self.state_changed.emit("disconnected")

    def _reset_session_data(self, username="N/A", gateway="N/A"):
        self.vpn_interface = None
        self.session_data = {
            "username": username,
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": gateway,
            "dns": "N/A"
        }

    def _on_output(self, text: str):
        self.log_message.emit(text)

        m_iface = self.re_interface.search(text)
        if m_iface:
            self.vpn_interface = m_iface.group(1)
            self.session_data["interface"] = self.vpn_interface

        m_local = self.re_local_ip.search(text)
        if m_local:
            self.session_data["local_ip"] = m_local.group(1)

        m_remote = self.re_remote_ip.search(text)
        if m_remote:
            self.session_data["remote_ip"] = m_remote.group(1)

        m_dns = self.re_dns.search(text)
        if m_dns:
            self.session_data["dns"] = m_dns.group(1)

        if "Tunnel is up and running" in text:
            self.state_changed.emit("connected")
            self.connection_details_received.emit(self.session_data)
            self._apply_dns_settings()
            if self.vpn_interface:
                self.stats_timer.start()

    def _apply_dns_settings(self):
        if not self.vpn_interface or not self.current_dns_domain:
            return

        raw_domains = re.split(r'[,\s]+', self.current_dns_domain)
        domains_to_apply = []
        for d in raw_domains:
            d = d.strip()
            if not d:
                continue
            if not d.startswith("~"):
                d = f"~{d}"
            domains_to_apply.append(d)

        if not domains_to_apply:
            return

        domains_str = " ".join(domains_to_apply)
        self.log_message.emit(f"Configurando Split-DNS para {domains_str} en {self.vpn_interface}...")

        try:
            if subprocess.call(["which", "resolvectl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                cmd_domain = ["resolvectl", "domain", self.vpn_interface] + domains_to_apply
                if os.geteuid() != 0:
                    # Usar sudo si está disponible sin contraseña, sino fallback a pkexec
                    if subprocess.call(["sudo", "-n", "resolvectl", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                        cmd_domain = ["sudo"] + cmd_domain
                    else:
                        cmd_domain = ["pkexec"] + cmd_domain

                result = subprocess.run(cmd_domain, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    self.log_message.emit(f"DNS configurado: {domains_str} -> {self.vpn_interface}")
                else:
                    self.log_message.emit(f"Fallo al configurar DNS: {result.stderr or result.stdout}")
        except Exception as e:
            self.log_message.emit(f"Error configurando DNS: {e}")

    def _read_traffic_stats(self):
        if not self.vpn_interface:
            return
        rx_path = f"/sys/class/net/{self.vpn_interface}/statistics/rx_bytes"
        tx_path = f"/sys/class/net/{self.vpn_interface}/statistics/tx_bytes"
        try:
            rx = 0
            tx = 0
            if os.path.exists(rx_path):
                with open(rx_path, "r") as f:
                    rx = int(f.read().strip())
            if os.path.exists(tx_path):
                with open(tx_path, "r") as f:
                    tx = int(f.read().strip())
            self.traffic_stats_updated.emit(rx, tx)
        except Exception:
            pass

    def _on_finished(self, code: int):
        self.stats_timer.stop()
        if code != 0 and self.session_data.get("interface") is None:
            self.connection_failed.emit(f"El proceso terminó con error (código {code}).")
        self.state_changed.emit("disconnected")

    def _on_thread_finished(self):
        self.stats_timer.stop()
        if self.temp_config_path and os.path.exists(self.temp_config_path):
            try:
                os.remove(self.temp_config_path)
            except OSError:
                pass
        self.temp_config_path = None
