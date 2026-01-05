# OpenFortiVPN GUI

Un cliente gráfico moderno, robusto y seguro para `openfortivpn` en Linux, construido con Python y PySide6.

**Versión Actual:** v1.2

![screenshot](screenshot_1.png)

## Novedades v1.2

*   **Seguridad Mejorada (Hardening)**: Borrado seguro garantizado de archivos temporales de configuración y limpieza automática de procesos huérfanos.
*   **Asistente de Migración**: Detecta automáticamente configuraciones antiguas inseguras en `/etc/openfortivpn/config` y permite importarlas al almacenamiento seguro.
*   **Modo Sin Contraseña**: Opción para conectar y desconectar sin prompts de `sudo/pkexec` configurando permisos específicos.
*   **Autostart**: Opción para iniciar con el sistema (minimizado en la bandeja).
*   **UX Refinada**: Desconexión suave sin contraseñas, validación de puertos estricta y mejor gestión de errores.

## Características Principales

*   **Interfaz Moderna**: Tema oscuro (Fusion Dark) e iconos nítidos.
*   **Gestión de Perfiles**: Crea, edita y gestiona múltiples perfiles de conexión.
*   **Multi-Gateway & Failover**: Añade múltiples servidores a un mismo perfil. Si uno falla, el cliente intentará conectar al siguiente automáticamente.
*   **Seguridad**: 
    *   Soporte para contraseñas de sesión (no guardadas en disco).
    *   Soporte para OTP / 2FA (Tokens).
    *   Almacenamiento seguro de credenciales en el Llavero del Sistema (Keyring).
*   **Integración de Escritorio**:
    *   Minimizar al System Tray.
    *   Notificaciones nativas de conexión/desconexión.
*   **Monitoreo**: Panel de estadísticas de tráfico en tiempo real y logs detallados (`~/.config/ofvpn-gui/debug.log`).

## Requisitos

*   Linux (Diseñado y probado en **KDE Plasma**, compatible con GNOME/XFCE)
*   Python 3.8+
*   `openfortivpn` (Instalado automáticamente por el script)
*   `sudo` / `pkexec`

## Instalación Rápida

El proyecto incluye un script de instalación automatizado que se encarga de las dependencias, el entorno virtual y el lanzador de escritorio.

1.  Clona el repositorio:
    ```bash
    git clone https://github.com/ivancarneiro/openfortivpn-gui.git
    cd openfortivpn-gui
    ```

2.  Ejecuta el instalador:
    ```bash
    ./install.sh
    ```

3.  ¡Listo! Busca "OpenFortiVPN GUI" en tu menú de aplicaciones.

## Configuración Avanzada: Modo Sin Contraseña

Por defecto, la aplicación solicitará su contraseña de usuario (sudo) para iniciar la conexión VPN, ya que `openfortivpn` requiere permisos de root. 

Para habilitar una experiencia **totalmente fluida sin contraseñas** (tanto para conectar como para desconectar), ejecute el siguiente script una única vez:

```bash
./configure_permissions.sh
```

Esto añadirá una regla segura en `/etc/sudoers.d/` permitiendo ejecutar solo la VPN y el comando de cierre específico sin password.

## Uso y Solución de Problemas

*   **Logs**: Si tienes problemas, revisa `~/.config/ofvpn-gui/debug.log`.
*   **Permisos**: Si la aplicación no guarda la configuración, asegúrate de ser el dueño de la carpeta de config: `sudo chown -R $USER:$USER ~/.config/ofvpn-gui`.
*   **Desconexión**: Use el botón "Desconectar" de la app. Si cierra la ventana con la `X`, la aplicación se minimizará a la bandeja. Para cerrar completamente, use Clic Derecho en el icono del tray -> Salir.

## Contribuir

¡Las contribuciones son bienvenidas! Por favor abre un issue o envía un pull request.

## Licencia

MIT License. Ver archivo `LICENSE` para más detalles.

---
Desarrollado con ❤️ por ciex.
