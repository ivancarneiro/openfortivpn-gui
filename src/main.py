import sys
import os
import subprocess
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                               QWidget, QLabel, QComboBox, QMessageBox, QHBoxLayout,
                               QInputDialog, QLineEdit, QDialog, QTextEdit, QSystemTrayIcon,
                               QMenu)
from PySide6.QtGui import QIcon, QPixmap, QAction, QPainter, QColor
from PySide6.QtCore import Qt, QSize
from vpn_manager import VPNManager
from profile_manager import ProfileManager
from config_dialog import ConfigDialog
from stats_panel import StatsPanel

class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs de Conexión (Verbose)")
        self.resize(600, 400)
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: monospace; font-size: 10px; background: #222; color: #eee;")
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def append_log(self, text):
        self.text_edit.append(text)
        # Auto scroll
        sb = self.text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayuda - ofvpn-gui")
        self.resize(500, 400)
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml("""
            <h2>Bienvenido a OpenFortiVPN GUI</h2>
            <p>Esta aplicación te permite conectar a VPNs Fortinet de forma sencilla.</p>
            
            <h3>Primeros Pasos</h3>
            <ol>
                <li><b>Crear un Perfil:</b> Haz clic en el botón de engranaje (⚙) y selecciona "Nuevo Perfil".</li>
                <li><b>Configurar:</b> Ingresa un nombre, tu usuario y añade al menos un Gateway (Host y Puerto).</li>
                <li><b>Gateways Múltiples:</b> Puedes añadir varios servidores. Si el primero falla, se intentará el siguiente automáticamente.</li>
            </ol>
            
            <h3>Certificados (Trusted Cert)</h3>
            <p>La primera vez que conectas, o si el certificado del servidor cambia, verás un error de <i>"Trusted cert..."</i>. 
            La aplicación detectará esto automáticamente y te preguntará si confías en el nuevo certificado para actualizar tu perfil.</p>
            
            <h3>OTP / 2FA</h3>
            <p>Si tu VPN requiere un token (OTP), marca la casilla "Conexión requiere OTP" en el perfil. Se te pedirá el código al conectar.</p>
        """)
        layout.addWidget(text_edit)
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ofvpn-gui")
        self.resize(400, 550) # Taller for logos
        
        # Use fortivpn2.png (512x512) for Window/Tray Icon as it is square and higher res
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fortivpn2.png")
        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()
        
        # Managers
        self.vpn_manager = VPNManager()
        self.profile_manager = ProfileManager()
        
        # Log Dialog
        self.log_dialog = LogDialog(self)
        
        # System Tray
        self.init_system_tray()

        # UI
        self.setup_ui()
        
        # Signals
        self.vpn_manager.state_changed.connect(self.on_vpn_state_changed)
        self.vpn_manager.log_message.connect(self.on_log_message)
        self.vpn_manager.connection_failed.connect(self.on_connection_failed)
        self.vpn_manager.cert_trust_needed.connect(self.on_cert_trust_needed)
        self.vpn_manager.connection_details_received.connect(self.on_connection_details)
        self.vpn_manager.traffic_stats_updated.connect(self.on_traffic_updated)

    def send_notification(self, title, message, urgency="normal"):
        """Sends a native notification using notify-send as the logged-in user."""
        sudo_user = os.environ.get('SUDO_USER')
        sudo_uid = os.environ.get('SUDO_UID')
        
        if sudo_user and sudo_uid:
            try:
                # Construct connection to user's DBus
                # This assumes standard systemd-logind session bus location
                dbus_address = f"unix:path=/run/user/{sudo_uid}/bus"
                display = os.environ.get('DISPLAY', ':0')
                
                # Command: sudo -u user env VAR=VAL notify-send ...
                cmd = [
                    "sudo", "-u", sudo_user, 
                    "env", 
                    f"DBUS_SESSION_BUS_ADDRESS={dbus_address}", 
                    f"DISPLAY={display}",
                    "notify-send", "-u", urgency, "-a", "OpenFortiVPN GUI", title, message
                ]
                
                subprocess.Popen(cmd)
            except Exception as e:
                print(f"Failed to send notification: {e}")
                # Fallback to Qt tray message if native fails
                self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)
        else:
            # Fallback for direct root login or missing sudo env
             self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Use window icon or specific tray icon
        self.tray_icon.setIcon(self.app_icon)
        
        # Menu
        tray_menu = QMenu()
        
        self.action_show = QAction("Mostrar/Ocultar", self)
        self.action_show.triggered.connect(self.toggle_window)
        tray_menu.addAction(self.action_show)
        
        tray_menu.addSeparator()
        
        self.action_quit = QAction("Salir", self)
        self.action_quit.triggered.connect(self.quit_app)
        tray_menu.addAction(self.action_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window()

    def quit_app(self):
        # Explicit quit from Tray
        self.vpn_manager.blocking_stop()
        QApplication.quit()

    def setup_ui(self):
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Profile Selector
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.update_profile_combo()
        profile_layout.addWidget(QLabel("Perfil:"))
        profile_layout.addWidget(self.profile_combo)
        
        config_btn = QPushButton("⚙")
        config_btn.setFixedWidth(30)
        config_btn.setToolTip("Configurar Perfiles")
        config_btn.clicked.connect(self.open_config)
        profile_layout.addWidget(config_btn)

        help_btn = QPushButton("?")
        help_btn.setFixedWidth(30)
        help_btn.setToolTip("Ayuda")
        help_btn.clicked.connect(self.show_help)
        profile_layout.addWidget(help_btn)
        
        layout.addLayout(profile_layout)
        
        # Branding (Logo)
        logo_layout = QVBoxLayout()
        logo_lbl = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fortivpn2.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Resize bigger (200)
            pixmap = pixmap.scaledToWidth(200, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
            logo_lbl.setAlignment(Qt.AlignCenter)
            logo_layout.addWidget(logo_lbl)
            
        title_lbl = QLabel("OpenFortiVPN by ciex")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("font-size: 11px; color: #888; margin-bottom: 20px;")
        logo_layout.addWidget(title_lbl)
        layout.addLayout(logo_layout)

        # Status Label
        self.status_label = QLabel("Desconectado")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; margin: 10px;")
        layout.addWidget(self.status_label)

        # Connect Button
        self.connect_button = QPushButton("Conectar")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.connect_button.setStyleSheet("font-size: 16px; padding: 15px; font-weight: bold;")
        layout.addWidget(self.connect_button)
        
        # Traffic Stats Panel
        self.stats_panel = StatsPanel()
        layout.addWidget(self.stats_panel)
        
        # Tools Layout (Logs)
        tools_layout = QHBoxLayout()
        tools_layout.addStretch()
        
        log_btn = QPushButton("Ver Logs")
        log_btn.clicked.connect(self.show_logs)
        log_btn.setStyleSheet("font-size: 10px;")
        tools_layout.addWidget(log_btn)
        
        layout.addLayout(tools_layout)
        
    def show_logs(self):
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()
        
    def on_log_message(self, text):
        print(text) # Still print to stdout
        self.log_dialog.append_log(text)

    def on_connection_details(self, data):
        self.stats_panel.update_details(data)

    def on_traffic_updated(self, rx, tx):
        self.stats_panel.update_traffic(rx, tx)

    def update_profile_combo(self):
        current_id = self.profile_combo.currentData()
        self.profile_combo.clear()
        
        profiles = self.profile_manager.get_profiles()
        if not profiles:
            self.profile_combo.addItem("Sin perfiles", None)
            return

        for p in profiles:
            self.profile_combo.addItem(p['name'], p['id'])
        
        # Restore selection if possible
        if current_id:
            index = self.profile_combo.findData(current_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)

    def open_config(self):
        dialog = ConfigDialog(self.profile_manager, self)
        dialog.exec()
        self.update_profile_combo()

    def toggle_connection(self):
        if self.connect_button.isChecked():
            profile_id = self.profile_combo.currentData()
            if not profile_id:
                QMessageBox.warning(self, "Error", "Selecciona o crea un perfil primero.")
                self.connect_button.setChecked(False)
                return

            # Retrieve profile to check requirements
            profile = next((p for p in self.profile_manager.get_profiles() if p['id'] == profile_id), None)
            if not profile:
                 return

            runtime_password = None
            runtime_otp = None

            # Check if password is empty -> Prompt
            if not profile.get('password'):
                pwd, ok = QInputDialog.getText(self, "Contraseña Requerida", 
                                               f"Contraseña para {profile['username']}:", QLineEdit.Password)
                if ok and pwd:
                    runtime_password = pwd
                else:
                    self.connect_button.setChecked(False)
                    return # User cancelled

            # Check if OTP is enabled -> Prompt
            if profile.get('otp_enabled'):
                otp, ok = QInputDialog.getText(self, "OTP Requerido", 
                                               "Ingrese código OTP/Token:", QLineEdit.Normal)
                if ok and otp:
                    runtime_otp = otp
                else:
                    self.connect_button.setChecked(False)
                    return # User cancelled

            try:
                # Generate all configs for failover with runtime creds
                config_paths = self.profile_manager.generate_all_openfortivpn_configs(
                    profile_id, 
                    runtime_password=runtime_password,
                    runtime_otp=runtime_otp
                )
                self.vpn_manager.connect_vpn(config_paths)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                self.connect_button.setChecked(False)
        else:
            self.vpn_manager.disconnect_vpn()

    def on_connection_failed(self, reason):
        QMessageBox.warning(self, "Fallo de Conexión", reason)
        self.connect_button.setChecked(False)
        self.status_label.setText("Fallo de Conexión")
        self.status_label.setStyleSheet("color: red; font-size: 14px; margin: 10px;")
        self.connect_button.setText("Conectar")
        self.connect_button.setEnabled(True)
        self.stats_panel.reset()
        self.send_notification("Fallo de Conexión", reason, "critical")

    def on_cert_trust_needed(self, cert_hash):
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return

        reply = QMessageBox.question(
            self, 
            "Certificado No Confiable", 
            f"El gateway presentó un certificado nuevo.\nHash: {cert_hash}\n\n¿Desea confiar en este certificado y actualizar el perfil?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Update profile with new cert
            self.profile_manager.update_profile(profile_id, {'trusted_cert': cert_hash})
            QMessageBox.information(self, "Actualizado", "Certificado actualizado. Intente conectar nuevamente.")
        
        self.connect_button.setChecked(False)
        self.status_label.setText("Certificado Actualizado" if reply == QMessageBox.Yes else "Conexión Cancelada")
        self.status_label.setStyleSheet("color: orange; font-size: 14px; margin: 10px;")
        self.connect_button.setText("Conectar")
        self.connect_button.setEnabled(True)
        self.stats_panel.reset()

    def on_vpn_state_changed(self, state):

        if state == "connecting":
            self.status_label.setText("Conectando...")
            self.connect_button.setText("Cancelar")
            self.connect_button.setEnabled(True)
            self.connect_button.setStyleSheet("background-color: #ff9800; color: white; font-size: 16px; padding: 15px; font-weight: bold; border-radius: 5px;")
            self.stats_panel.reset()
        elif state == "failover":
             self.status_label.setText("Reintentando (Failover)...")
             self.status_label.setStyleSheet("color: #ff9800; font-size: 14px; margin: 10px;")
             self.connect_button.setStyleSheet("background-color: #ff9800; color: white; font-size: 16px; padding: 15px; font-weight: bold; border-radius: 5px;")
             self.send_notification("Failover", "Cambiando a servidor de respaldo...", "critical")
        elif state == "connected":
            # Get Gateway info
            profile_id = self.profile_combo.currentData()
            gateway_host = "VPN" # Default
            if profile_id:
                 profile = next((p for p in self.profile_manager.get_profiles() if p['id'] == profile_id), None)
                 if profile and self.vpn_manager.current_attempt_index < len(profile['gateways']):
                     gateway = profile['gateways'][self.vpn_manager.current_attempt_index]
                     gateway_host = f"{gateway['host']}"

            self.status_label.setText(f"CONECTADO A {gateway_host}")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 14px; margin: 10px;")
            self.connect_button.setText("Desconectar")
            self.connect_button.setChecked(True)
            self.connect_button.setStyleSheet("background-color: #f44336; color: white; font-size: 16px; padding: 15px; font-weight: bold; border-radius: 5px;")
            self.send_notification("Conectado", f"Conexión establecida con {gateway_host}")
            self.tray_icon.setToolTip(f"ofvpn-gui: Conectado a {gateway_host}")
        elif state == "disconnected":
            # Only reset if not handled by failed handler
            self.status_label.setText("Desconectado")
            self.status_label.setStyleSheet("color: #cccccc; font-size: 14px; margin: 10px;")
            self.connect_button.setText("Conectar")
            self.connect_button.setChecked(False)
            # Reset style to default (or explicit gray)
            self.connect_button.setStyleSheet("font-size: 16px; padding: 15px; font-weight: bold;") 
            self.stats_panel.reset()
            self.tray_icon.setToolTip("ofvpn-gui: Desconectado")

    def show_logs(self):
        self.log_dialog.show()

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting
        if self.tray_icon.isVisible():
            self.hide()
            self.send_notification("OpenFortiVPN GUI", "La aplicación sigue ejecutándose en segundo plano.")
            event.ignore()
        else:
            # Fallback quit
            self.vpn_manager.blocking_stop()
            event.accept()

from styles import apply_dark_theme

if __name__ == "__main__":
    # Inject DBUS session for keyring if running as sudo
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        # Construct the user's DBus session address
        # This assumes standard systemd location: /run/user/<uid>/bus
        dbus_address = f"unix:path=/run/user/{sudo_uid}/bus"
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = dbus_address
        # Also ensure HOME is set to user's home for some tools? 
        # ProfileManager handles config dir manually, but keyring might need it?
        # Usually DBUS address is enough for Secret Service.

    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
