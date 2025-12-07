import subprocess
import os
import signal
import time
import re
from PySide6.QtCore import QObject, Signal, QThread, QTimer

class VPNRunner(QThread):
    """
    Thread to run the openfortivpn process.
    """
    output_received = Signal(str)
    # error_occurred = Signal(str) # Not widely used, output covers it
    process_finished = Signal(int)
    cert_error_detected = Signal(str) # Emits the hash found

    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.process = None
        self._is_running = False
        # Regex to find: "trusted-cert = <hash>" or "--trusted-cert <hash>"
        # The log output shows:
        # ERROR:      trusted-cert = 18b3ca13afe20180d70f1efbb949b9dcafb793d0aae246518b6ef909646f23b8
        self.cert_regex = re.compile(r"trusted-cert\s*=\s*([a-f0-9]{64})")

    def run(self):
        self._is_running = True
        
        # Check if we are running as root
        if os.geteuid() == 0:
            cmd = ["openfortivpn", "-c", self.config_path]
        else:
            cmd = ["pkexec", "openfortivpn", "-c", self.config_path]
        
        try:
            # Start the process with pipes for output
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True,
                bufsize=1, # Line buffered
                preexec_fn=os.setsid 
            )

            # Read output line by line
            while self._is_running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    self.output_received.emit(line)
                    # Check for cert error
                    match = self.cert_regex.search(line)
                    if match:
                         self.cert_error_detected.emit(match.group(1))
            
            # If process exits
            if self.process:
                return_code = self.process.wait()
                self.process_finished.emit(return_code)

        except Exception as e:
            self.output_received.emit(f"Internal Error: {e}")
            self.process_finished.emit(1)
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass 

class VPNManager(QObject):
    state_changed = Signal(str) # "connected", "disconnected", "connecting", "failover"
    log_message = Signal(str)
    connection_failed = Signal(str) # Reason
    cert_trust_needed = Signal(str) # Hash
    
    # New signals
    connection_details_received = Signal(dict) # {interface, local_ip, remote_ip, gateway_ip}
    traffic_stats_updated = Signal(int, int) # (rx_bytes, tx_bytes)

    def __init__(self):
        super().__init__()
        self.runner = None
        self.connection_queue = [] 
        self.current_attempt_index = 0
        self.is_user_disconnected = False
        
        # Stats monitoring
        self.vpn_interface = None
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(1000)
        self.stats_timer.timeout.connect(self._read_traffic_stats)
        
        # IP Regex
        self.re_interface = re.compile(r"Using interface (ppp\d+|tun\d+)")
        self.re_local_ip = re.compile(r"local  IP address ([\d\.]+)")
        self.re_remote_ip = re.compile(r"remote IP address ([\d\.]+)")
        # Note: Gateway IP is usually the one we connect to, or resolved from host.
        
        self.session_data = {
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A"
        }

    def connect_vpn(self, config_paths):
        if self.runner and self.runner.isRunning():
            return
            
        self.connection_queue = config_paths
        self.current_attempt_index = 0
        self.is_user_disconnected = False
        self._reset_session_data()
        self._start_attempt()
        
    def _reset_session_data(self):
        self.session_data = {
            "interface": None,
            "local_ip": "N/A",
            "remote_ip": "N/A",
            "gateway_ip": "N/A"
        }
        self.vpn_interface = None
        self.stats_timer.stop()
        self.traffic_stats_updated.emit(0, 0)

    # ... _start_attempt, disconnect_vpn ... keep as is but verify later
    def _start_attempt(self):
        if self.current_attempt_index >= len(self.connection_queue):
            self.state_changed.emit("disconnected")
            self.connection_failed.emit("Todos los gateways fallaron.")
            return

        config_path = self.connection_queue[self.current_attempt_index]
        self.state_changed.emit("connecting")
        
        # Try to extract host for "Gateway IP" display (approximate)
        # We can pass plain host if needed, but parsing from file is tricky here.
        # Let's assume we can get it later or update UI with config data separately.
        self.log_message.emit(f"Intentando conectar con gateway #{self.current_attempt_index + 1}...")

        self.runner = VPNRunner(config_path)
        self.runner.output_received.connect(self._on_output)
        self.runner.process_finished.connect(self._on_finished)
        self.runner.cert_error_detected.connect(self._on_cert_error)
        self.runner.start()

    def disconnect_vpn(self):
        self.is_user_disconnected = True
        self.stats_timer.stop()
        if self.runner:
            self.runner.stop()
            # Do not set self.runner = None here. Let _on_finished handle it, 
            # or allow caller to wait on it.
        self.state_changed.emit("disconnected")

    def blocking_stop(self):
        """Stops and waits for the thread to finish. Used on app exit."""
        self.disconnect_vpn()
        if self.runner:
            self.runner.wait(2000) # Wait up to 2 seconds


    def _on_output(self, text):
        self.log_message.emit(text)
        
        # Parse Info
        m_iface = self.re_interface.search(text)
        if m_iface:
            self.session_data["interface"] = m_iface.group(1)
            self.vpn_interface = m_iface.group(1)
            
        m_local = self.re_local_ip.search(text)
        if m_local:
            self.session_data["local_ip"] = m_local.group(1)
            
        m_remote = self.re_remote_ip.search(text)
        if m_remote:
            self.session_data["remote_ip"] = m_remote.group(1)

        if "Tunnel is up and running" in text:
            self.state_changed.emit("connected")
            self.connection_details_received.emit(self.session_data)
            if self.vpn_interface:
                self.stats_timer.start()

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
        except:
            pass # Interface might be gone or perm issue
            
    def _on_cert_error(self, cert_hash):
        self.is_user_disconnected = True 
        if self.runner:
            self.runner.stop()
        self.state_changed.emit("disconnected")
        self.cert_trust_needed.emit(cert_hash)

    def _on_finished(self, code):
        self.runner = None
        self.stats_timer.stop()
        
        if self.is_user_disconnected:
            self.state_changed.emit("disconnected")
        elif code != 0:
            self.log_message.emit(f"Gateway falló con código {code}. Intentando siguiente...")
            self.state_changed.emit("failover")
            self.current_attempt_index += 1
            QTimer.singleShot(1000, self._start_attempt)
        else:
            self.state_changed.emit("disconnected")

