import sys
import os

# Asegurar que el directorio src/ esté en sys.path
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import subprocess
import time
import logging
import pwd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel,
    QComboBox, QMessageBox, QHBoxLayout, QInputDialog, QLineEdit, QDialog,
    QTextEdit, QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QIcon, QPixmap, QAction
from PySide6.QtCore import Qt, QTimer
from vpn_manager import VPNManager
from profile_manager import ProfileManager
from config_dialog import ConfigDialog
from stats_panel import StatsPanel
from styles import apply_dark_theme
import migration_utils


class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs de Conexión - VPN GNA")
        self.resize(650, 420)
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: monospace; font-size: 10px; background: #222; color: #eee;")
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def append_log(self, text: str):
        self.text_edit.append(text)
        sb = self.text_edit.verticalScrollBar()
        sb.setValue(sb.maximum())


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayuda - VPN GNA")
        self.resize(520, 420)
        layout = QVBoxLayout()

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml("""
            <h2>VPN GNA (Cliente Dual SSL / IPSec)</h2>
            <p>Cliente unificado oficial para conexiones remotas seguras a los concentradores de Gendarmería Nacional Argentina.</p>
            
            <h3>Soporte Dual (SSL e IPSec)</h3>
            <ul>
                <li><b>IPSec (strongSwan):</b> Nueva tecnología estándar IKEv2 con autenticación EAP para la migración de concentradores.</li>
                <li><b>SSL (openfortivpn):</b> Compatibilidad con concentradores Fortinet tradicionales.</li>
            </ul>

            <h3>Primeros Pasos</h3>
            <ol>
                <li><b>Configurar Perfil:</b> Clic en el engranaje (⚙) y selecciona "Nuevo Perfil".</li>
                <li><b>Elegir Tipo:</b> Selecciona si la sede destino utiliza IPSec o SSL.</li>
                <li><b>Credenciales:</b> Ingresa tu usuario institucional. La contraseña se almacena de forma segura en el llavero del sistema.</li>
                <li><b>Doble Factor (2FA / FortiToken):</b> Si tu cuenta requiere token, activa la casilla de verificación y se solicitará el código al conectar.</li>
            </ol>
            
            <h3>Failover de Servidores</h3>
            <p>Puedes agregar múltiples direcciones de concentrador en un mismo perfil. Si el primero no responde, la aplicación conmutará automáticamente al siguiente.</p>
        """)
        layout.addWidget(text_edit)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("VPN GNA")
        self.resize(420, 560)

        # Icono de la aplicación
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "vpn_gna_icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "openfortivpn_isologo.png")

        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()

        # Gestores
        self.vpn_manager = VPNManager(self)
        self.profile_manager = ProfileManager()
        self._force_quit = False

        # Temporizador de conexión
        self.connection_timer = QTimer(self)
        self.connection_timer.setInterval(1000)
        self.connection_timer.timeout.connect(self.update_connection_time)
        self.connection_start_time = None

        # Diálogo de logs
        self.log_dialog = LogDialog(self)

        # Bandeja del sistema
        self.init_system_tray()

        # Interfaz de usuario
        self.setup_ui()

        # Conectar señales del VPNManager
        self.vpn_manager.state_changed.connect(self.on_vpn_state_changed)
        self.vpn_manager.log_message.connect(self.on_log_message)
        self.vpn_manager.connection_failed.connect(self.on_connection_failed)
        self.vpn_manager.cert_trust_needed.connect(self.on_cert_trust_needed)
        self.vpn_manager.connection_details_received.connect(self.on_connection_details)
        self.vpn_manager.traffic_stats_updated.connect(self.on_traffic_updated)

        # Migración automática de ofvpn-gui a vpn-gna en el primer inicio
        migration_utils.migrate_ofvpn_gui_to_vpn_gna()
        self.update_profile_combo()

        # Chequeo de archivos legacy (/etc/openfortivpn/config)
        QTimer.singleShot(1000, self.check_migrations)

    def check_migrations(self):
        legacy = migration_utils.detect_legacy_configs()
        if not legacy:
            return

        msg = "Se han detectado configuraciones antiguas en disco:\n\n"
        insecure_count = 0
        for item in legacy:
            msg += f"- {item['path']}"
            if item['has_password']:
                msg += " [ALERTA: Contraseña en texto plano]"
                insecure_count += 1
            msg += "\n"

        msg += "\n¿Desea importarlas al almacenamiento seguro de VPN-GNA?"

        box = QMessageBox(self)
        box.setWindowTitle("Migración de Configuraciones")
        box.setText(msg)
        box.setIcon(QMessageBox.Warning if insecure_count else QMessageBox.Information)

        btn_migrate = box.addButton("Migrar", QMessageBox.AcceptRole)
        btn_delete = box.addButton("Eliminar Archivos", QMessageBox.DestructiveRole)
        box.addButton("Ignorar", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() == btn_migrate:
            imported = 0
            for item in legacy:
                c = item['content']
                if 'host' in c and 'username' in c:
                    gateways = [{'host': c['host'], 'port': int(c.get('port', 443))}]
                    name = f"Imported_{os.path.basename(item['path'])}"
                    self.profile_manager.add_profile(
                        name=name,
                        username=c['username'],
                        password=c.get('password', ''),
                        trusted_cert=c.get('trusted-cert', ''),
                        gateways=gateways,
                        otp_enabled=False,
                        vpn_type="ssl"
                    )
                    imported += 1

            QMessageBox.information(self, "Migración", f"Se importaron {imported} perfiles.")
            self.update_profile_combo()

            reply = QMessageBox.question(self, "Limpieza", "¿Desea eliminar los archivos de texto plano originales?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                for item in legacy:
                    migration_utils.secure_delete(item['path'])

        elif box.clickedButton() == btn_delete:
            for item in legacy:
                migration_utils.secure_delete(item['path'])
            QMessageBox.information(self, "Limpieza", "Archivos eliminados.")

    def send_notification(self, title: str, message: str, urgency: str = "normal"):
        sudo_user = os.environ.get('SUDO_USER')
        sudo_uid = os.environ.get('SUDO_UID')

        if sudo_user and sudo_uid:
            try:
                dbus_address = f"unix:path=/run/user/{sudo_uid}/bus"
                display = os.environ.get('DISPLAY', ':0')
                cmd = [
                    "sudo", "-u", sudo_user,
                    "env",
                    f"DBUS_SESSION_BUS_ADDRESS={dbus_address}",
                    f"DISPLAY={display}",
                    "notify-send", "-u", urgency, "-a", "VPN GNA", title, message
                ]
                subprocess.Popen(cmd)
            except Exception:
                self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)
        else:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)

        tray_menu = QMenu()
        self.action_show = QAction("Mostrar / Ocultar", self)
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

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Selector de Perfil
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.update_profile_combo()
        profile_layout.addWidget(QLabel("Perfil:"))
        profile_layout.addWidget(self.profile_combo)

        config_btn = QPushButton("⚙")
        config_btn.setFixedWidth(32)
        config_btn.setToolTip("Gestionar Perfiles")
        config_btn.clicked.connect(self.open_config)
        profile_layout.addWidget(config_btn)

        help_btn = QPushButton("?")
        help_btn.setFixedWidth(32)
        help_btn.setToolTip("Ayuda")
        help_btn.clicked.connect(self.show_help)
        profile_layout.addWidget(help_btn)

        layout.addLayout(profile_layout)

        # Branding (Logo e Identidad VPN-GNA)
        logo_layout = QVBoxLayout()
        logo_lbl = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "vpn_gna_icon.png")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", "openfortivpn_isologo.png")

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            pixmap = pixmap.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pixmap)
            logo_lbl.setAlignment(Qt.AlignCenter)
            logo_layout.addWidget(logo_lbl)

        title_lbl = QLabel("VPN GNA — Gendarmería Nacional")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("font-size: 12px; color: #aaa; font-weight: bold; margin-top: 4px; margin-bottom: 15px;")
        logo_layout.addWidget(title_lbl)
        layout.addLayout(logo_layout)

        # Estado de la conexión
        self.status_label = QLabel("Desconectado")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; margin-top: 5px; margin-bottom: 2px;")
        layout.addWidget(self.status_label)

        # Indicador visual del usuario conectado (REQUERIMIENTO EXPLÍCITO)
        self.user_label = QLabel("")
        self.user_label.setAlignment(Qt.AlignCenter)
        self.user_label.setStyleSheet("font-size: 13px; color: #64b5f6; font-weight: bold; margin-bottom: 6px;")
        self.user_label.hide()
        layout.addWidget(self.user_label)

        # Temporizador de tiempo transcurrido
        self.timer_label = QLabel("")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 13px; color: #81c784; font-weight: bold; margin-bottom: 8px;")
        self.timer_label.hide()
        layout.addWidget(self.timer_label)

        # Botón principal de Conexión
        self.connect_button = QPushButton("Conectar")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.connect_button.setStyleSheet("font-size: 16px; padding: 14px; font-weight: bold;")
        layout.addWidget(self.connect_button)

        # Panel de Estadísticas de Tráfico
        self.stats_panel = StatsPanel()
        layout.addWidget(self.stats_panel)

        # Barra inferior (Ver Logs)
        tools_layout = QHBoxLayout()
        tools_layout.addStretch()
        logs_btn = QPushButton("Ver Logs")
        logs_btn.clicked.connect(self.show_logs)
        tools_layout.addWidget(logs_btn)
        layout.addLayout(tools_layout)

    def on_log_message(self, text: str):
        self.log_dialog.append_log(text)
        logging.info(text)

    def on_connection_details(self, data: dict):
        self.stats_panel.update_details(data)
        # Asegurar actualización de usuario en UI
        username = data.get("username")
        if username and username != "N/A" and self.connect_button.isChecked():
            self.user_label.setText(f"👤 Usuario: {username}")
            self.user_label.show()

    def on_traffic_updated(self, rx: int, tx: int):
        self.stats_panel.update_traffic(rx, tx)

    def update_connection_time(self):
        if self.connection_start_time is None:
            return
        elapsed = int(time.time() - self.connection_start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.timer_label.setText(f"Tiempo transcurrido: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def start_connection_timer(self):
        self.connection_start_time = time.time()
        self.update_connection_time()
        self.timer_label.show()
        self.connection_timer.start()

    def stop_connection_timer(self):
        if self.connection_timer.isActive():
            self.connection_timer.stop()
        self.connection_start_time = None
        self.timer_label.setText("")
        self.timer_label.hide()

    def update_profile_combo(self):
        current_id = self.profile_combo.currentData()
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        for p in profiles:
            vpn_type = p.get('vpn_type', 'ssl').upper()
            display_name = f"[{vpn_type}] {p['name']}"
            self.profile_combo.addItem(display_name, p['id'])

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

            profile = self.profile_manager.get_profile(profile_id)
            if not profile:
                self.connect_button.setChecked(False)
                return

            runtime_password = profile.get('password')
            runtime_otp = None

            # 1. Solicitar contraseña si no está almacenada en el Keyring
            if not runtime_password:
                pwd, ok = QInputDialog.getText(
                    self, "Contraseña Requerida",
                    f"Contraseña para {profile['username']}:", QLineEdit.Password
                )
                if ok and pwd:
                    runtime_password = pwd
                else:
                    self.connect_button.setChecked(False)
                    return

            # 2. Solicitar Clave Pre-compartida (PSK) si es perfil IPSec y no está en Keyring
            if profile.get('vpn_type') == 'ipsec':
                runtime_psk = profile.get('preshared_key')
                if not runtime_psk:
                    psk, ok = QInputDialog.getText(
                        self, "Clave Pre-compartida Requerida (PSK)",
                        f"Ingrese la Clave Pre-compartida (PSK) de la VPN IPSec:", QLineEdit.Password
                    )
                    if ok and psk.strip():
                        runtime_psk = psk.strip()
                        profile['preshared_key'] = runtime_psk
                        self.profile_manager.save_psk(profile['id'], runtime_psk)
                    else:
                        self.connect_button.setChecked(False)
                        return

            # 3. Solicitar OTP / Doble Factor si el perfil lo requiere
            if profile.get('otp_enabled'):
                otp, ok = QInputDialog.getText(
                    self, "Doble Factor Requerido (2FA)",
                    f"Ingrese código OTP / FortiToken para {profile['username']}:", QLineEdit.Normal
                )
                if ok and otp:
                    runtime_otp = otp.strip()
                else:
                    self.connect_button.setChecked(False)
                    return

            try:
                self.vpn_manager.connect_vpn(
                    profile,
                    password=runtime_password,
                    otp=runtime_otp,
                    dns_domain=profile.get('dns_domain', "")
                )
            except Exception as e:
                QMessageBox.critical(self, "Error al Conectar", str(e))
                self.connect_button.setChecked(False)
        else:
            self.vpn_manager.disconnect_vpn()

    def on_connection_failed(self, reason: str):
        self.stop_connection_timer()
        self.user_label.hide()
        self.user_label.setText("")

        QMessageBox.warning(self, "Fallo de Conexión", reason)
        self.connect_button.setChecked(False)
        self.status_label.setText("Fallo de Conexión")
        self.status_label.setStyleSheet("color: #f44336; font-size: 14px; margin: 10px;")
        self.connect_button.setText("Conectar")
        self.connect_button.setEnabled(True)
        self.connect_button.setStyleSheet("font-size: 16px; padding: 14px; font-weight: bold;")
        self.stats_panel.reset()
        self.send_notification("Fallo de Conexión", reason, "critical")

    def on_cert_trust_needed(self, cert_hash: str):
        self.stop_connection_timer()
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return

        reply = QMessageBox.question(
            self,
            "Certificado No Confiable",
            f"El gateway presentó un certificado nuevo.\nHash SHA256: {cert_hash}\n\n¿Desea confiar en este certificado y registrarlo en el perfil?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.profile_manager.update_profile(profile_id, {'trusted_cert': cert_hash})
            QMessageBox.information(self, "Actualizado", "Certificado registrado. Presione Conectar para ingresar.")

        self.connect_button.setChecked(False)
        self.status_label.setText("Certificado Actualizado" if reply == QMessageBox.Yes else "Conexión Cancelada")
        self.status_label.setStyleSheet("color: orange; font-size: 14px; margin: 10px;")
        self.connect_button.setText("Conectar")
        self.connect_button.setEnabled(True)
        self.stats_panel.reset()

    def on_vpn_state_changed(self, state: str):
        if state == "connecting":
            self.stop_connection_timer()
            self.user_label.hide()
            self.user_label.setText("")
            self.status_label.setText("Conectando...")
            self.status_label.setStyleSheet("color: #ff9800; font-size: 14px; margin: 10px;")
            self.connect_button.setText("Cancelar")
            self.connect_button.setEnabled(True)
            self.connect_button.setStyleSheet("background-color: #ff9800; color: white; font-size: 16px; padding: 14px; font-weight: bold; border-radius: 5px;")
            self.stats_panel.reset()

        elif state == "failover":
            self.stop_connection_timer()
            self.user_label.hide()
            self.user_label.setText("")
            self.status_label.setText("Reintentando con Gateway de Respaldo...")
            self.status_label.setStyleSheet("color: #ff9800; font-size: 14px; margin: 10px;")
            self.connect_button.setStyleSheet("background-color: #ff9800; color: white; font-size: 16px; padding: 14px; font-weight: bold; border-radius: 5px;")
            self.send_notification("Failover", "Cambiando a servidor de respaldo...", "critical")

        elif state == "connected":
            profile_id = self.profile_combo.currentData()
            gateway_host = "VPN"
            vpn_type = "SSL"
            username = self.vpn_manager.get_connected_username()

            if profile_id:
                profile = self.profile_manager.get_profile(profile_id)
                if profile:
                    vpn_type = profile.get('vpn_type', 'ssl').upper()
                    if not username or username == "N/A":
                        username = profile.get('username', '')
                    gateways = profile.get('gateways', [])
                    if self.vpn_manager.current_attempt_index < len(gateways):
                        gateway_host = f"{gateways[self.vpn_manager.current_attempt_index]['host']}"

            self.status_label.setText(f"CONECTADO A {gateway_host} ({vpn_type})")
            self.status_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 14px; margin-top: 8px; margin-bottom: 2px;")

            # Mostrar el usuario conectado en la GUI
            if username and username != "N/A":
                self.user_label.setText(f"👤 Usuario: {username}")
                self.user_label.show()
            else:
                self.user_label.hide()

            self.connect_button.setText("Desconectar")
            self.connect_button.setChecked(True)
            self.connect_button.setStyleSheet("background-color: #f44336; color: white; font-size: 16px; padding: 14px; font-weight: bold; border-radius: 5px;")
            self.start_connection_timer()
            self.send_notification("Conectado", f"Conexión {vpn_type} establecida con {gateway_host} como {username}")
            self.tray_icon.setToolTip(f"VPN GNA: Conectado a {gateway_host} ({username})")

        elif state == "disconnected":
            self.stop_connection_timer()
            self.user_label.hide()
            self.user_label.setText("")
            self.status_label.setText("Desconectado")
            self.status_label.setStyleSheet("color: #cccccc; font-size: 14px; margin: 10px;")
            self.connect_button.setText("Conectar")
            self.connect_button.setChecked(False)
            self.connect_button.setStyleSheet("font-size: 16px; padding: 14px; font-weight: bold;")
            self.stats_panel.reset()
            self.tray_icon.setToolTip("VPN GNA: Desconectado")

    def show_logs(self):
        self.log_dialog.show()

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def quit_app(self):
        self.stop_connection_timer()
        self._force_quit = True
        self.vpn_manager.blocking_stop()
        QApplication.quit()

    def closeEvent(self, event):
        if getattr(self, '_force_quit', False):
            self.vpn_manager.blocking_stop()
            event.accept()
        elif self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.vpn_manager.blocking_stop()
            event.accept()


def setup_logging():
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            home_dir = pwd.getpwnam(sudo_user).pw_dir
        except Exception:
            home_dir = os.path.expanduser("~")
    else:
        home_dir = os.path.expanduser("~")

    log_dir = os.path.join(home_dir, ".config/vpn-gna")
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, mode=0o700, exist_ok=True)
        except Exception:
            log_dir = "/tmp"

    log_file = os.path.join(log_dir, "debug.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def main():
    setup_logging()
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    app.setApplicationName("VPN GNA")
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()

    if "--minimized" in sys.argv:
        window.hide()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
