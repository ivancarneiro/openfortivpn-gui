import os
import re

LEGACY_PATHS = [
    os.path.expanduser("~/.openfortivpn/config"),
    "/etc/openfortivpn/config"
]

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
    with open(path, 'r') as f:
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
        # Get file size
        stat = os.stat(path)
        size = stat.st_size
        
        # Overwrite with zeros
        with open(path, 'wb') as f:
            f.write(b'\0' * size)
            f.flush()
            os.fsync(f.fileno())
            
        # Remove
        os.remove(path)
    except Exception as e:
        print(f"Error secure deleting {path}: {e}")
        # Try normal remove if overwrite failed (e.g. permissions, though we checked write access ideally)
        if os.path.exists(path):
            os.remove(path)
