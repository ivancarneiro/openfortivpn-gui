# Guía de Contexto del Proyecto (OpenFortiVPN GUI)

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
[specs/001-dual-vpn-gna/plan.md](file:///home/ciex/openfortivpn-gui/specs/001-dual-vpn-gna/plan.md)
<!-- SPECKIT END -->

## 1. Descripción del Proyecto

**OpenFortiVPN GUI** es un cliente gráfico de escritorio moderno, seguro y optimizado para `openfortivpn` en Linux, desarrollado con **Python 3.8+** y **PySide6** (Qt para Python).

### Estructura de Directorios Clave
- [src/main.py](file:///home/ciex/openfortivpn-gui/src/main.py): Punto de entrada, ventana principal (`MainWindow`), barra de herramientas, bandeja del sistema (System Tray) y ciclo de vida de la aplicación.
- [src/vpn_manager.py](file:///home/ciex/openfortivpn-gui/src/vpn_manager.py): Gestor de procesos para `openfortivpn`, control de conexión/desconexión asíncrona, temporizador y lógica de failover multi-gateway.
- [src/profile_manager.py](file:///home/ciex/openfortivpn-gui/src/profile_manager.py): Almacenamiento y gestión de perfiles de conexión. Integración segura con el Keyring del sistema.
- [src/config_dialog.py](file:///home/ciex/openfortivpn-gui/src/config_dialog.py): Diálogo modal para configuración, creación y edición de perfiles VPN.
- [src/stats_panel.py](file:///home/ciex/openfortivpn-gui/src/stats_panel.py): Panel de monitoreo de estadísticas de tráfico en tiempo real (RX / TX).
- [src/migration_utils.py](file:///home/ciex/openfortivpn-gui/src/migration_utils.py): Asistente de migración segura de credenciales y configuraciones antiguas.
- [src/styles.py](file:///home/ciex/openfortivpn-gui/src/styles.py): Estilos visuales Qt (Tema Fusion Dark).

---

## 2. Constitución y Reglas Críticas (No Negociables)

Cualquier cambio o desarrollo en este repositorio debe respetar la [Constitución del Proyecto](file:///home/ciex/openfortivpn-gui/.specify/memory/constitution.md):
1. **Seguridad de Credenciales**: Nunca escribir contraseñas, secretos o tokens 2FA en texto plano en disco ni en logs (`~/.config/ofvpn-gui/debug.log`). Usar Keyring del sistema.
2. **Separación de Privilegios**: La aplicación corre en espacio de usuario. Solo `openfortivpn` o scripts específicos se elevan con `sudo`/`pkexec`.
3. **Limpieza de Procesos Huérfanos**: Garantizar el cierre seguro (SIGTERM/SIGKILL) de procesos de fondo al desconectar o cerrar la aplicación.
4. **No Bloqueo de la GUI**: Todas las operaciones lentas (subprocess, red, monitoreo) deben gestionarse mediante `QThread`, `QTimer` o señales asíncronas de Qt.

---

## 3. Spec-Kit: Flujo de Trabajo "Shorter Path"

El proyecto cuenta con **GitHub Spec Kit** configurado para Antigravity. Para características pequeñas o mejoras incrementales, utiliza el **Shorter Path**:

1. `/speckit-specify`: Definir la especificación funcional a partir del requerimiento.
2. `/speckit-plan`: Diseñar la arquitectura técnica adaptada a PySide6 y la estructura de `src/`.
3. `/speckit-tasks`: Generar la lista ordenada de tareas atómicas (`tasks.md`).
4. `/speckit-implement`: Ejecutar el plan e implementar el código.
5. `/speckit-converge`: Validar que el código implementado satisfaga al 100% la especificación y plan, cerrando cualquier brecha.

Consulta la guía detallada en [docs/spec-kit/shorter-path.md](file:///home/ciex/openfortivpn-gui/docs/spec-kit/shorter-path.md).

---

## 4. Orquestación Multi-Agente & Control de Versiones

El proyecto sigue un modelo de **Supervisor de Arquitectura / Especialistas en Paralelo**, normado en [.agents/rules/orchestration.md](file:///home/ciex/openfortivpn-gui/.agents/rules/orchestration.md) y configurado en [.agents/workflows/parallel_dissection.json](file:///home/ciex/openfortivpn-gui/.agents/workflows/parallel_dissection.json):

* **Supervisor**: Actúa como orquestador, fragmentando el trabajo de `tasks.md` mediante `/task-splitter`.
* **Pool de Especialistas**:
  * `agent_ui_desktop`: `src/main.py`, `src/config_dialog.py`, `src/stats_panel.py`, `src/styles.py`
  * `agent_vpn_core`: `src/vpn_manager.py`, `configure_permissions.sh`
  * `agent_security_storage`: `src/profile_manager.py`, `src/migration_utils.py`
  * `agent_qa_testing`: `tests/`, `install.sh`, `update.sh`
* **Conventional Commits Obligatorio**: Todo commit (manual o vía agente) es validado por el hook [.git/hooks/commit-msg](file:///home/ciex/openfortivpn-gui/.git/hooks/commit-msg) (respaldo en [scripts/hooks/commit-msg](file:///home/ciex/openfortivpn-gui/scripts/hooks/commit-msg)).

---

## 5. Skills Disponibles (Matt Pocock & Antigravity)

Las skills de desarrollo avanzado están disponibles en [.agents/skills/](file:///home/ciex/openfortivpn-gui/.agents/skills/):
- `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, `/speckit-converge` (Spec-Kit Shorter Path)
- `/task-splitter`: Disección de `tasks.md` en tareas atómicas asignadas por dominio para ejecución concurrente.
- `/setup-matt-pocock-skills`: Inicializar mapeo de issues, etiquetas y documentación de agentes.
- `/tdd`: Metodología Red-Green-Refactor para desarrollo guiado por tests.
- `/diagnosing-bugs`: Bucle metódico de investigación para bugs esquivos o caídas.
- `/code-review`: Revisión automática de estándares y especificación.
- `/grill-me`: Cuestionamiento y refinamiento crítico de ideas de diseño.
