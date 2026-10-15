from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame)
from PySide6.QtCore import Qt


class StatsPanel(QFrame):
    """
    Panel de monitoreo de red en tiempo real para sesiones VPN (SSL e IPSec).
    Muestra IPs locales/remotas, enlace/interfaz, DNS y tasas acumuladas de RX/TX.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Grilla de Detalles de Red
        details_layout = QHBoxLayout()

        self.lbl_local_ip = QLabel("Local: -")
        self.lbl_remote_ip = QLabel("Remote: -")
        self.lbl_gateway = QLabel("Enlace: -")

        for lbl in [self.lbl_local_ip, self.lbl_remote_ip, self.lbl_gateway]:
            lbl.setStyleSheet("font-size: 11px; color: #b0bec5;")

        details_layout.addWidget(self.lbl_local_ip)
        details_layout.addWidget(self.lbl_remote_ip)
        details_layout.addWidget(self.lbl_gateway)
        layout.addLayout(details_layout)

        # Línea de Servidores DNS
        self.lbl_dns = QLabel("DNS: -")
        self.lbl_dns.setStyleSheet("font-size: 11px; color: #90a4ae;")
        layout.addWidget(self.lbl_dns)

        # Contadores de Tráfico (RX / TX)
        traffic_layout = QHBoxLayout()
        self.lbl_rx = QLabel("↓ 0 B")
        self.lbl_tx = QLabel("↑ 0 B")

        self.lbl_rx.setStyleSheet("color: #00e676; font-weight: bold; font-size: 12px;")
        self.lbl_tx.setStyleSheet("color: #2979ff; font-weight: bold; font-size: 12px;")

        traffic_layout.addWidget(self.lbl_rx)
        traffic_layout.addWidget(self.lbl_tx)
        layout.addLayout(traffic_layout)

        self.hide()

    def update_details(self, data: dict):
        iface = data.get('interface', '-')
        if iface and iface.startswith("sa:"):
            display_iface = f"IPSec ({iface})"
        elif iface:
            display_iface = f"SSL ({iface})"
        else:
            display_iface = "-"

        self.lbl_local_ip.setText(f"Local: {data.get('local_ip', '-')}")
        self.lbl_remote_ip.setText(f"Remote: {data.get('remote_ip', '-')}")
        self.lbl_gateway.setText(f"Enlace: {display_iface}")
        self.lbl_dns.setText(f"DNS: {data.get('dns', '-')}")
        self.show()

    def update_traffic(self, rx: int, tx: int):
        self.lbl_rx.setText(f"↓ {self._format_bytes(rx)}")
        self.lbl_tx.setText(f"↑ {self._format_bytes(tx)}")

    def _format_bytes(self, size: float) -> str:
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size >= power and n < 4:
            size /= power
            n += 1
        return f"{size:.1f} {power_labels.get(n, '')}B"

    def reset(self):
        self.lbl_local_ip.setText("Local: -")
        self.lbl_remote_ip.setText("Remote: -")
        self.lbl_gateway.setText("Enlace: -")
        self.lbl_dns.setText("DNS: -")
        self.update_traffic(0, 0)
        self.hide()
