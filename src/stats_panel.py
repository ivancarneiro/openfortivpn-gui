from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton)
from PySide6.QtCore import Qt

class StatsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Details Grid
        details_layout = QHBoxLayout()
        
        self.lbl_local_ip = QLabel("Local IP: -")
        self.lbl_remote_ip = QLabel("Remote IP: -")
        self.lbl_gateway = QLabel("Interface: -")
        
        # Styling
        for lbl in [self.lbl_local_ip, self.lbl_remote_ip, self.lbl_gateway]:
             lbl.setStyleSheet("font-size: 10px; color: #cccccc;") # Lighter gray
        
        details_layout.addWidget(self.lbl_local_ip)
        details_layout.addWidget(self.lbl_remote_ip)
        details_layout.addWidget(self.lbl_gateway)
        
        layout.addLayout(details_layout)
        
        # Traffic Split
        traffic_layout = QHBoxLayout()
        self.lbl_rx = QLabel("↓ 0 B")
        self.lbl_tx = QLabel("↑ 0 B")
        
        # Brighter colors for dark mode
        self.lbl_rx.setStyleSheet("color: #00e676; font-weight: bold;") # Bright Green
        self.lbl_tx.setStyleSheet("color: #2979ff; font-weight: bold;") # Bright Blue
        
        traffic_layout.addWidget(self.lbl_rx)
        traffic_layout.addWidget(self.lbl_tx)
        
        layout.addLayout(traffic_layout)
        
        self.hide() # Hidden by default until connected

    def update_details(self, data):
        self.lbl_local_ip.setText(f"Local: {data.get('local_ip', '-')}")
        self.lbl_remote_ip.setText(f"Remote: {data.get('remote_ip', '-')}")
        self.lbl_gateway.setText(f"Iface: {data.get('interface', '-')}")
        self.show()

    def update_traffic(self, rx, tx):
        self.lbl_rx.setText(f"↓ {self._format_bytes(rx)}")
        self.lbl_tx.setText(f"↑ {self._format_bytes(tx)}")

    def _format_bytes(self, size):
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.1f} {power_labels.get(n, '')}B"

    def reset(self):
        self.lbl_local_ip.setText("Local IP: -")
        self.lbl_remote_ip.setText("Remote IP: -")
        self.lbl_gateway.setText("Interface: -")
        self.update_traffic(0, 0)
        self.hide()
