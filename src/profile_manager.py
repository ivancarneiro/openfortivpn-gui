import json
import os
import uuid
import tempfile
import pwd
import keyring

KEYRING_SERVICE = "vpn-gna"
LEGACY_KEYRING_SERVICE = "ofvpn-gui"


class ProfileManager:
    """
    Gestor de perfiles y credenciales para VPN-GNA (Dual SSL / IPSec).
    Almacena configuraciones en profiles.json y credenciales en Keyring seguro.
    """

    def __init__(self):
        # Determinar directorio de configuración
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            try:
                user_info = pwd.getpwnam(sudo_user)
                home_dir = user_info.pw_dir
            except KeyError:
                home_dir = os.path.expanduser("~")
        else:
            home_dir = os.path.expanduser("~")

        primary_dir = os.path.join(home_dir, ".config/vpn-gna")
        legacy_dir = os.path.join(home_dir, ".config/ofvpn-gui")

        # Si existe el directorio legacy pero no el primario, preparar migración transparente
        if not os.path.exists(primary_dir) and os.path.exists(legacy_dir):
            self.legacy_profiles_path = os.path.join(legacy_dir, "profiles.json")
        else:
            self.legacy_profiles_path = None

        self.config_dir = primary_dir
        self.profiles_path = os.path.join(self.config_dir, "profiles.json")
        self.profiles = []
        self._ensure_config_dir()
        self.load_profiles()

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir, mode=0o700)
            except OSError as e:
                print(f"Error creating config directory {self.config_dir}: {e}")

    def _get_keyring_password(self, pid: str) -> str:
        """
        Recupera la contraseña desde el Keyring buscando primero en 'vpn-gna'
        y retrocediendo a 'ofvpn-gui' para migración transparente.
        """
        # Intentar en nuevo servicio vpn-gna
        try:
            stored = keyring.get_password(KEYRING_SERVICE, pid)
            if stored is not None:
                return stored
        except Exception as e:
            print(f"Warning: keyring read error on {KEYRING_SERVICE} for {pid}: {e}")

        # Intentar en servicio heredado ofvpn-gui
        try:
            legacy_stored = keyring.get_password(LEGACY_KEYRING_SERVICE, pid)
            if legacy_stored:
                # Migrar hacia adelante a vpn-gna
                try:
                    keyring.set_password(KEYRING_SERVICE, pid, legacy_stored)
                except Exception:
                    pass
                return legacy_stored
        except Exception:
            pass

        return ""

    def load_profiles(self):
        # Determinar archivo origen (primario o migración desde legacy)
        source_path = self.profiles_path
        migrating_from_legacy = False

        if not os.path.exists(source_path):
            if self.legacy_profiles_path and os.path.exists(self.legacy_profiles_path):
                source_path = self.legacy_profiles_path
                migrating_from_legacy = True
            else:
                self.profiles = []
                return

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                loaded_profiles = data.get('profiles', [])

                self.profiles = []
                migrated = migrating_from_legacy

                for p in loaded_profiles:
                    pid = p['id']

                    # Migración: Si la contraseña estaba en texto plano en JSON (legacy extremo)
                    json_password = p.get('password')
                    if json_password:
                        try:
                            keyring.set_password(KEYRING_SERVICE, pid, json_password)
                            migrated = True
                        except Exception as e:
                            print(f"Error migrating password for {pid}: {e}")

                    # Cargar siempre desde Keyring
                    stored_password = self._get_keyring_password(pid)

                    # Garantizar compatibilidad con esquema dual (FR-001 / profile-schema.json)
                    if 'vpn_type' not in p or p['vpn_type'] not in ['ssl', 'ipsec']:
                        p['vpn_type'] = 'ssl'
                        migrated = True

                    if p['vpn_type'] == 'ipsec' and 'ike_version' not in p:
                        p['ike_version'] = 2
                        migrated = True

                    if 'otp_enabled' not in p:
                        p['otp_enabled'] = False

                    if 'dns_domain' not in p:
                        p['dns_domain'] = ""

                    p['password'] = stored_password if stored_password else ""
                    stored_psk = self._get_keyring_password(f"psk_{pid}")
                    p['preshared_key'] = stored_psk if stored_psk else ""
                    self.profiles.append(p)

                # Si se detectaron cambios o se importó de legacy, guardar en destino primario
                if migrated:
                    self.save_profiles()

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading profiles from {source_path}: {e}")
            self.profiles = []

    def save_profiles(self):
        self._ensure_config_dir()
        clean_profiles = []
        for p in self.profiles:
            clean_p = p.copy()

            # Guardar contraseña en Keyring antes de omitirla en JSON
            pwd = clean_p.get('password')
            if pwd:
                try:
                    keyring.set_password(KEYRING_SERVICE, clean_p['id'], pwd)
                except Exception as e:
                    print(f"Error saving password to keyring: {e}")

            # Guardar PSK en Keyring si existe
            psk = clean_p.get('preshared_key')
            if psk:
                try:
                    keyring.set_password(KEYRING_SERVICE, f"psk_{clean_p['id']}", psk)
                except Exception as e:
                    print(f"Error saving PSK to keyring: {e}")

            # Principio I de la Constitución: NUNCA escribir contraseñas ni PSKs a disco
            if 'password' in clean_p:
                del clean_p['password']
            if 'preshared_key' in clean_p:
                del clean_p['preshared_key']

            clean_profiles.append(clean_p)

        data = {'profiles': clean_profiles}
        temp_file = f"{self.profiles_path}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            os.replace(temp_file, self.profiles_path)
            os.chmod(self.profiles_path, 0o600)
        except IOError as e:
            print(f"Error saving profiles to {self.profiles_path}: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def add_profile(
        self,
        name: str,
        username: str,
        password: str = "",
        trusted_cert: str = "",
        gateways: list = None,
        otp_enabled: bool = False,
        dns_domain: str = "",
        vpn_type: str = "ssl",
        ike_version: int = 2,
        preshared_key: str = ""
    ) -> dict:
        """
        Crea y persiste un nuevo perfil de conexión dual (SSL o IPSec).
        """
        norm_type = "ipsec" if vpn_type == "ipsec" else "ssl"
        default_port = 500 if norm_type == "ipsec" else 443

        if not gateways:
            gateways = [{'host': '', 'port': default_port}]

        profile = {
            'id': str(uuid.uuid4()),
            'name': name.strip(),
            'vpn_type': norm_type,
            'username': username.strip(),
            'password': password,
            'preshared_key': preshared_key.strip() if norm_type == "ipsec" else "",
            'trusted_cert': trusted_cert.strip() if norm_type == "ssl" else "",
            'gateways': gateways,
            'otp_enabled': bool(otp_enabled),
            'dns_domain': dns_domain.strip() if dns_domain else "",
            'ike_version': ike_version if norm_type == "ipsec" else 2
        }
        self.profiles.append(profile)
        self.save_profiles()
        return profile

    def delete_profile(self, profile_id: str):
        for service in [KEYRING_SERVICE, LEGACY_KEYRING_SERVICE]:
            try:
                keyring.delete_password(service, profile_id)
                keyring.delete_password(service, f"psk_{profile_id}")
            except Exception:
                pass

        self.profiles = [p for p in self.profiles if p['id'] != profile_id]
        self.save_profiles()

    def save_psk(self, profile_id: str, psk: str):
        """Guarda la clave pre-compartida (PSK) de forma segura en el Keyring."""
        try:
            keyring.set_password(KEYRING_SERVICE, f"psk_{profile_id}", psk)
            for p in self.profiles:
                if p['id'] == profile_id:
                    p['preshared_key'] = psk
                    break
        except Exception as e:
            print(f"Error saving PSK for {profile_id}: {e}")

    def save_password(self, profile_id: str, password: str):
        """Guarda la contraseña de forma segura en el Keyring."""
        try:
            keyring.set_password(KEYRING_SERVICE, profile_id, password)
            for p in self.profiles:
                if p['id'] == profile_id:
                    p['password'] = password
                    break
        except Exception as e:
            print(f"Error saving password for {profile_id}: {e}")

    def import_forticlient_config(self, file_path: str) -> dict:
        """
        Importa automáticamente un perfil de conexión desde un archivo XML de FortiClient (.conf / .xml).
        """
        import xml.etree.ElementTree as ET

        tree = ET.parse(file_path)
        root = tree.getroot()

        # Buscar conexión IPsec
        ipsec_conn = root.find('.//ipsecvpn/connections/connection')
        if ipsec_conn is not None:
            name = ipsec_conn.findtext('name', 'VPN_IPSEC-GNA')
            servers_raw = ipsec_conn.findtext('.//server', '')
            port_text = ipsec_conn.findtext('.//udp_port', '500')
            port = int(port_text) if port_text and port_text.isdigit() else 500
            ike_ver_text = ipsec_conn.findtext('.//version', '2')
            ike_version = int(ike_ver_text) if ike_ver_text and ike_ver_text.isdigit() else 2
            
            xauth = ipsec_conn.find('.//xauth/enabled')
            otp_enabled = bool(xauth is not None and xauth.text == '1')

            # Si la PSK está en texto plano, cargarla (si es EncX, quedará vacía para que el usuario la ingrese)
            psk_raw = ipsec_conn.findtext('.//preshared_key', '')
            psk = ""
            if psk_raw and not psk_raw.startswith("Enc") and not psk_raw.startswith("EncX"):
                psk = psk_raw.strip()

            gateways = []
            for s in servers_raw.split(';'):
                s_clean = s.strip()
                if s_clean:
                    gateways.append({'host': s_clean, 'port': port})

            if not gateways:
                gateways = [{'host': '181.104.156.140', 'port': port}]

            return self.add_profile(
                name=name,
                username="",
                password="",
                preshared_key=psk,
                gateways=gateways,
                otp_enabled=otp_enabled,
                vpn_type="ipsec",
                ike_version=ike_version
            )

        # Buscar conexión SSL
        ssl_conn = root.find('.//sslvpn/connections/connection')
        if ssl_conn is not None:
            name = ssl_conn.findtext('name', 'VPN_SSL-GNA')
            server = ssl_conn.findtext('server', '')
            port_text = ssl_conn.findtext('port', '443')
            port = int(port_text) if port_text and port_text.isdigit() else 443

            gateways = [{'host': server.strip(), 'port': port}] if server else []
            return self.add_profile(
                name=name,
                username="",
                password="",
                gateways=gateways,
                vpn_type="ssl"
            )

        raise ValueError("No se encontraron conexiones IPSec ni SSL válidas en el archivo FortiClient.")

    def update_profile(self, profile_id: str, data: dict) -> bool:
        for profile in self.profiles:
            if profile['id'] == profile_id:
                filtered_data = {k: v for k, v in data.items() if v is not None}
                # Si se actualiza el tipo a ipsec, limpiar trusted_cert
                if filtered_data.get('vpn_type') == 'ipsec':
                    filtered_data['trusted_cert'] = ""
                profile.update(filtered_data)
                self.save_profiles()
                return True
        return False

    def get_profile(self, profile_id: str) -> dict | None:
        return next((p for p in self.profiles if p['id'] == profile_id), None)

    def get_profiles(self) -> list:
        return self.profiles

    # Métodos utilitarios para SSL (utilizados por OpenFortiBackend)
    def generate_openfortivpn_config(self, profile_id: str, gateway_index: int = 0, runtime_password: str = None, runtime_otp: str = None) -> str:
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError("Profile not found")

        if gateway_index >= len(profile['gateways']):
            raise ValueError("Gateway index out of range")

        gateway = profile['gateways'][gateway_index]
        password = runtime_password if runtime_password is not None else profile.get('password', '')

        config_content = f"""host = {gateway['host']}
port = {gateway.get('port', 443)}
username = {profile['username']}
password = {password}
set-dns = 1
pppd-use-peerdns = 1
"""
        trusted_cert = profile.get('trusted_cert', '').strip()
        if trusted_cert:
            config_content += f"trusted-cert = {trusted_cert}\n"

        if runtime_otp:
            config_content += f"otp = {runtime_otp}\n"

        fd, path = tempfile.mkstemp(prefix=f"vpn_gna_{gateway_index}_", suffix=".conf", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        os.chmod(path, 0o600)
        return path

    def generate_all_openfortivpn_configs(self, profile_id: str, runtime_password: str = None, runtime_otp: str = None) -> list:
        profile = self.get_profile(profile_id)
        if not profile or not profile.get('gateways'):
            raise ValueError("Profile invalid or no gateways")

        paths = []
        for i in range(len(profile['gateways'])):
            paths.append(self.generate_openfortivpn_config(profile_id, i, runtime_password, runtime_otp))
        return paths
