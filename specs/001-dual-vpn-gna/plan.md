# Implementation Plan: VPN-GNA Dual SSL / IPSec

**Branch**: `001-dual-vpn-gna` | **Date**: 2026-10-14 | **Spec**: [specs/001-dual-vpn-gna/spec.md](file:///home/ciex/openfortivpn-gui/specs/001-dual-vpn-gna/spec.md)

**Input**: Feature specification from `/specs/001-dual-vpn-gna/spec.md`

## Summary

Evolucionar la aplicación gráfica de escritorio de **OpenFortiVPN-GUI** a **VPN-GNA**, introduciendo una arquitectura de motor dual (Dual-Stack) que soporte tanto conexiones **SSL-VPN** (`openfortivpn`) como **IPSec IKEv2 EAP** (`strongSwan` con `swanctl`), permitiendo la convivencia de perfiles, autenticación 2FA con FortiToken y migración transparente de configuraciones para los usuarios de Gendarmería Nacional Argentina.

## Technical Context

**Language/Version**: Python 3.8+ (PySide6 / Qt6)  
**Primary Dependencies**: `PySide6`, `keyring` (SecretService), `openfortivpn`, `strongswan-swanctl`  
**Storage**: `~/.config/vpn-gna/profiles.json` (perfiles de conexión) y Keyring del sistema operativo (contraseñas seguras)  
**Testing**: Manual test suite & automated unit/integration tests with `pytest` / `pytest-qt`  
**Target Platform**: Linux (Ubuntu 22.04+, Debian 12+, Arch, Fedora; probado en KDE Plasma, GNOME, XFCE)  
**Project Type**: Desktop GUI Application (PySide6 / Qt)  
**Performance Goals**:
- Inicio y carga de perfiles < 300ms.
- Establecimiento y desconexión de túneles < 2s.
- Monitoreo en segundo plano no bloqueante (consumo de CPU < 1%).  
**Constraints**:
- **Zero Plaintext Secrets**: Nunca persistir contraseñas, tokens OTP o claves precompartidas en texto plano en disco ni logs.
- **Separación de Privilegios**: Aplicación 100% en espacio de usuario; elevación exclusiva para binarios de red vía `sudoers` (`/etc/sudoers.d/vpn-gna`).
- **Limpieza Inmediata**: Borrado garantizado de archivos de configuración efímeros en RAM (`/run/user/<uid>/`).  
**Scale/Scope**: Múltiples perfiles concurrentes configurables; 1 túnel activo por sesión.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio Constitucional | Estado | Evidencia de Cumplimiento |
| :--- | :--- | :--- |
| **I. Seguridad de Credenciales** | **PASS** | Credenciales en Keyring (`vpn-gna`), tokens 2FA volátiles en RAM, configuración efímera en `/run/user/` eliminada inmediatamente tras la carga en `charon`. Cero logs de secretos. |
| **II. Separación de Privilegios & Procesos** | **PASS** | Aplicación corre sin root. Binarios autorizados en `/etc/sudoers.d/vpn-gna`: `openfortivpn`, `killall openfortivpn`, `resolvectl`, `swanctl`. Desconexión limpia garantizada (`swanctl --terminate`). |
| **III. Qt Threading & UI Responsiveness** | **PASS** | `BaseVPNBackend` hereda de `QObject`; todos los comandos de red se ejecutan en subprocesos asíncronos o hilos dedicados sin congelar la GUI. |
| **IV. Resiliencia & Failover** | **PASS** | Soporte de failover entre gateways múltiples para ambos motores; máquina de estados estricta y notificaciones nativas de escritorio. |
| **V. Integración Desktop & UX** | **PASS** | Tema Fusion Dark unificado, soporte para bandeja del sistema (System Tray), lanzador `vpn-gna.desktop` e inicio minimizado. |

## Project Structure

### Documentation (this feature)

```text
specs/001-dual-vpn-gna/
├── spec.md              # Especificación funcional aprobada
├── plan.md              # Este plan de implementación
├── research.md          # Investigación técnica (Phase 0)
├── data-model.md        # Modelo de datos y máquina de estados (Phase 1)
├── quickstart.md        # Guía de validación y escenarios de prueba (Phase 1)
├── contracts/           # Contratos de interfaces (Phase 1)
│   ├── vpn-backend-contract.md
│   ├── profile-schema.json
│   └── swanctl-template-contract.md
└── checklists/
    └── requirements.md  # Checklist de calidad de requerimientos
```

### Source Code (repository root)

```text
src/
├── main.py                     # MainWindow, System Tray, branding 'VPN GNA'
├── vpn_manager.py              # Gestor y orquestador central (delegan en backends)
├── backends/
│   ├── __init__.py             # Exportador de backends y factory
│   ├── base.py                 # BaseVPNBackend (interfaz abstracta y señales Qt)
│   ├── openforti_backend.py    # Motor SSL (código extraído y modularizado de openfortivpn)
│   └── strongswan_backend.py   # Motor IPSec (swanctl load/initiate/terminate/stats)
├── profile_manager.py          # Almacenamiento y validación de perfiles (SSL e IPSec)
├── config_dialog.py            # Diálogo modal de edición de perfiles con formulario dinámico
├── stats_panel.py              # Panel de monitoreo de tráfico RX/TX y temporizador
├── migration_utils.py          # Asistente de migración ofvpn-gui -> vpn-gna
└── styles.py                   # Tema visual Fusion Dark

configure_permissions.sh        # Script para configurar /etc/sudoers.d/vpn-gna
install.sh                      # Instalador de entorno y lanzador de escritorio
update.sh                       # Actualizador del repositorio
```

**Structure Decision**: Se modulariza `src/vpn_manager.py` desacoplando la lógica de conexión en un paquete `src/backends/` polimórfico, manteniendo intactos los contratos visuales consumidos por `src/main.py`.

## Complexity Tracking

> **Sin violaciones constitucionales.** La arquitectura preserva la simplicidad y robustez requeridas por el proyecto.
