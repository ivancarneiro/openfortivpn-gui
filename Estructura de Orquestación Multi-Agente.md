Para orquestar múltiples agentes en **Antigravity-IDE** partiendo de los requerimientos globales generados por /grill-me y la documentación técnica estructurada bajo tu flujo de **spek-kit**, debes configurar un flujo de trabajo jerárquico (*Supervisor/Worker Pattern*) dentro de la carpeta de directivas de tu entorno.

Como **Antigravity-IDE** opera a nivel de contexto mediante archivos de configuración locales, la disección y asignación paralela se automatiza creando un plano de orquestación en la raíz de tu espacio de trabajo.

## **📋 Estructura de Orquestación Multi-Agente**

Para indicarle al IDE cómo fragmentar las tareas basadas en tus pasos de **spek-kit** y asignarlas a agentes especialistas en paralelo, crea o edita tu archivo de flujos en .agent/workflows.json (o el formato homólogo que maneje tu versión de Antigravity-IDE) con la siguiente lógica de prompts e instrucciones:

`{`  
  `"workflow": "parallel_task_dissection",`  
  `"trigger": "Al finalizar la documentación de un paso en spek-kit",`  
  `"orchestrator_agent": {`  
    `"role": "Supervisor de Arquitectura",`  
    `"prompt": "Analiza las especificaciones globales de /grill-me y el paso actual documentado con spek-kit. Divide la implementación en subtareas independientes, atómicas y autocontenidas. Cada tarea debe poder ejecutarse en paralelo sin bloquear a las demás."`  
  `},`  
  `"agent_pool": [`  
    `{`  
      `"id": "agent_backend_db",`  
      `"specialty": "Modelos de datos y Persistencia",`  
      `"scope": ["src/models/", "src/migrations/"]`  
    `},`  
    `{`  
      `"id": "agent_backend_logic",`  
      `"specialty": "Controladores y Casos de Uso",`  
      `"scope": ["src/controllers/", "src/services/"]`  
    `},`  
    `{`  
      `"id": "agent_testing",`  
      `"specialty": "Pruebas Unitarias e Integración",`  
      `"scope": ["tests/"]`  
    `}`  
  `],`  
  `"execution_rules": {`  
    `"parallel": true,`  
    `"max_concurrent_agents": 3,`  
    `"version_control": "Cada agente debe empaquetar sus cambios de forma independiente utilizando estrictamente las reglas de **conventional commits** al proponer sus modificaciones."`  
  `}`  
`}`

## **🛠️ Configuración de Directivas Técnicas en .agent/rules.md**

Para asegurar que los agentes especialistas no colisionen y respeten tu flujo mandatorio, añade las siguientes directivas en tu archivo de reglas de Antigravity-IDE:

> * **Regla de Sincronización:** *"Antes de escribir código, cada agente asignado debe validar de forma aislada que su subtarea se alinee exactamente con el diseño del componente especificado en el paso de spek-kit."*  
> * **Regla de Aislamiento:** *"Los agentes asignados en paralelo solo tienen permitido modificar archivos dentro de su directiva scope. Si un agente requiere cambios fuera de su alcance, debe emitir una solicitud de interfaz al Agente Supervisor."*  
> * **Regla de Cierre de Tareas:** *"Cada agente concluirá su bloque de trabajo generando el mensaje de confirmación bajo el estándar mandatorio de conventional commits (ej. feat(auth): ... o fix(db): ...) antes de ceder el control para la consolidación final."*

Al estructurar tus archivos de configuración bajo este modelo, tu cuenta Pro de Gemini sabrá que debe actuar primero como un **orquestador de tareas** (diseccionando el spek-kit) y luego instanciar subprocesos paralelos (agentes virtuales aislados) para escribir el código simultáneamente, optimizando por completo tus tiempos de desarrollo.

Para arrancar el **Proyecto X desde cero** en Antigravity-IDE y estructurar de inmediato el entorno multi-agente paralelizado, debes seguir una secuencia estricta que va desde la concepción de la idea hasta la automatización del pipeline de desarrollo.

El orden cronológico de pasos y los archivos esenciales que debes crear antes de tirar la primera línea de código del software son los siguientes:

## ---

**Paso 1: Configurar el Entorno del Agente en el IDE**

