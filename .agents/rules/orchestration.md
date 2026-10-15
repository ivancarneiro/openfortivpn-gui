# Reglas de Orquestación Multi-Agente — OpenFortiVPN GUI

Este documento define el modelo jerárquico (**Supervisor / Especialistas en Paralelo**) para la orquestación de tareas en **OpenFortiVPN GUI** dentro de Antigravity-IDE.

---

## 1. Modelo de Supervisión y Pool de Agentes

El Agente Principal actúa como **Supervisor de Arquitectura**, encargado de coordinar, diseccionar especificaciones (`tasks.md`) y delegar la ejecución a agentes especialistas aislados por su alcance de archivos (*scope*).

### Pool de Especialistas

```text
               ┌─────────────────────────────────────────┐
               │         Supervisor de Arquitectura      │
               │        (Orquestador / Spec-Kit)         │
               └────────────────────┬────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
┌────────▼────────┐        ┌────────▼────────┐        ┌────────▼────────┐
│ agent_ui_desktop│        │ agent_vpn_core  │        │agent_sec_storage│
│ (PySide6 / GUI) │        │(vpn_manager.py) │        │ (keyring/perfil)│
└─────────────────┘        └─────────────────┘        └─────────────────┘
                                    │
                           ┌────────▼────────┐
                           │agent_qa_testing │
                           │(tests / mocks)  │
                           └─────────────────┘
```

1. **`agent_ui_desktop` (Especialista en GUI / Qt PySide6)**
   * **Scope**: `src/main.py`, `src/config_dialog.py`, `src/stats_panel.py`, `src/styles.py`, `assets/`
   * **Responsabilidad**: Interfaz gráfica, widgets PySide6, bandeja del sistema (`QSystemTrayIcon`), notificaciones nativas, manejo de eventos y tema Fusion Dark.
   * **Regla estricta**: No bloquear el hilo de la GUI bajo ninguna circunstancia.

2. **`agent_vpn_core` (Especialista en Conectividad y Procesos VPN)**
   * **Scope**: `src/vpn_manager.py`, `configure_permissions.sh`
   * **Responsabilidad**: Supervisión de procesos `openfortivpn` en background, parsing de salida en tiempo real, failover multi-gateway, temporizadores y señales asíncronas.
   * **Regla estricta**: Garantizar el cierre limpio de procesos huérfanos (SIGTERM con fallback a SIGKILL).

3. **`agent_security_storage` (Especialista en Seguridad y Persistencia)**
   * **Scope**: `src/profile_manager.py`, `src/migration_utils.py`
   * **Responsabilidad**: Gestión de perfiles, integración segura con el Keyring del sistema, cifrado y migración de credenciales heredadas.
   * **Regla estricta**: NUNCA guardar contraseñas o tokens 2FA en texto plano en disco ni en logs.

4. **`agent_qa_testing` (Especialista en Pruebas y Validación)**
   * **Scope**: `tests/`, `install.sh`, `update.sh`
   * **Responsabilidad**: Creación de tests unitarios, mocks de `openfortivpn` y validación de scripts de despliegue y permisos.
   * **Regla estricta**: Ejecutar pruebas de regresión antes de autorizar la convergencia final.

---

## 2. Directivas Obligatorias de Convivencia

### Directiva 1: Regla de Sincronización
> *Antes de escribir cualquier línea de código, cada agente especialista asignado debe validar que su subtarea se alinea estrictamente con el contrato de interfaz definido en `plan.md` y `tasks.md`.*

### Directiva 2: Regla de Aislamiento de Alcance (*Scope Isolation*)
> *Ningún agente especialista puede modificar archivos fuera de su directiva `scope`. Si una funcionalidad requiere cambios transversales (ej. `agent_ui_desktop` necesita un nuevo método en `vpn_manager.py`), debe solicitar formalmente el cambio al Supervisor, quien delegará dicha modificación a `agent_vpn_core`.*

### Directiva 3: Regla de Conventional Commits
> *Cada agente debe empaquetar sus cambios de forma atómica respetando el estándar de **Conventional Commits** antes de dar por completada su tarea:*
> * `feat(ui): ...` — Nuevas capacidades visuales o widgets.
> * `feat(vpn): ...` — Nuevas funciones en el gestor de túneles o failover.
> * `fix(sec): ...` — Correcciones de seguridad o manejo de llavero.
> * `test(core): ...` — Incorporación o corrección de pruebas.
> * `refactor(scope): ...` — Reestructuración interna sin cambio de comportamiento.

### Directiva 4: Regla de Convergencia
> *Al finalizar las tareas paralelas, el Supervisor debe ejecutar `/speckit-converge` y `/code-review` para comprobar que la integración conjunta satisface al 100% la constitución del proyecto y la especificación sin generar colisiones ni regresiones.*
