# OpenFortiVPN GUI

Un cliente gráfico moderno y fácil de usar para `openfortivpn` en Linux, construido con Python y PySide6.

![Screenshot](assets/screenshot.png) *(Puedes añadir una captura aquí)*

## Características

*   **Interfaz Moderna**: Tema oscuro (Fusion Dark) e iconos nítidos.
*   **Gestión de Perfiles**: Crea, edita y gestiona múltiples perfiles de conexión.
*   **Multi-Gateway & Failover**: Añade múltiples servidores a un mismo perfil. Si uno falla, el cliente intentará conectar al siguiente automáticamente.
*   **Seguridad**: 
    *   Soporte para contraseñas de sesión (no guardadas en disco).
    *   Soporte para OTP / 2FA (Tokens).
    *   Detección y aceptación de certificados de confianza (Trusted Certs).
*   **Integración de Escritorio**:
    *   Minimizar al System Tray.
    *   Notificaciones nativas de conexión/desconexión.
*   **Monitoreo**: Panel de estadísticas de tráfico en tiempo real y logs detallados.

## Requisitos

*   Linux (Probado en Ubuntu/Debian)
*   Python 3.8+
*   `openfortivpn` (Debe estar instalado en el sistema)
*   `sudo` (Para ejecutar `openfortivpn`. La GUI utiliza `pkexec` o detecta si ya es root).

```bash
# Instalar openfortivpn
sudo apt install openfortivpn
```

## Instalación

1.  Clona el repositorio:
    ```bash
    git clone https://github.com/ivancarneiro/openfortivpn-gui.git
    cd ofvpn-gui
    ```

2.  Crea un entorno virtual e instala las dependencias:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

## Uso

Para integrar correctamente con `pkexec` y notificaciones, se recomienda ejecutar desde el entorno virtual:

```bash
sudo ./.venv/bin/python src/main.py
```

*Nota: La aplicación requiere permisos de root para levantar la interfaz de red VPN (ppp0). Sin embargo, la configuración se guarda en el directorio home de su usuario real (`~/.config/ofvpn-gui`).*

## Contribuir

¡Las contribuciones son bienvenidas! Por favor abre un issue o envía un pull request.

## Licencia

MIT License. Ver archivo `LICENSE` para más detalles.

---
Desarrollado con ❤️ por ciex.
