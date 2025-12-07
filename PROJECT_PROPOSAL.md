# Propuesta de Proyecto: ofvpn-gui

## 1. Resumen y Viabilidad

*   **Objetivo:** Crear una aplicación de escritorio con interfaz gráfica (GUI) para gestionar conexiones de `openfortivpn`. La aplicación se centrará en la facilidad de uso y en una integración nativa con el entorno de escritorio KDE Plasma.
*   **Viabilidad:** **Muy alta.** El sistema del usuario (Ubuntu 25.10, KDE Plasma 6.4.5) es una base ideal. `openfortivpn` es una herramienta de línea de comandos, lo que simplifica su control desde una aplicación externa.

## 2. Tecnología Recomendada

*   **Lenguaje:** **Python**. Por su rapidez de desarrollo y su robusto ecosistema.
*   **Framework GUI:** **PySide6 (Qt for Python)**. Para garantizar una integración 100% nativa con KDE Plasma, utilizando sus temas, iconos y estilos.
*   **Manejo de Privilegios:** **`pkexec` (PolicyKit)**. Para solicitar la contraseña de administrador de forma segura y estándar en el escritorio.

## 3. Arquitectura de la Aplicación

### Frontend (La Interfaz Gráfica)

La interacción del usuario será minimalista y directa:

*   **Ventana Principal:** Contendrá un único botón de control.
    *   **Botón Único (Conectar/Desconectar):** Un solo botón que actuará como un interruptor.
        *   **Estado Desconectado:** El botón mostrará el texto "Conectar" y tendrá un color neutro o rojizo.
        *   **Estado Conectado:** El botón mostrará el texto "Desconectar" y cambiará a un color verde para indicar actividad.
*   **Icono en la Bandeja del Sistema (System Tray):**
    *   Permitirá un acceso rápido para conectar/desconectar.
    *   Mostrará el estado de la conexión mediante su icono.
    *   Tendrá un menú para seleccionar perfiles y abrir la configuración.
*   **Ventana de Configuración:**
    *   Permitirá al usuario crear, editar y eliminar perfiles de conexión.

### Backend (El Controlador)

El cerebro de la aplicación, que funcionará de forma invisible para el usuario:

*   **Orquestador de Procesos:** Gestionará el ciclo de vida del proceso `openfortivpn`. Usará `pkexec` para lanzarlo con los privilegios necesarios.
*   **Lógica de Conexión:** Implementará el bucle de conexión y la lógica de "failover" de gateways.
*   **Monitorización:** Capturará la salida de `openfortivpn` para detectar si la conexión se ha establecido correctamente, qué gateway se ha usado y si se producen errores.

### Almacenamiento de Configuración

*   Los perfiles de VPN se guardarán en un archivo de formato JSON en `~/.config/ofvpn-gui/profiles.json`.
*   Esto separa la configuración del usuario de la aplicación y facilita hacer copias de seguridad.

## 4. Característica Clave: "Failover" de Gateways

Para mejorar la robustez, la aplicación implementará una lógica de tolerancia a fallos:

1.  **Múltiples Gateways por Perfil:** La configuración permitirá definir una lista ordenada de hosts (gateways) para un mismo perfil de VPN.
2.  **Intentos Secuenciales:** Al conectar, la aplicación intentará establecer la conexión con el primer gateway de la lista.
3.  **Failover Automático:** Si un gateway no responde en un tiempo determinado (ej. 15 segundos), el intento se cancelará y la aplicación pasará al siguiente gateway de la lista automáticamente.
4.  **Notificación al Usuario:** Cuando la conexión sea exitosa, la interfaz informará al usuario a través de qué gateway se ha conectado. Si todos fallan, se mostrará un error.

## 5. Plan de Desarrollo Inicial

1.  **Fase 0: Documentación (Este archivo).**
2.  **Fase 1: Estructura y Prototipo Básico.**
    *   Crear la estructura de directorios (`src/`, etc.).
    *   Crear el archivo principal `main.py`.
    *   Implementar la ventana principal con el botón único (sin funcionalidad aún).
3.  **Fase 2: Lógica de Conexión.**
    *   Implementar la función que lanza `openfortivpn` con `pkexec`, usando los datos de `gendarmeria.conf` como prueba.
    *   Asociar esta función al botón para crear un primer prototipo funcional.
4.  **Fase 3: Gestión de Perfiles.**
    *   Crear la lógica para leer/escribir perfiles desde el archivo JSON.
    *   Crear la ventana de configuración para gestionar dichos perfiles.
5.  **Fase 4: Integración con el Escritorio.**
    *   Implementar el icono de la bandeja del sistema.
    *   Pulir detalles de integración con KDE (iconos, notificaciones).