Antes de interactuar con las herramientas, necesitas preparar el espacio para que Gemini reconozca las reglas del juego. Crea la estructura base de configuración en la raíz de tu directorio vacío.

> * 📁 **Crear carpeta:** .agent/  
> * 📄 **Crear archivo:** .agent/rules.md  
  * *Propósito:* Define las reglas globales de convivencia. Aquí debes declarar de forma explícita que **Conventional Commits** es obligatorio para cualquier agente o humano, y que se utilizará el framework **spec-kit** para documentar antes de programar. \[1, 2\]

## ---

**Paso 2: Ejecutar el proceso con /grill-me**

Con el entorno preparado, el primer paso operativo es consolidar la idea abstracta en requerimientos firmes.

> 1. **Ejecutar el comando o skill:** Lanza /grill-me apuntando a tu idea del **Proyecto X**.  
> 2. **Iteración:** Responde al cuestionario exhaustivo de la skill para desglosar el alcance, las restricciones y la arquitectura general.  
> 3. **Generar la salida:** Guarda el resultado definitivo en un archivo central de requerimientos.  
   * 📄 **Crear archivo:** docs/requirements/global\_spec.md

## ---

**Paso 3: Definir el "Plano de Construcción" (Spec-kit Base)**

Basándote en la especificación global de /grill-me, inicializa tu estructura de **Specification-Driven Development (SDD)**. \[2\]

> * 📄 **Crear archivo:** docs/spec-kit/template.md (El molde que usarán los agentes para entender el diseño técnico de cada componente).  
> * 📄 **Crear archivo:** docs/spec-kit/001\_architecture\_spec.md (La especificación inicial que detalla el stack tecnológico, base de datos y la interfaz de comunicación entre módulos).

## ---

**Paso 4: Crear el Orquestador y Flujo de Trabajo Multi-Agente**

Este es el paso clave para que Antigravity-IDE entienda cómo diseccionar las tareas basadas en el spec-kit y paralelizarlas.

> * 📄 **Crear archivo:** .agent/workflows/parallel\_dissection.json  
  * *Contenido:* Define el flujo de trabajo donde el **Agente Supervisor (Orquestador)** toma un archivo de docs/spec-kit/, lo divide en subtareas atómicas y las distribuye en un *pool* de agentes especialistas simultáneos (ej. Agente Base de Datos, Agente Lógica de Negocio, Agente Testing). \[1\]  
> * 📄 **Crear archivo:** .agent/skills/task-splitter/SKILL.md  
  * *Propósito:* Un prompt del sistema especializado para Gemini Pro que le enseña textualmente cómo agarrar un markdown de spec-kit y transformarlo en un JSON de tareas independientes asignables.

## ---

**Paso 5: Automatización de Git y Conventional Commits**

Para garantizar que ningún agente rompa las reglas de control de versiones. \[1\]

> * 📄 **Crear archivo:** .husky/commit-msg o un script de Git Hook equivalente soportado por tu repositorio local.  
  * *Propósito:* Bloquear cualquier confirmación (tanto tuya como de los sub-agentes) que no cumpla con la estructura de un *Conventional Commit* (feat:, fix:, docs:, etc.).

## ---

**Resumen del árbol de archivos inicial (Listo para el primer commit)**

`proyecto-x/`  
`├── .agent/`  
`│   ├── rules.md                     <-- Mandatos de spec-kit y conventional commits`  
`│   ├── workflows/`  
`│   │   └── parallel_dissection.json <-- Reglas de disección y pool de agentes`  
`│   └── skills/`  
`│       └── task-splitter/`  
`│           └── SKILL.md             <-- Instrucciones de fragmentación para Gemini`  
`├── docs/`  
`│   ├── requirements/`  
`│   │   └── global_spec.md           <-- Salida consolidada de /grill-me`  
`│   └── spec-kit/`  
`│       ├── template.md              <-- Estructura base de tus especificaciones`  
`│       └── 001_architecture_spec.md <-- Primera especificación técnica del sistema`  
`└── .gitignore`

Una vez que tengas esta estructura en tu directorio, el flujo operativo del proyecto consistirá en pedirle al **Agente Supervisor** que lea el archivo 001\_architecture\_spec.md, ejecute la skill de disección, y verás cómo Antigravity-IDE levanta las subtareas en paralelo para codificar respetando tu estándar estricto de commits. \[1\]