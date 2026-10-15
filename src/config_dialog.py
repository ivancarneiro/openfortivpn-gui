import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QMessageBox,
    QLabel, QInputDialog, QCheckBox, QListWidgetItem, QFormLayout, QLineEdit,
    QComboBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
try:
    from profile_manager import ProfileManager
except ImportError:
    from src.profile_manager import ProfileManager


class ProfileEditorDialog(QDialog):
    """
    Diálogo para crear y editar perfiles de conexión con soporte dual (SSL e IPSec).
    """

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Perfil" if profile else "Nuevo Perfil")
        self.resize(480, 520)

        layout = QFormLayout()

        # Selector de Tipo de VPN (Dual Engine)
        self.type_combo = QComboBox()
        self.type_combo.addItem("SSL (OpenFortiVPN)", "ssl")
        self.type_combo.addItem("IPSec (strongSwan)", "ipsec")

        current_type = profile.get('vpn_type', 'ssl') if profile else 'ssl'
        idx = self.type_combo.findData(current_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

        self.name_edit = QLineEdit(profile['name'] if profile else "")
        self.user_edit = QLineEdit(profile['username'] if profile else "")

        self.pass_edit = QLineEdit(profile['password'] if profile else "")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("(Opcional - se solicitará en cada conexión si se deja vacío)")

        # Trusted Cert (específico de SSL)
        self.cert_label = QLabel("Trusted Cert (Hash):")
        self.cert_edit = QLineEdit(profile.get('trusted_cert', "") if profile else "")
        self.cert_edit.setPlaceholderText("Hash SHA256 (se detecta automáticamente si se deja vacío)")

        # Pre-Shared Key (específico de IPSec)
        self.psk_label = QLabel("Clave Precompartida (PSK):")
        self.psk_edit = QLineEdit(profile.get('preshared_key', "") if profile else "")
        self.psk_edit.setEchoMode(QLineEdit.Password)
        self.psk_edit.setPlaceholderText("(Opcional - Requerida si el concentrador usa PSK)")

        self.dns_edit = QLineEdit(profile.get('dns_domain', "") if profile else "")
        self.dns_edit.setPlaceholderText("Ej: gna.gob.ar gna gendarmeria.local")

        self.otp_check = QCheckBox("Conexión requiere OTP / Doble Factor (2FA)")
        self.otp_check.setChecked(profile.get('otp_enabled', False) if profile else False)

        layout.addRow("Tipo de VPN:", self.type_combo)
        layout.addRow("Nombre del Perfil:", self.name_edit)
        layout.addRow("Usuario / Identidad:", self.user_edit)
        layout.addRow("Contraseña:", self.pass_edit)
        layout.addRow(self.psk_label, self.psk_edit)
        layout.addRow(self.cert_label, self.cert_edit)
        layout.addRow("Dominio Split-DNS:", self.dns_edit)
        layout.addRow("", self.otp_check)

        # Gateways Section
        gw_label = QLabel("Gateways / Servidores (Orden de Failover):")
        layout.addRow(gw_label)

        gw_input_layout = QHBoxLayout()
        self.gw_host_edit = QLineEdit()
        self.gw_host_edit.setPlaceholderText("Host o IP del servidor")

        default_port = "500" if current_type == "ipsec" else "443"
        self.gw_port_edit = QLineEdit(default_port)
        self.gw_port_edit.setValidator(QIntValidator(1, 65535))
        self.gw_port_edit.setFixedWidth(60)

        self.gw_add_btn = QPushButton("+ Añadir")
        self.gw_add_btn.clicked.connect(self.add_gateway)

        gw_input_layout.addWidget(self.gw_host_edit)
        gw_input_layout.addWidget(self.gw_port_edit)
        gw_input_layout.addWidget(self.gw_add_btn)
        layout.addRow(gw_input_layout)

        self.gw_list = QListWidget()
        self.gw_list.setMaximumHeight(90)
        layout.addRow(self.gw_list)

        self.gw_del_btn = QPushButton("Eliminar Gateway Seleccionado")
        self.gw_del_btn.clicked.connect(self.del_gateway)
        layout.addRow(self.gw_del_btn)

        # Cargar gateways existentes
        if profile and 'gateways' in profile:
            for gw in profile['gateways']:
                self.add_gateway_item(gw['host'], gw['port'])

        # Texto de ayuda
        self.help_lbl = QLabel("Nota: Si el primer gateway falla, se intentará automáticamente el siguiente.")
        self.help_lbl.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(self.help_lbl)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.setStyleSheet("font-weight: bold;")
        save_btn.clicked.connect(self.validate_and_save)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)

        layout.addRow(btn_box)
        self.setLayout(layout)

        # Aplicar visibilidad inicial según tipo
        self._on_type_changed()

    def _on_type_changed(self):
        vpn_type = self.type_combo.currentData()
        is_ssl = (vpn_type == "ssl")
        self.cert_label.setVisible(is_ssl)
        self.cert_edit.setVisible(is_ssl)
        self.cert_label.setEnabled(is_ssl)
        self.cert_edit.setEnabled(is_ssl)

        self.psk_label.setVisible(not is_ssl)
        self.psk_edit.setVisible(not is_ssl)
        self.psk_label.setEnabled(not is_ssl)
        self.psk_edit.setEnabled(not is_ssl)

        # Ajustar puerto por defecto si está en un valor común
        cur_port = self.gw_port_edit.text().strip()
        if is_ssl and cur_port in ["500", "4500", ""]:
            self.gw_port_edit.setText("443")
        elif not is_ssl and cur_port in ["443", ""]:
            self.gw_port_edit.setText("500")

    def add_gateway(self):
        host = self.gw_host_edit.text().strip()
        port = self.gw_port_edit.text().strip()

        if not host:
            QMessageBox.warning(self, "Campo Requerido", "Ingrese el host o IP del servidor gateway.")
            return

        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Puerto Inválido", "El puerto debe ser un número entre 1 y 65535.")
            return

        self.add_gateway_item(host, int(port))
        self.gw_host_edit.clear()
        default_port = "443" if self.type_combo.currentData() == "ssl" else "500"
        self.gw_port_edit.setText(default_port)

    def add_gateway_item(self, host, port):
        item_text = f"{host}:{port}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, {'host': host, 'port': port})
        self.gw_list.addItem(item)

    def del_gateway(self):
        row = self.gw_list.currentRow()
        if row >= 0:
            self.gw_list.takeItem(row)

    def validate_and_save(self):
        name = self.name_edit.text().strip()
        user = self.user_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Validación", "El perfil debe tener un nombre descriptivo.")
            return

        if not user:
            QMessageBox.warning(self, "Validación", "Debe especificar el nombre de usuario o identidad institucional.")
            return

        # Si el usuario escribió un gateway en los campos pero olvidó pulsar '+', agregarlo automáticamente
        pending_host = self.gw_host_edit.text().strip()
        if pending_host and self.gw_list.count() == 0:
            self.add_gateway()

        if self.gw_list.count() == 0:
            QMessageBox.warning(self, "Validación", "Debe agregar al menos un gateway o servidor de conexión.")
            return

        self.accept()

    def get_data(self):
        gateways = []
        for i in range(self.gw_list.count()):
            data = self.gw_list.item(i).data(Qt.UserRole)
            gateways.append(data)

        password = self.pass_edit.text()
        if not password:
            password = None  # Señal para no sobrescribir si no se cambió

        vpn_type = self.type_combo.currentData()
        return {
            'name': self.name_edit.text().strip(),
            'vpn_type': vpn_type,
            'username': self.user_edit.text().strip(),
            'password': password,
            'preshared_key': self.psk_edit.text().strip() if vpn_type == 'ipsec' else "",
            'trusted_cert': self.cert_edit.text().strip() if vpn_type == 'ssl' else "",
            'gateways': gateways,
            'otp_enabled': self.otp_check.isChecked(),
            'dns_domain': self.dns_edit.text().strip(),
            'ike_version': 2
        }


