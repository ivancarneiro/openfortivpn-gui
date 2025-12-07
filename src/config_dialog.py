from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QPushButton, QMessageBox, QLabel, QInputDialog, QCheckBox,
                               QListWidgetItem)
from profile_manager import ProfileManager
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLineEdit

class ProfileEditorDialog(QDialog):

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Perfil" if profile else "Nuevo Perfil")
        self.resize(450, 450)
        
        layout = QFormLayout()
        
        self.name_edit = QLineEdit(profile['name'] if profile else "")
        self.user_edit = QLineEdit(profile['username'] if profile else "")
        
        self.pass_edit = QLineEdit(profile['password'] if profile else "")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("(Opcional)")
        
        self.cert_edit = QLineEdit(profile['trusted_cert'] if profile else "")
        
        self.otp_check = QCheckBox("Conexión requiere OTP (2FA)")
        self.otp_check.setChecked(profile.get('otp_enabled', False) if profile else False)
        
        layout.addRow("Nombre del Perfil:", self.name_edit)
        layout.addRow("Usuario:", self.user_edit)
        layout.addRow("Contraseña:", self.pass_edit)
        layout.addRow("Trusted Cert (Hash):", self.cert_edit)
        layout.addRow("", self.otp_check)
        
        # Gateways Section
        gw_label = QLabel("Gateways (Failover Order):")
        layout.addRow(gw_label)
        
        gw_input_layout = QHBoxLayout()
        self.gw_host_edit = QLineEdit()
        self.gw_host_edit.setPlaceholderText("Host/IP")
        self.gw_port_edit = QLineEdit("443")
        self.gw_port_edit.setFixedWidth(60)
        self.gw_add_btn = QPushButton("+")
        self.gw_add_btn.setFixedWidth(30)
        self.gw_add_btn.clicked.connect(self.add_gateway)
        
        gw_input_layout.addWidget(self.gw_host_edit)
        gw_input_layout.addWidget(self.gw_port_edit)
        gw_input_layout.addWidget(self.gw_add_btn)
        layout.addRow(gw_input_layout)
        
        self.gw_list = QListWidget()
        self.gw_list.setMaximumHeight(100)
        layout.addRow(self.gw_list)
        
        self.gw_del_btn = QPushButton("Eliminar Gateway Seleccionado")
        self.gw_del_btn.clicked.connect(self.del_gateway)
        layout.addRow(self.gw_del_btn)
        
        # Load existing gateways
        if profile and 'gateways' in profile:
            for gw in profile['gateways']:
                self.add_gateway_item(gw['host'], gw['port'])

        # Help text
        help_lbl = QLabel("Nota: Si el primer gateway falla, se intentará el siguiente.")
        help_lbl.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow(help_lbl)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        
        layout.addRow(btn_box)
        self.setLayout(layout)

    def add_gateway(self):
        host = self.gw_host_edit.text().strip()
        port = self.gw_port_edit.text().strip()
        if host and port:
            self.add_gateway_item(host, int(port))
            self.gw_host_edit.clear()
            self.gw_port_edit.setText("443")
            
    def add_gateway_item(self, host, port):
        item_text = f"{host}:{port}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, {'host': host, 'port': port})
        self.gw_list.addItem(item)
        
    def del_gateway(self):
        row = self.gw_list.currentRow()
        if row >= 0:
            self.gw_list.takeItem(row)

    def get_data(self):
        gateways = []
        for i in range(self.gw_list.count()):
            data = self.gw_list.item(i).data(Qt.UserRole)
            gateways.append(data)
            
        return {
            'name': self.name_edit.text(),
            'username': self.user_edit.text(),
            'password': self.pass_edit.text(),
            'trusted_cert': self.cert_edit.text(),
            'gateways': gateways,
            'otp_enabled': self.otp_check.isChecked()
        }

class ConfigDialog(QDialog):
    def __init__(self, profile_manager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.setWindowTitle("Gestionar Perfiles")
        self.resize(500, 400)
        
        layout = QHBoxLayout()
        
        # List of profiles
        self.profile_list = QListWidget()
        self.profile_list.itemDoubleClicked.connect(self.edit_profile)
        layout.addWidget(self.profile_list)
        
        # Buttons
        btn_layout = QVBoxLayout()
        
        add_btn = QPushButton("Nuevo")
        add_btn.clicked.connect(self.add_profile)
        
        edit_btn = QPushButton("Editar")
        edit_btn.clicked.connect(self.edit_profile)
        
        del_btn = QPushButton("Eliminar")
        del_btn.clicked.connect(self.delete_profile)
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.profile_list.clear()
        profiles = self.profile_manager.get_profiles()
        for p in profiles:
            self.profile_list.addItem(p['name'])
            # Store ID in user role if needed, or lookup by index/name
            # simplified: assume name is unique or list order matches manager
            self.profile_list.item(self.profile_list.count() - 1).setData(Qt.UserRole, p['id'])

    def add_profile(self):
        dialog = ProfileEditorDialog(parent=self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "Error", "El nombre es obligatorio")
                return
            self.profile_manager.add_profile(**data)
            self.refresh_list()

    def edit_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
            
        profile_id = item.data(Qt.UserRole)
        # Find profile
        profile = next((p for p in self.profile_manager.get_profiles() if p['id'] == profile_id), None)
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
        
        reply = QMessageBox.question(self, "Confirmar", 
                                     f"¿Eliminar perfil '{item.text()}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            profile_id = item.data(Qt.UserRole)
            self.profile_manager.delete_profile(profile_id)
            self.refresh_list()
