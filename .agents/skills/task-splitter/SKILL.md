---
name: task-splitter
description: Disecciona especificaciones y planes técnicos de Spec-Kit en tareas atómicas y paralelizables asignadas al pool de agentes especialistas (UI, VPN Core, Seguridad, QA).
---

# Skill: /task-splitter (Disección Multi-Agente para OpenFortiVPN GUI)

Esta skill permite al **Supervisor de Arquitectura** fragmentar una especificación técnica (`spec.md`) o un plan de implementación (`plan.md`) en subtareas atómicas e independientes, preparadas para ejecución en paralelo por el pool de agentes especialistas del proyecto.

---

## 1. Cuándo Invocar Esta Skill

* Tras ejecutar `/speckit-plan` (o `/grill-me`), antes o durante la generación de `tasks.md`.
* Cuando una característica requiera cambios coordinados en interfaz gráfica, lógica de procesos VPN y persistencia en llavero.
* Para verificar que ninguna subtarea cree colisiones de archivos entre agentes simultáneos.

---

## 2. Mapa de Especialistas y Prefijos Obligatorios

Cada tarea diseccionada debe llevar un prefijo de dominio y un agente asignado:

| Prefijo de Tarea | Agente Asignado | Scope Autorizado | Ejemplo de Tarea |
|---|---|---|---|
| `[UI]` | `agent_ui_desktop` | `src/main.py`, `src/config_dialog.py`, `src/stats_panel.py`, `src/styles.py` | `[UI] Diseñar botón de reconexión rápida en MainWindow` |
| `[CORE]` | `agent_vpn_core` | `src/vpn_manager.py`, `configure_permissions.sh` | `[CORE] Agregar señal auto_reconnect_triggered en VpnManager` |
| `[SEC]` | `agent_security_storage` | `src/profile_manager.py`, `src/migration_utils.py` | `[SEC] Añadir clave auto_reconnect a esquema de perfiles` |
| `[TEST]` | `agent_qa_testing` | `tests/`, `install.sh`, `update.sh` | `[TEST] Escribir mock de fallo de red para validar reconexión` |

---

## 3. Protocolo de Disección (Algoritmo Paso a Paso)

Al invocar `/task-splitter`:

1. **Lectura de Artefactos**:
   * Cargar la especificación activa desde `.specify/feature.json` o `specs/<feature>/spec.md` y `plan.md`.
   * Cargar la [Constitución del Proyecto](file:///.specify/memory/constitution.md) para verificar que las tareas respeten las restricciones de seguridad (Keyring, permisos no privilegiados, no bloqueo de GUI).

2. **Detección de Interfaces y Contratos**:
   * Si dos componentes se comunican (ejemplo: `MainWindow` escucha una nueva señal de `VpnManager`), **definir primero la signatura de la señal/método** en el plan antes de codificar la UI.
   * La tarea del contrato se asigna a `[CORE]` o `[SEC]` como prerrequisito de `[UI]`.

3. **Verificación de Aislamiento (*Scope Check*)**:
   * Cada tarea debe tener un conjunto disjunto de archivos modificados respecto a las tareas marcadas para ejecución concurrente.
   * Si dos tareas tocan el mismo archivo (ej. `src/main.py`), deben serializarse en fases dependientes (Fase 1 -> Fase 2).

4. **Salida Estructurada**:
   * Formatear las tareas en formato `tasks.md` estándar de Spec-Kit:
     ```markdown
     ## Fase 1: Interfaces y Lógica Central
     - [ ] T001 [CORE] Implementar método X en src/vpn_manager.py (scope: vpn_core)
     - [ ] T002 [SEC] Actualizar esquema de guardado en src/profile_manager.py (scope: sec_storage)

     ## Fase 2: Presentación en Interfaz (Paralelo a Fase 1 o tras contratos)
     - [ ] T003 [UI] Conectar slots visuales en src/main.py (scope: ui_desktop)

     ## Fase 3: Pruebas y Validación
     - [ ] T004 [TEST] Crear test unitario en tests/test_feature.py (scope: qa_testing)
     ```

5. **Regla de Conventional Commits para Workers**:
   * Cada worker debe generar un commit atómico al terminar:
     * `[UI]` -> `feat(ui): ...` o `fix(ui): ...`
     * `[CORE]` -> `feat(vpn): ...` o `fix(vpn): ...`
     * `[SEC]` -> `feat(sec): ...` o `fix(sec): ...`
     * `[TEST]` -> `test(vpn): ...`
