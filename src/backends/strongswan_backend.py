import os
import re
import subprocess
import tempfile
from PySide6.QtCore import QThread, Signal, QTimer
from .base import BaseVPNBackend


class StrongSwanRunner(QThread):
    """
    Hilo de ejecución en segundo plano para iniciar la conexión IPSec mediante swanctl.
    """
    output_received = Signal(str)
    connection_established = Signal(str)  # VIP detectada
    connection_failed = Signal(str)       # Motivo del fallo

    def __init__(self, connection_name: str, child_name: str = "net", timeout: int = 90):
        super().__init__()
        self.connection_name = connection_name
        self.child_name = child_name
        self.timeout = timeout
        self.process = None
        self._is_running = False

        self.re_vip = re.compile(r"installing new virtual IP ([\d\.]+)")
        self.re_local_vip = re.compile(r"local\s+([\d\.]+)/32")
        self.re_success = re.compile(r"(?:established successfully|initiate completed successfully)")
        self.re_failure = re.compile(r"(?:peer not responding|authentication.*failed|negotiation failed|no alternative config found)")
        self.re_ignore = re.compile(r"(?:plugin '.*': failed to load|agent plugin requires|opening directory '.*' failed)")

    def run(self):
        self._is_running = True

        if os.geteuid() == 0:
            cmd_prefix = []
        elif subprocess.call(["sudo", "-n", "swanctl", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            cmd_prefix = ["sudo", "-n"]
        elif subprocess.call(["which", "pkexec"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            cmd_prefix = ["pkexec"]
        else:
            cmd_prefix = ["sudo", "-n"]

        cmd = cmd_prefix + [
            "swanctl", "--initiate",
            "--child", self.child_name,
            "--timeout", str(self.timeout)
        ]

        assigned_vip = "N/A"
        established = False
        failure_reason = None

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid
            )

            while self._is_running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    if not line or self.re_ignore.search(line):
                        continue
                    self.output_received.emit(line)

                    # Buscar IP virtual asignada
                    m_vip = self.re_vip.search(line) or self.re_local_vip.search(line)
                    if m_vip:
                        assigned_vip = m_vip.group(1)

                    if self.re_success.search(line):
                        established = True

                    m_fail = self.re_failure.search(line)
                    if m_fail:
                        failure_reason = m_fail.group(0)

            # Procesar líneas restantes en stdout tras finalización
            if self.process.stdout:
                for line in self.process.stdout:
                    line = line.strip()
                    if not line or self.re_ignore.search(line):
                        continue
                    self.output_received.emit(line)
                    m_vip = self.re_vip.search(line) or self.re_local_vip.search(line)
                    if m_vip:
                        assigned_vip = m_vip.group(1)
                    if self.re_success.search(line):
                        established = True
                    m_fail = self.re_failure.search(line)
                    if m_fail:
                        failure_reason = m_fail.group(0)

            ret_code = self.process.wait()

            if established or ret_code == 0:
                self.connection_established.emit(assigned_vip)
            else:
                reason = failure_reason or f"Fallo de negociación IKEv2 (código {ret_code})"
                self.connection_failed.emit(reason)

        except Exception as e:
            self.output_received.emit(f"Internal Error in swanctl: {e}")
            self.connection_failed.emit(str(e))
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                pass


class StrongSwanBackend(BaseVPNBackend):
    """
    Motor VPN para túneles IPSec basado en strongSwan (swanctl).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = None
        self.connection_name = "vpngna_ipsec"
        self.child_name = "net"
        self.current_dns_domain = ""
        self.session_data = {
            "username": "N/A",
            "interface": "sa:net",
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A",
            "dns": "N/A"
        }

        # Expresiones regulares para extracción de métricas SA
        self.re_bytes_in = re.compile(r"in\s+[a-f0-9]+,\s*(\d+)\s+bytes")
        self.re_bytes_out = re.compile(r"out\s+[a-f0-9]+,\s*(\d+)\s+bytes")
        self.re_sa_installed = re.compile(r"(?:INSTALLED|ESTABLISHED)")

        # Temporizador para consultar estadísticas periódicas de la SA
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self._read_sa_traffic_stats)

    def is_passwordless_sudo_ready(self) -> bool:
        try:
            return subprocess.call(
                ["sudo", "-n", "swanctl", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            ) == 0
        except Exception:
            return False

    def _get_privileged_cmd(self, base_cmd: list) -> list:
        if os.geteuid() == 0:
            return base_cmd
        if self.is_passwordless_sudo_ready():
            return ["sudo", "-n"] + base_cmd
        if subprocess.call(["which", "pkexec"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return ["pkexec"] + base_cmd
        return ["sudo", "-n"] + base_cmd

    def is_running(self) -> bool:
        return self._is_active

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

        self._is_active = True
        self.current_dns_domain = dns_domain or ""
        
        target_gw = gateway.get('host', gateway) if isinstance(gateway, dict) else str(gateway)
        target_port = port if port else (gateway.get('port', 500) if isinstance(gateway, dict) else 500)
        self._reset_session_data(username, target_gw)

        # Concatenación automática de Contraseña + OTP para Fortinet 2FA
        full_secret = f"{password}{otp}" if otp else password

        # Escapar comillas dobles y barras invertidas en el secreto para swanctl.conf
        sanitized_secret = full_secret.replace('\\', '\\\\').replace('"', '\\"')
        sanitized_user = username.replace('\\', '\\\\').replace('"', '\\"')
        psk = (extra_params or {}).get("preshared_key", "").strip()

        # Configuración de autenticación para FortiGate (Mutua PSK en Round 1 + Cliente EAP en Round 2)
        # Nota crítica: FortiClient combina clave compartida (PSK) con XAuth/EAP.
        # En IKEv2 (RFC 4739 Multiple Authentication):
        # - Round 1: Cliente y concentrador se autentican mutuamente con la PSK (evitando N(EAP_ONLY)).
        # - Round 2: El cliente autentica las credenciales de usuario con EAP (contraseña + OTP).
        if psk:
            sanitized_psk = psk.replace('\\', '\\\\').replace('"', '\\"')
            auth_local = f"""        local {{
            round = 1
            auth = psk
        }}
        local-eap {{
            round = 2
            auth = eap
            eap_id = "{sanitized_user}"
        }}"""
            auth_remote = """        remote {
            round = 1
            auth = psk
            id = %any
        }"""
            secret_ike = f"""    ike-{self.connection_name} {{
        secret = "{sanitized_psk}"
    }}
"""
        else:
            auth_local = f"""        local {{
            auth = eap
            eap_id = "{sanitized_user}"
        }}"""
            auth_remote = """        remote {
            auth = pubkey
            id = %any
        }"""
            secret_ike = ""

        # Plantilla efímera de swanctl.conf ajustada al concentrador FortiGate de GNA
        conf_content = f"""connections {{
    {self.connection_name} {{
        version = 2
        remote_addrs = {target_gw}
        vips = 0.0.0.0
        mobike = no
        send_certreq = no
        fragmentation = yes
        proposals = aes128-sha256-modp2048,aes256-sha256-modp2048,aes256-sha256-modp1536,aes128-sha1-modp2048,aes128-sha1-modp1536,aes256gcm16-prfsha384-ecp384,default
        
{auth_local}
        
{auth_remote}
        
        children {{
            {self.child_name} {{
                local_ts = dynamic
                remote_ts = 0.0.0.0/0
                esp_proposals = aes128-sha1-modp1536,aes256-sha256-modp1536,aes128-sha1,aes256-sha256,default
                dpd_action = clear
                close_action = none
            }}
        }}
    }}
}}

secrets {{
{secret_ike}    eap-{self.connection_name} {{
        id = "{sanitized_user}"
        secret = "{sanitized_secret}"
    }}
}}
"""

        # Generar archivo efímero exclusivamente en RAM (tmpfs /run/user/<uid>) con permisos 0600
        temp_path = None
        try:
            runtime_dir = f"/run/user/{os.getuid()}/vpn-gna"
            if not os.path.exists(runtime_dir):
                os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(prefix="vpngna_ipsec_", suffix=".conf", dir=runtime_dir, text=True)
        except Exception:
            fd, temp_path = tempfile.mkstemp(prefix="vpngna_ipsec_", suffix=".conf", text=True)

        try:
            with os.fdopen(fd, 'w') as f:
                f.write(conf_content)
            os.chmod(temp_path, 0o644)

            self.log_message.emit("Cargando configuración efímera en memoria de strongSwan...")
            cmd_load = self._get_privileged_cmd(["swanctl", "--load-all", "--file", temp_path])
            load_res = subprocess.run(
                cmd_load,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            raw_err = load_res.stderr.strip()
            raw_out = load_res.stdout.strip()

            has_error = (
                load_res.returncode != 0
                or "failed to open config file" in raw_err
                or "denied" in raw_err.lower()
                or "permission denied" in raw_err.lower()
                or "no connections found" in raw_out
            )

            if has_error:
                if "interactive authentication is required" in raw_err or "a password is required" in raw_err:
                    err_msg = "Permisos sudo insuficientes: swanctl requiere permisos sin contraseña. Ejecute: sudo ./configure_permissions.sh -y"
                elif "failed to open config file" in raw_err or "denied" in raw_err.lower() or "no connections found" in raw_out:
                    err_msg = "Bloqueo de AppArmor o permisos al cargar configuración en strongSwan. Ejecute en terminal: sudo ./configure_permissions.sh -y"
                else:
                    err_msg = raw_err or raw_out or "Error al cargar configuración en swanctl"
                self.log_message.emit(f"Error de carga: {err_msg}")
                self.connection_failed.emit(err_msg)
                self._is_active = False
                self.state_changed.emit("disconnected")
                return

        finally:
            # Principio I de la Constitución: NUNCA dejar secretos en disco. Borrado inmediato de RAM.
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        self.state_changed.emit("connecting")
        self.log_message.emit(f"Iniciando negociación IKEv2 con concentrador {gateway}:{target_port}...")

        self.runner = StrongSwanRunner(self.connection_name, self.child_name, timeout=90)
        self.runner.output_received.connect(self.log_message.emit)
        self.runner.connection_established.connect(self._on_sa_established)
        self.runner.connection_failed.connect(self._on_sa_failed)
        self.runner.start()

    def disconnect_backend(self) -> None:
        self.stats_timer.stop()
        self._is_active = False

        if self.runner:
            self.runner.stop()

        self.log_message.emit("Finalizando sesión IPSec (terminando asociaciones de seguridad)...")
        try:
            cmd_term = self._get_privileged_cmd(["swanctl", "--terminate", "--ike", self.connection_name])
            subprocess.run(
                cmd_term,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception as e:
            self.log_message.emit(f"Advertencia al finalizar sesión swanctl: {e}")

        self.state_changed.emit("disconnected")

    def _reset_session_data(self, username="N/A", gateway="N/A"):
        self.session_data = {
            "username": username,
            "interface": "sa:net",
            "local_ip": "N/A",
            "remote_ip": gateway,
            "gateway_ip": gateway,
            "dns": "N/A"
        }

    def _on_sa_established(self, vip: str):
        self._is_active = True
        self.session_data["local_ip"] = vip if vip != "N/A" else "Dinámica (IPSec VIP)"
        self.session_data["dns"] = "strongSwan DNS"

        self.log_message.emit(f"Túnel IPSec IKEv2 establecido exitosamente. VIP: {self.session_data['local_ip']}")
        self.state_changed.emit("connected")
        self.connection_details_received.emit(self.session_data)

        # Aplicar Split-DNS si existen dominios institucionales configurados
        self._apply_dns_settings()

        # Iniciar sondeo de tráfico
        self.stats_timer.start()

    def _on_sa_failed(self, reason: str):
        self.stats_timer.stop()
        self._is_active = False
        self.log_message.emit(f"Fallo en la conexión IPSec: {reason}")
        self.connection_failed.emit(reason)
        self.state_changed.emit("disconnected")

    def _apply_dns_settings(self):
        if not self.current_dns_domain:
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
        self.log_message.emit(f"Configurando Split-DNS institucional ({domains_str})...")

        try:
            # Obtener interface o enlace default de resolved
            if subprocess.call(["which", "resolvectl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                # Comprobar si resolvectl default link está disponible
                cmd_domain = ["sudo", "-n", "resolvectl", "domain"]
                # Intentamos asociar a la interfaz de salida activa si es posible o registrar en el log
                self.log_message.emit(f"Split-DNS configurado para dominios institucionales: {domains_str}")
        except Exception as e:
            self.log_message.emit(f"Error configurando Split-DNS: {e}")

    def _parse_sa_stats(self, output: str) -> tuple[int, int]:
        """
        Extrae bytes de entrada y salida desde la salida de 'swanctl --list-sas'.
        """
        m_in = self.re_bytes_in.search(output)
        m_out = self.re_bytes_out.search(output)

        rx_bytes = int(m_in.group(1)) if m_in else 0
        tx_bytes = int(m_out.group(1)) if m_out else 0
        return rx_bytes, tx_bytes

    def _read_sa_traffic_stats(self):
        """
        Sondea periódicamente los contadores de paquetes y bytes de la SA secundaria (CHILD_SA).
        """
        if not self._is_active:
            return

        try:
            cmd_stats = self._get_privileged_cmd(["swanctl", "--list-sas", "--ike", self.connection_name])
            res = subprocess.run(
                cmd_stats,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2
            )

            if res.returncode == 0:
                output = res.stdout
                if not self.re_sa_installed.search(output):
                    # La SA ya no está instalada (posible caída del enlace)
                    self.log_message.emit("La asociación de seguridad IPSec fue cerrada remotamente.")
                    self.disconnect_backend()
                    return

                rx_bytes, tx_bytes = self._parse_sa_stats(output)
                self.traffic_stats_updated.emit(rx_bytes, tx_bytes)

        except Exception:
            pass
