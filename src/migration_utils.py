import os
import re
import json
import pwd
import keyring

LEGACY_PATHS = [
    os.path.expanduser("~/.openfortivpn/config"),
    "/etc/openfortivpn/config"
]

OLD_KEYRING_SERVICE = "ofvpn-gui"
NEW_KEYRING_SERVICE = "vpn-gna"


def migrate_ofvpn_gui_to_vpn_gna() -> bool:
    """
    Migra automáticamente la configuración y contraseñas de openfortivpn-gui (~/.config/ofvpn-gui)
    hacia la nueva estructura institucional VPN-GNA (~/.config/vpn-gna).
    Retorna True si se realizó una migración.
    """
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        try:
            user_info = pwd.getpwnam(sudo_user)
            home_dir = user_info.pw_dir
        except KeyError:
            home_dir = os.path.expanduser("~")
    else:
        home_dir = os.path.expanduser("~")

    old_config_dir = os.path.join(home_dir, ".config/ofvpn-gui")
    new_config_dir = os.path.join(home_dir, ".config/vpn-gna")

    old_profiles_path = os.path.join(old_config_dir, "profiles.json")
    new_profiles_path = os.path.join(new_config_dir, "profiles.json")

    # Si no hay perfiles antiguos o ya existe el nuevo directorio de perfiles, no es necesaria la migración
    if not os.path.exists(old_profiles_path) or os.path.exists(new_profiles_path):
        return False

    try:
        if not os.path.exists(new_config_dir):
            os.makedirs(new_config_dir, mode=0o700, exist_ok=True)

        with open(old_profiles_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profiles = data.get("profiles", [])
        migrated_profiles = []

        for p in profiles:
            pid = p.get("id")
            if not pid:
                continue

            # Asignar tipo SSL por defecto a perfiles heredados
            if "vpn_type" not in p or p["vpn_type"] not in ["ssl", "ipsec"]:
                p["vpn_type"] = "ssl"

            if "ike_version" not in p:
                p["ike_version"] = 2

            # Migrar contraseña desde keyring antiguo hacia el nuevo servicio
            try:
                old_pwd = keyring.get_password(OLD_KEYRING_SERVICE, pid)
                if old_pwd:
                    keyring.set_password(NEW_KEYRING_SERVICE, pid, old_pwd)
            except Exception as e:
                print(f"Warning: error migrating keyring for profile {pid}: {e}")

            # Limpiar contraseñas en texto plano si existieran en el JSON
            if "password" in p:
                del p["password"]

            migrated_profiles.append(p)

        new_data = {"profiles": migrated_profiles}
        temp_path = f"{new_profiles_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)
        os.replace(temp_path, new_profiles_path)
        os.chmod(new_profiles_path, 0o600)
        return True

    except Exception as e:
        print(f"Error during migration from ofvpn-gui to vpn-gna: {e}")
        return False


def detect_legacy_configs():
    """
    Scans common locations for openfortivpn config files.
    Returns a list of dicts: {'path': str, 'has_password': bool, 'content': dict}
    """
    found = []
    for path in LEGACY_PATHS:
        if os.path.exists(path) and os.access(path, os.R_OK):
            try:
                content = parse_config(path)
                has_password = 'password' in content and bool(content['password'])
                found.append({
                    'path': path,
                    'has_password': has_password,
                    'content': content
                })
            except Exception as e:
                print(f"Error parsing {path}: {e}")
    return found


def parse_config(path):
    """
    Simple parser for openfortivpn config format (key = value)
    """
    config = {}
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                config[key] = val
    return config


def secure_delete(path):
    """
    Overwrites the file with zeros before unlinking (shredding).
    """
    if not os.path.exists(path):
        return

    try:
        stat = os.stat(path)
        size = stat.st_size
        with open(path, 'wb') as f:
            f.write(b'\0' * size)
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
    except Exception as e:
        print(f"Error secure deleting {path}: {e}")
        if os.path.exists(path):
            os.remove(path)
