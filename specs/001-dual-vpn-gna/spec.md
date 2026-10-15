# Feature Specification: VPN-GNA Dual SSL / IPSec

**Feature Branch**: `001-dual-vpn-gna`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Evolucionar OpenFortiVPN-GUI a VPN-GNA con soporte dual SSL e IPSec con strongswan"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conexión Segura vía IPSec IKEv2 con Autenticación Dual Factor (Priority: P1)

Como personal o usuario remoto de Gendarmería Nacional Argentina, necesito conectarme a la red institucional mediante túneles IPSec (IKEv2) utilizando mis credenciales de usuario y mi token de doble factor (FortiToken/OTP), para acceder a los sistemas internos de forma segura tras la discontinuación de SSL-VPN en los concentradores Fortinet.

**Why this priority**: Es el objetivo central y crítico del proyecto. La infraestructura de seguridad de GNA migra su concentrador a IPSec, convirtiéndose en el único método admitido para conexiones remotas a mediano y largo plazo.

**Independent Test**: Puede probarse de forma independiente creando un perfil IPSec, ingresando credenciales y OTP, y verificando el establecimiento exitoso del túnel y la navegación a recursos de la red interna de GNA.

**Acceptance Scenarios**:

1. **Given** un perfil IPSec configurado con servidor concentrador y usuario, **When** el usuario hace clic en "Conectar" e ingresa su código OTP cuando se le solicita, **Then** el sistema autentica ante el concentrador y el estado cambia a "Conectado", mostrando la notificación correspondiente.
2. **Given** un intento de conexión IPSec en curso, **When** el usuario ingresa un código OTP inválido o expirado, **Then** el sistema cancela el intento, no almacena el código fallido, muestra un mensaje descriptivo de fallo de autenticación y regresa al estado "Desconectado".

---

### User Story 2 - Coexistencia Dual y Gestión de Perfiles SSL e IPSec (Priority: P2)

Como usuario que se conecta a diferentes dependencias o entornos durante la fase de transición, necesito gestionar perfiles tanto SSL como IPSec dentro de la misma interfaz gráfica, seleccionando fácilmente el destino deseado sin cambiar de aplicación ni alterar configuraciones de sistema complejas.

**Why this priority**: La migración de concentradores en GNA es progresiva. Los usuarios deben poder acceder a sedes que aún usen SSL y a sedes que ya operen con IPSec desde un único cliente unificado.

**Independent Test**: Puede probarse configurando un perfil de tipo SSL y otro de tipo IPSec; conectar sucesivamente a cada uno de ellos y verificar que la interfaz adapta sus campos y orquesta el motor correspondiente de manera transparente.

**Acceptance Scenarios**:

1. **Given** el diálogo de gestión de perfiles, **When** el usuario elige el tipo "IPSec", **Then** el formulario oculta los campos exclusivos de SSL (como el hash de certificado SSL) y presenta los campos requeridos para IPSec (servidor concentrador, identidad EAP, dominios institucionales).
2. **Given** un perfil SSL preexistente y un perfil IPSec recién creado, **When** el usuario selecciona cualquiera de ellos en el selector principal y presiona "Conectar", **Then** la aplicación invoca el motor correspondiente sin conflictos.

---

### User Story 3 - Transición de Identidad y Migración Transparente a "VPN-GNA" (Priority: P3)

Como usuario de OpenFortiVPN-GUI, al actualizar a la nueva versión necesito que mis perfiles, configuraciones y accesos directos se reconozcan automáticamente bajo la nueva identidad institucional "VPN-GNA" sin perder credenciales almacenadas ni requerir reconfiguraciones manuales.

**Why this priority**: Garantiza continuidad operativa para los usuarios actuales sin generar fricción, consultas técnicas a mesa de ayuda ni interrupciones del servicio.

**Independent Test**: Iniciar la aplicación en un entorno con configuraciones previas en `~/.config/ofvpn-gui/` y credenciales en Keyring; comprobar que los perfiles se cargan en la nueva estructura bajo el nombre y branding de "VPN-GNA".

**Acceptance Scenarios**:

1. **Given** una instalación previa con perfiles almacenados en el directorio antiguo, **When** se inicia VPN-GNA por primera vez, **Then** el sistema migra de forma transparente los perfiles y contraseñas seguras, actualiza los accesos del sistema y continúa operando normalmente.

---

### User Story 4 - Monitoreo de Sesión, Tráfico y Cierre Seguro (Priority: P4)

Como usuario conectado mediante IPSec, necesito visualizar el tiempo transcurrido de conexión, el volumen de datos transferidos (RX/TX) y poder desconectarme inmediatamente con un solo clic garantizando que no queden procesos huérfanos ni rutas colgadas.

**Why this priority**: Proporciona visibilidad del enlace activo, asegura la estabilidad de las rutas de red del usuario al desconectar y cumple con las normas de seguridad de procesos.

**Independent Test**: Conectar a un perfil IPSec, transferir tráfico de red, verificar el incremento en el contador de bytes en el panel gráfico, pulsar "Desconectar" y constatar que el enlace se cierra en menos de 2 segundos.

**Acceptance Scenarios**:

1. **Given** un túnel IPSec activo, **When** se transfieren datos por la conexión, **Then** el panel de estadísticas actualiza periódicamente la tasa y volumen acumulado de RX/TX.
2. **Given** un túnel IPSec activo, **When** el usuario presiona "Desconectar", **Then** el túnel se interrumpe de inmediato, las rutas se restauran, el temporizador se detiene y la interfaz vuelve al estado "Desconectado".