class ConfigDialog(QDialog):
    """
    Diálogo principal de gestión de perfiles (crear, editar, eliminar y autostart).
    """

    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.setWindowTitle("Gestionar Perfiles - VPN GNA")
        self.resize(520, 420)

        layout = QHBoxLayout()

        # Lista de perfiles con visualización del tipo (SSL / IPSec)
        self.profile_list = QListWidget()
        self.profile_list.itemDoubleClicked.connect(self.edit_profile)
        layout.addWidget(self.profile_list)

        # Botones de acción
        btn_layout = QVBoxLayout()

        add_btn = QPushButton("Nuevo Perfil")
        add_btn.clicked.connect(self.add_profile)

        import_btn = QPushButton("Importar FortiClient...")
        import_btn.clicked.connect(self.import_forticlient)

        edit_btn = QPushButton("Editar")
        edit_btn.clicked.connect(self.edit_profile)

        del_btn = QPushButton("Eliminar")
        del_btn.clicked.connect(self.delete_profile)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)

        # Checkbox de Autostart
        self.autostart_check = QCheckBox("Iniciar con el sistema")
        self.autostart_check.setChecked(self.check_autostart_state())
        self.autostart_check.stateChanged.connect(self.toggle_autostart)
        btn_layout.addWidget(self.autostart_check)

        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.refresh_list()

    def check_autostart_state(self) -> bool:
        new_path = os.path.expanduser("~/.config/autostart/vpn-gna.desktop")
        old_path = os.path.expanduser("~/.config/autostart/openfortivpn-gui.desktop")
        return os.path.exists(new_path) or os.path.exists(old_path)

    def toggle_autostart(self, state):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        target_path = os.path.join(autostart_dir, "vpn-gna.desktop")
        legacy_target = os.path.join(autostart_dir, "openfortivpn-gui.desktop")

        source_candidates = [
            os.path.expanduser("~/.local/share/applications/vpn-gna.desktop"),
            os.path.expanduser("~/.local/share/applications/openfortivpn-gui.desktop")
        ]
        source_path = next((p for p in source_candidates if os.path.exists(p)), None)

        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir, exist_ok=True)

        if state == 2:  # Checked
            if source_path and os.path.exists(source_path):
                import shutil
                shutil.copy(source_path, target_path)
            else:
                QMessageBox.warning(self, "Autostart", "No se encontró el lanzador de escritorio para habilitar inicio automático.")
        else:  # Unchecked
            for p in [target_path, legacy_target]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    def refresh_list(self):
        self.profile_list.clear()
        profiles = self.profile_manager.get_profiles()
        for p in profiles:
            vpn_type = p.get('vpn_type', 'ssl').upper()
            label = f"[{vpn_type}] {p['name']} ({p['username']})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, p['id'])
            self.profile_list.addItem(item)

    def add_profile(
        self,
        name: str = None,
        gateways: list = None,
        vpn_type: str = "ssl"
    ):
        dialog = ProfileEditorDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.profile_manager.add_profile(
                name=data['name'],
                username=data['username'],
                password=data['password'] or "",
                preshared_key=data.get('preshared_key', ""),
                trusted_cert=data.get('trusted_cert', ""),
                gateways=data.get('gateways', []),
                otp_enabled=data.get('otp_enabled', False),
                dns_domain=data.get('dns_domain', ""),
                vpn_type=data.get('vpn_type', "ssl"),
                ike_version=data.get('ike_version', 2)
            )
            self.refresh_list()

    def import_forticlient(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar configuración de FortiClient",
            "",
            "Configuraciones FortiClient (*.conf *.xml);;Todos los archivos (*)"
        )
        if not file_path:
            return

        try:
            profile = self.profile_manager.import_forticlient_config(file_path)
            self.refresh_list()
            gw_count = len(profile.get('gateways', []))
            QMessageBox.information(
                self,
                "Importación Exitosa",
                f"Perfil '{profile['name']}' importado con éxito ({gw_count} gateways cargados).\n\n"
                "Para conectarse, edite el perfil para ingresar su usuario y la Pre-Shared Key (PSK) institucional si su concentrador la requiere."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error de Importación", f"No se pudo importar el archivo FortiClient:\n{e}")

    def edit_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        profile_id = item.data(Qt.UserRole)
        profile = self.profile_manager.get_profile(profile_id)
        if not profile:
            return

        dialog = ProfileEditorDialog(profile, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            self.profile_manager.update_profile(profile_id, data)
            self.refresh_list()

    def delete_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        profile_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            "¿Está seguro de eliminar el perfil seleccionado?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.profile_manager.delete_profile(profile_id)
            self.refresh_list()
