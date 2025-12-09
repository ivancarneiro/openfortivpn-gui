import json
import os
import uuid
import tempfile
import pwd
import keyring

KEYRING_SERVICE = "ofvpn-gui"

class ProfileManager:
    def __init__(self):
        # Determine config dir. If running under sudo, use the real user's home.
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
             try:
                 user_info = pwd.getpwnam(sudo_user)
                 home_dir = user_info.pw_dir
                 self.config_dir = os.path.join(home_dir, ".config/ofvpn-gui")
             except KeyError:
                 # Fallback if user not found (weird)
                 self.config_dir = os.path.expanduser("~/.config/ofvpn-gui")
        else:
            self.config_dir = os.path.expanduser("~/.config/ofvpn-gui")
            
        self.profiles_path = os.path.join(self.config_dir, "profiles.json")
        self.profiles = []
        self._ensure_config_dir()
        self.load_profiles()

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, mode=0o700)

    def load_profiles(self):
        if not os.path.exists(self.profiles_path):
            self.profiles = []
            return

        try:
            with open(self.profiles_path, 'r') as f:
                data = json.load(f)
                loaded_profiles = data.get('profiles', [])
                
                # Migration and Loading Logic
                self.profiles = []
                migrated = False
                
                for p in loaded_profiles:
                    pid = p['id']
                    
                    # Migration: Check if password exists in JSON
                    json_password = p.get('password')
                    if json_password:
                        # Move to keyring
                        try:
                            keyring.set_password(KEYRING_SERVICE, pid, json_password)
                            migrated = True
                        except Exception as e:
                            print(f"Error migrating password for {pid}: {e}")
                            
                    # Load from keyring (always authoritative)
                    try:
                        stored_password = keyring.get_password(KEYRING_SERVICE, pid)
                    except Exception as e:
                        print(f"Error retrieving password for {pid}: {e}")
                        stored_password = None
                        
                    # Reconstruct profile in memory with password available for UI/Use
                    p['password'] = stored_password if stored_password else ""
                    self.profiles.append(p)
                
                # If we migrated passwords, save immediately to scrub them from JSON
                if migrated:
                    self.save_profiles()
                    
        except (json.JSONDecodeError, IOError):
            self.profiles = []

    def save_profiles(self):
        # Prepare list for JSON serialization (EXCLUDING passwords)
        clean_profiles = []
        for p in self.profiles:
            # Create a copy to modify for saving
            clean_p = p.copy()
            
            # Remove sensitive data from JSON copy
            if 'password' in clean_p:
                del clean_p['password']
                
            clean_profiles.append(clean_p)
            
            # Save password to keyring (Source of Truth)
            if p.get('password'):
                try:
                    keyring.set_password(KEYRING_SERVICE, p['id'], p['password'])
                except Exception as e:
                    print(f"Error saving password to keyring: {e}")
            else:
                # If password is empty, maybe we should delete it from keyring?
                # For now, let's just leave it or set empty. 
                # keyring.delete_password might raise if not found.
                pass

        data = {'profiles': clean_profiles}
        with open(self.profiles_path, 'w') as f:
            json.dump(data, f, indent=4)

    def add_profile(self, name, username, password, trusted_cert, gateways, otp_enabled=False):
        """
        gateways: list of dicts {'host': '...', 'port': 443}
        """
        profile = {
            'id': str(uuid.uuid4()),
            'name': name,
            'username': username,
            'password': password, 
            'trusted_cert': trusted_cert,
            'gateways': gateways,
            'otp_enabled': otp_enabled
        }
        self.profiles.append(profile)
        self.save_profiles()
        return profile

    def delete_profile(self, profile_id):
        # Remove from keyring first
        try:
            keyring.delete_password(KEYRING_SERVICE, profile_id)
        except Exception:
            pass # Ignore if not found
            
        self.profiles = [p for p in self.profiles if p['id'] != profile_id]
        self.save_profiles()

    def update_profile(self, profile_id, data):
        for profile in self.profiles:
            if profile['id'] == profile_id:
                profile.update(data)
                self.save_profiles() # Will handle keyring update
                return True
        return False

    def generate_openfortivpn_config(self, profile_id, gateway_index=0, runtime_password=None, runtime_otp=None):
        """
        Generates a temporary config file for the specified profile and gateway index.
        Returns the path to the temporary file.
        """
        profile = next((p for p in self.profiles if p['id'] == profile_id), None)
        if not profile:
            raise ValueError("Profile not found")

        if gateway_index >= len(profile['gateways']):
             raise ValueError("Gateway index out of range")
        
        gateway = profile['gateways'][gateway_index]
        
        # Priority: Runtime > Profile (InMemory)
        # Profile password should already be populated from keyring by load_profiles/update_profile
        password = runtime_password if runtime_password is not None else profile.get('password', '')
        
        config_content = f"""host = {gateway['host']}
port = {gateway.get('port', 443)}
username = {profile['username']}
password = {password}
"""
        trusted_cert = profile.get('trusted_cert', '').strip()
        if trusted_cert:
            config_content += f"trusted-cert = {trusted_cert}\n"

        if runtime_otp:
             config_content += f"otp = {runtime_otp}\n"
        
        fd, path = tempfile.mkstemp(prefix=f"ofvpn_{gateway_index}_", suffix=".conf", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        
        return path

    def generate_all_openfortivpn_configs(self, profile_id, runtime_password=None, runtime_otp=None):
        """
        Generates a list of config files for all gateways in the profile (for failover).
        """
        profile = next((p for p in self.profiles if p['id'] == profile_id), None)
        if not profile or not profile.get('gateways'):
            raise ValueError("Profile invalid or no gateways")

        paths = []
        for i in range(len(profile['gateways'])):
            paths.append(self.generate_openfortivpn_config(profile_id, i, runtime_password, runtime_otp))
        
        return paths

    def get_profiles(self):
        return self.profiles