---

### Edge Cases

- **Pérdida de conectividad física / Timeout**: Si la red Wi-Fi o cableada se interrumpe abruptamente durante una sesión IPSec, el sistema debe detectar la caída del enlace, actualizar el estado a "Desconectado" y notificar al usuario.
- **Cancelación durante solicitud de OTP**: Si el usuario presiona "Cancelar" o cierra la ventana al solicitarle el código de doble factor, el proceso de conexión debe abortarse limpiamente sin dejar subprocesos en espera.
- **Falta de permisos del sistema**: Si las reglas de ejecución privilegiada sin contraseña no han sido aplicadas en el sistema, la aplicación debe guiar al usuario o recurrir al diálogo de autenticación del sistema sin congelar la ventana principal.
- **Configuración de Split-DNS con múltiples dominios**: Al conectarse por IPSec con dominios de búsqueda institucionales (`gna.gob.ar`, `gendarmeria.gob.ar`), el sistema debe asegurar que el tráfico hacia esos dominios resuelva por el túnel sin afectar la resolución de internet general.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir crear, visualizar, editar y eliminar perfiles de conexión diferenciando explícitamente entre motor "SSL (OpenFortiVPN)" y motor "IPSec (strongSwan)".
- **FR-002**: Para perfiles de tipo IPSec, el sistema DEBE permitir registrar el servidor concentrador, puerto (por defecto 500/4500), identidad/usuario y habilitación opcional de segundo factor (2FA/OTP).
- **FR-003**: Al iniciar una conexión en un perfil con 2FA habilitado, el sistema DEBE solicitar al usuario el código OTP mediante un diálogo interactivo seguro y no persistente.
- **FR-004**: Para la autenticación IPSec IKEv2 EAP, el sistema DEBE combinar de forma transparente la contraseña y el código OTP conforme al mecanismo de validación del concentrador institucional, sin escribir el token en disco ni logs.
- **FR-005**: El sistema DEBE almacenar las contraseñas de los perfiles en el llavero seguro del sistema (Keyring), permitiendo también la opción de no recordarlas y solicitarlas en cada sesión.
- **FR-006**: Toda la lógica de conexión, desconexión y monitoreo de túneles IPSec y SSL DEBE ejecutarse de forma asíncrona en segundo plano sin bloquear la respuesta de la interfaz de usuario.
- **FR-007**: El sistema DEBE reflejar fielmente los estados del ciclo de vida de la conexión: `Desconectado`, `Conectando`, `Conectado` y `Fallo de Conexión`.
- **FR-008**: Durante una sesión IPSec activa, el sistema DEBE medir y reportar en la interfaz el tiempo transcurrido y las métricas de tráfico recibido y transmitido (RX/TX).
- **FR-009**: El sistema DEBE renombrar su identidad de aplicación a "VPN-GNA", actualizando títulos de ventana, lanzador de escritorio y directorio de datos de forma compatible con instalaciones previas.
- **FR-010**: Al solicitar la desconexión o al cerrar la aplicación, el sistema DEBE finalizar de forma segura e inmediata la asociación de seguridad (SA) o el túnel activo, sin dejar procesos huérfanos.

---

### Key Entities

- **Perfil de Conexión (Connection Profile)**: Representa la configuración para conectarse a una red remota. Atributos: identificador único, nombre representativo, tipo de motor (`ssl` o `ipsec`), lista de servidores/gateways, usuario/identidad, configuración de segundo factor (booleano), dominios de Split-DNS institucionales.
- **Credenciales Seguras (Secure Credentials)**: Secretos asociados al perfil (contraseña de usuario). Se gestionan en el Keyring del sistema operativo bajo el espacio de nombres de la aplicación.
- **Sesión VPN (VPN Session)**: Representa el túnel en tiempo real. Atributos: estado de conexión, identificador de enlace/SA, dirección IP asignada, servidores DNS, hora de inicio y contadores de tráfico RX/TX.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un usuario puede configurar un perfil IPSec completo e iniciar conexión exitosa en menos de 1 minuto.
- **SC-002**: El 100% de los perfiles SSL preexistentes continúan funcionando sin interrupción ni pérdida de datos tras la actualización.
- **SC-003**: La desconexión del túnel IPSec y restablecimiento del estado en la interfaz ocurre en menos de 2 segundos tras presionar el botón de desconexión.
- **SC-004**: Cero (0%) credenciales, secretos o códigos 2FA almacenados en texto plano en el sistema de archivos permanente o en archivos de registro (`debug.log`).
- **SC-005**: Las operaciones de conexión y desconexión no congelan ni degradan la fluidez de la interfaz gráfica (0 bloqueos de la GUI).

---

## Assumptions

- Los servidores concentradores de GNA para IPSec implementan el protocolo estándar IKEv2 con autenticación EAP (MSCHAPv2 / RADIUS) y concatenación de token 2FA en el campo de contraseña.
- El concentrador IPSec cuenta con un certificado SSL/TLS de servidor emitido por una Autoridad Certificadora (CA) pública reconocida en el almacén del sistema (`/etc/ssl/certs`).
- La estación de trabajo Linux del usuario cuenta con `strongSwan` y el comando `swanctl` disponibles para el soporte de IPSec.
- Los dominios institucionales de GNA (`gna`, `gna.gob.ar`, `gendarmeria.gob.ar`) se enrutan de acuerdo con las políticas de Split-Tunneling y Split-DNS vigentes en la institución.
