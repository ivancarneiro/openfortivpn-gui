import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

# Asegurar QApplication para widgets Qt headless
app = QApplication.instance() or QApplication(sys.argv)

from src.profile_manager import ProfileManager, KEYRING_SERVICE, LEGACY_KEYRING_SERVICE
from src.backends.base import BaseVPNBackend
from src.backends.openforti_backend import OpenFortiBackend
from src.backends.strongswan_backend import StrongSwanBackend
from src.vpn_manager import VPNManager
from src.migration_utils import migrate_ofvpn_gui_to_vpn_gna
from src.config_dialog import ProfileEditorDialog
from src.stats_panel import StatsPanel


class TestProfileManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_dir = self.temp_dir.name
        self.config_dir = os.path.join(self.home_dir, ".config", "vpn-gna")
        os.makedirs(self.config_dir, exist_ok=True)

        self.expanduser_patcher = patch("os.path.expanduser", return_value=self.home_dir)
        self.mock_expanduser = self.expanduser_patcher.start()

        with patch.dict(os.environ, {}, clear=True):
            self.pm = ProfileManager()

    def tearDown(self):
        self.expanduser_patcher.stop()
        self.temp_dir.cleanup()

    def test_add_profile_defaults_to_ssl(self):
        profile = self.pm.add_profile(
            name="SSL-GNA",
            username="user_test",
            password="secretpassword",
            trusted_cert="abc123456",
            gateways=[{"host": "vpn.gna.gob.ar", "port": 443}]
        )
        self.assertEqual(profile["vpn_type"], "ssl")
        self.assertEqual(profile["username"], "user_test")
        self.assertEqual(profile["gateways"][0]["host"], "vpn.gna.gob.ar")
        self.assertEqual(profile["gateways"][0]["port"], 443)

    def test_add_profile_ipsec(self):
        profile = self.pm.add_profile(
            name="IPSec-GNA",
            username="agente01",
            password="secretpassword",
            vpn_type="ipsec",
            ike_version=2,
            otp_enabled=True,
            gateways=[{"host": "ipsec.gna.gob.ar", "port": 500}]
        )
        self.assertEqual(profile["vpn_type"], "ipsec")
        self.assertEqual(profile["ike_version"], 2)
        self.assertTrue(profile["otp_enabled"])
        self.assertEqual(profile["gateways"][0]["port"], 500)
        # En IPSec no debe almacenar trusted_cert
        self.assertEqual(profile["trusted_cert"], "")

    def test_save_profiles_does_not_persist_password_in_plaintext_json(self):
        profile = self.pm.add_profile(
            name="Secure-Profile",
            username="agente02",
            password="PlaintextSecretShouldNotBeInJson",
            gateways=[{"host": "vpn.gna.gob.ar", "port": 443}]
        )
        
        # Leer directamente el archivo profiles.json en disco
        with open(self.pm.profiles_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        saved_profiles = data.get("profiles", [])
        self.assertTrue(len(saved_profiles) > 0)
        saved_p = next(p for p in saved_profiles if p["id"] == profile["id"])
        
        # Principio I de la Constitución del Proyecto
        self.assertNotIn("password", saved_p, "El archivo profiles.json nunca debe contener el campo 'password'")

    @patch("keyring.get_password")
    def test_keyring_fallback_from_legacy_to_new_service(self, mock_get_pw):
        def side_effect(service, pid):
            if service == KEYRING_SERVICE:
                return None
            if service == LEGACY_KEYRING_SERVICE:
                return "migrated_pass_123"
            return None

        mock_get_pw.side_effect = side_effect
        password = self.pm._get_keyring_password("test-profile-uuid")
        self.assertEqual(password, "migrated_pass_123")


class TestMigrationUtils(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_dir = self.temp_dir.name
        self.old_dir = os.path.join(self.home_dir, ".config", "ofvpn-gui")
        self.new_dir = os.path.join(self.home_dir, ".config", "vpn-gna")

        self.expanduser_patcher = patch("os.path.expanduser", return_value=self.home_dir)
        self.mock_expanduser = self.expanduser_patcher.start()

    def tearDown(self):
        self.expanduser_patcher.stop()
        self.temp_dir.cleanup()

    @patch("keyring.get_password")
    @patch("keyring.set_password")
    def test_migration_from_ofvpn_gui_to_vpn_gna(self, mock_set_pw, mock_get_pw):
        os.makedirs(self.old_dir, exist_ok=True)
        old_profiles = {
            "profiles": [
                {
                    "id": "uuid-001",
                    "name": "Antigua VPN",
                    "username": "usuario_antiguo",
                    "gateways": [{"host": "vpn.old.gob.ar", "port": 443}]
                }
            ]
        }
        with open(os.path.join(self.old_dir, "profiles.json"), "w", encoding="utf-8") as f:
            json.dump(old_profiles, f)

        mock_get_pw.return_value = "secreto_antiguo"

        migrated = migrate_ofvpn_gui_to_vpn_gna()
        self.assertTrue(migrated)

        # Verificar que se creó el nuevo profiles.json con vpn_type: ssl
        new_profiles_path = os.path.join(self.new_dir, "profiles.json")
        self.assertTrue(os.path.exists(new_profiles_path))

        with open(new_profiles_path, "r", encoding="utf-8") as f:
            new_data = json.load(f)

        profile = new_data["profiles"][0]
        self.assertEqual(profile["vpn_type"], "ssl")
        self.assertEqual(profile["username"], "usuario_antiguo")
        mock_set_pw.assert_called_with("vpn-gna", "uuid-001", "secreto_antiguo")


class TestStrongSwanBackend(unittest.TestCase):
    def setUp(self):
        self.backend = StrongSwanBackend()

    def test_parse_sa_traffic_stats(self):
        sample_output = """
vpn-gna: #1, ESTABLISHED, IKEv2, ...
  local  'testuser' @ 192.168.1.50[4500]
  remote 'vpn.gna.gob.ar' @ 200.1.2.3[4500]
  vpn-gna: #1, reqid 1, INSTALLED, TUNNEL, ESP:AES_CBC_256/HMAC_SHA2_256_128
    installed 35s ago, rekeying in 1825s, expires in 2565s
    in  c27ba96c,   5242880 bytes,   1024 packets,     0s ago, reqid 1
    out c7ea9f5b,  10485760 bytes,   2048 packets,     0s ago, reqid 1
"""
        rx, tx = self.backend._parse_sa_stats(sample_output)
        self.assertEqual(rx, 5242880)
        self.assertEqual(tx, 10485760)

    @patch("subprocess.run")
    @patch("src.backends.strongswan_backend.StrongSwanRunner")
    def test_connect_backend_ephemeral_removal(self, mock_runner_cls, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        created_ephemeral_files = []
        original_remove = os.remove

        def tracking_remove(path):
            created_ephemeral_files.append(path)
            if os.path.exists(path):
                original_remove(path)

        with patch("os.remove", side_effect=tracking_remove):
            self.backend.connect_backend(
                gateway="ipsec.gna.gob.ar",
                port=500,
                username="test_eap_user",
                password="mypassword",
                otp="987654"
            )

        # Verificar que swanctl --load-all fue ejecutado
        load_call = None
        for c in mock_run.call_args_list:
            args = c[0][0]
            if "swanctl" in args and "--load-all" in args:
                load_call = args
                break
        self.assertIsNotNone(load_call, "swanctl --load-all debió ser invocado")

        # Verificar que el archivo efímero fue eliminado
        self.assertTrue(len(created_ephemeral_files) > 0, "El archivo efímero debió ser eliminado")
        for f in created_ephemeral_files:
            self.assertFalse(os.path.exists(f))

    @patch("subprocess.run")
    def test_disconnect_backend_stops_and_unloads(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.backend._is_active = True
        self.backend.disconnect_backend()

        terminate_found = False
        ike_found = False
        for c in mock_run.call_args_list:
            args = c[0][0]
            if "--terminate" in args:
                terminate_found = True
            if "--ike" in args:
                ike_found = True

        self.assertTrue(terminate_found)
        self.assertTrue(ike_found)
        self.assertFalse(self.backend.is_running())


class TestOpenFortiBackend(unittest.TestCase):
    def setUp(self):
        self.backend = OpenFortiBackend()

    @patch("src.backends.openforti_backend.OpenFortiRunner")
    def test_connect_backend_instantiates_runner(self, mock_runner_cls):
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        self.backend.connect_backend(
            gateway="ssl.gna.gob.ar",
            port=443,
            username="ssl_user",
            password="ssl_pass",
            otp="112233",
            extra_params={"trusted_cert": "fa712398"}
        )

        self.assertIsNotNone(self.backend.temp_config_path)
        # Verificar que el runner fue iniciado
        mock_runner.start.assert_called_once()

        # Limpiar archivo temporal generado
        if self.backend.temp_config_path and os.path.exists(self.backend.temp_config_path):
            os.remove(self.backend.temp_config_path)


class TestVPNManager(unittest.TestCase):
    def setUp(self):
        self.vpn_mgr = VPNManager()

    @patch.object(OpenFortiBackend, "connect_backend")
    def test_vpn_manager_routes_to_ssl_backend(self, mock_connect):
        ssl_profile = {
            "id": "ssl-001",
            "name": "SSL Profile",
            "vpn_type": "ssl",
            "username": "usuario_ssl",
            "gateways": [{"host": "ssl.gna.gob.ar", "port": 443}]
        }
        self.vpn_mgr.connect_vpn(ssl_profile, password="pwd", otp="123456")

        self.assertIsInstance(self.vpn_mgr.active_backend, OpenFortiBackend)
        self.assertEqual(self.vpn_mgr.get_connected_username(), "usuario_ssl")

    @patch.object(StrongSwanBackend, "connect_backend")
    def test_vpn_manager_routes_to_ipsec_backend(self, mock_connect):
        ipsec_profile = {
            "id": "ipsec-001",
            "name": "IPSec Profile",
            "vpn_type": "ipsec",
            "username": "usuario_ipsec",
            "gateways": [{"host": "ipsec.gna.gob.ar", "port": 500}]
        }
        self.vpn_mgr.connect_vpn(ipsec_profile, password="pwd", otp="654321")

        self.assertIsInstance(self.vpn_mgr.active_backend, StrongSwanBackend)
        self.assertEqual(self.vpn_mgr.get_connected_username(), "usuario_ipsec")

    @patch.object(StrongSwanBackend, "connect_backend")
    def test_vpn_manager_failover_to_next_gateway(self, mock_connect):
        multi_gw_profile = {
            "id": "ipsec-multi",
            "name": "Multi GW",
            "vpn_type": "ipsec",
            "username": "agente_failover",
            "gateways": [
                {"host": "primario.gna.gob.ar", "port": 500},
                {"host": "secundario.gna.gob.ar", "port": 500}
            ]
        }
        state_changes = []
        self.vpn_mgr.state_changed.connect(lambda s: state_changes.append(s))

        self.vpn_mgr.connect_vpn(multi_gw_profile, password="pwd")
        self.assertEqual(self.vpn_mgr.current_attempt_index, 0)
        self.assertIn("connecting", state_changes)

        # Simular fallo en el backend del primer gateway
        self.vpn_mgr._on_backend_failed("Timeout en primario")

        # Debe conmutar automáticamente al segundo gateway
        self.assertEqual(self.vpn_mgr.current_attempt_index, 1)
        self.assertIn("failover", state_changes)

    @patch.object(StrongSwanBackend, "connect_backend")
    def test_vpn_manager_no_failover_when_otp_consumed(self, mock_connect):
        multi_gw_profile = {
            "id": "ipsec-multi-otp",
            "name": "Multi GW OTP",
            "vpn_type": "ipsec",
            "username": "agente_otp",
            "gateways": [
                {"host": "primario.gna.gob.ar", "port": 500},
                {"host": "secundario.gna.gob.ar", "port": 500}
            ]
        }
        state_changes = []
        failure_reasons = []
        self.vpn_mgr.state_changed.connect(lambda s: state_changes.append(s))
        self.vpn_mgr.connection_failed.connect(lambda r: failure_reasons.append(r))

        self.vpn_mgr.connect_vpn(multi_gw_profile, password="pwd", otp="123456")
        self.assertEqual(self.vpn_mgr.current_attempt_index, 0)
        self.assertIn("connecting", state_changes)

        # Simular fallo en el backend del primer gateway con OTP consumido
        self.vpn_mgr._on_backend_failed("Timeout esperando AUTH de FortiGate")

        # NO debe conmutar al segundo gateway porque el OTP ya fue consumido
        self.assertEqual(self.vpn_mgr.current_attempt_index, 0)
        self.assertNotIn("failover", state_changes)
        self.assertIn("disconnected", state_changes)
        self.assertTrue(len(failure_reasons) > 0)
        self.assertIn("El código OTP fue consumido", failure_reasons[0])


class TestConfigDialogDualSelection(unittest.TestCase):
    def test_dialog_toggles_trusted_cert_visibility_on_type_change(self):
        editor = ProfileEditorDialog()

        # Por defecto es SSL: cert_edit visible y habilitado
        self.assertEqual(editor.type_combo.currentData(), "ssl")
        self.assertTrue(editor.cert_edit.isEnabled())

        # Cambiar a IPSec: cert_edit debe deshabilitarse o vaciarse
        idx = editor.type_combo.findData("ipsec")
        editor.type_combo.setCurrentIndex(idx)
        self.assertEqual(editor.type_combo.currentData(), "ipsec")
        self.assertFalse(editor.cert_edit.isEnabled())

        # Cambiar de vuelta a SSL
        ssl_idx = editor.type_combo.findData("ssl")
        editor.type_combo.setCurrentIndex(ssl_idx)
        self.assertTrue(editor.cert_edit.isEnabled())


class TestStatsPanelFormatting(unittest.TestCase):
    def setUp(self):
        self.panel = StatsPanel()

    def test_stats_panel_ipsec_and_ssl_updates(self):
        # Probar actualización con detalles IPSec (interfaz sa:net)
        ipsec_details = {
            "username": "agente01",
            "local_ip": "10.200.1.15",
            "remote_ip": "192.168.1.1",
            "gateway_ip": "ipsec.gna.gob.ar",
            "interface": "sa:net",
            "dns": "10.200.0.2"
        }
        self.panel.update_details(ipsec_details)
        self.assertIn("10.200.1.15", self.panel.lbl_local_ip.text())
        self.assertIn("sa:net", self.panel.lbl_gateway.text())

        # Probar actualización de tráfico RX / TX
        self.panel.update_traffic(1048576, 2097152) # 1 MB, 2 MB
        self.assertIn("1.0 MB", self.panel.lbl_rx.text())
        self.assertIn("2.0 MB", self.panel.lbl_tx.text())

        # Probar reseteo
        self.panel.reset()
        self.assertEqual(self.panel.lbl_rx.text(), "↓ 0.0 B")
        self.assertEqual(self.panel.lbl_tx.text(), "↑ 0.0 B")


class TestFortiClientImport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_dir = self.temp_dir.name
        self.expanduser_patcher = patch("os.path.expanduser", return_value=self.home_dir)
        self.mock_expanduser = self.expanduser_patcher.start()
        with patch.dict(os.environ, {}, clear=True):
            self.pm = ProfileManager()

    def tearDown(self):
        self.expanduser_patcher.stop()
        self.temp_dir.cleanup()

    def test_import_vpn_ipsec_gna_conf(self):
        conf_path = os.path.join(os.path.dirname(__file__), "..", "VPN_IPSEC-GNA.conf")
        if os.path.exists(conf_path):
            profile = self.pm.import_forticlient_config(conf_path)
            self.assertEqual(profile["name"], "VPN_IPSEC-GNA")
            self.assertEqual(profile["vpn_type"], "ipsec")
            self.assertEqual(len(profile["gateways"]), 2)
            self.assertEqual(profile["gateways"][0]["host"], "181.104.156.140")
            self.assertEqual(profile["gateways"][1]["host"], "181.209.26.140")
            self.assertTrue(profile["otp_enabled"])


if __name__ == "__main__":
    unittest.main()
