# Integración de CopilotKit en SODA

Esta guía describe el estado actual de la integración de CopilotKit en SODA y cómo montarla sin romper el backend principal. El objetivo sigue siendo una interfaz de dos columnas: a la izquierda el stream técnico del orquestador y a la derecha la conversación con el consultor tipo Copilot.

## Estado actual

Hoy SODA ya tiene el backend preparado en [ui/server.py](d:/Desktop/iacomp/SODA-PROJECT/ui/server.py) y el agente consultor en [kernel/intelligence/copilot_consultant.py](d:/Desktop/iacomp/SODA-PROJECT/kernel/intelligence/copilot_consultant.py).

La integración Python es opcional:

- Si `copilotkit` está instalado en el entorno, SODA registra `/api/copilotkit` y la acción `resume_project(project_id)`.
- Si `copilotkit` no está instalado, el servidor sigue arrancando normalmente y simplemente no expone ese endpoint.
- El orquestador ya emite eventos `COPILOT_SUGGESTION` cuando el consultor detecta mejoras en blueprint o arquitectura.

## Arquitectura de UI

El diseño del Command Center para SODA Orchestrator se basa en React + TailwindCSS.

### 1. El Backend (Python / FastAPI)

SODA expone dos vías de comunicación hacia la interfaz React:
1. **WebSocket (`ws://localhost:8000/api/event`)**: Envía eventos de Solo Lectura como `AI_WORKING`, `MODULE_START` y `LOG` para ver cómo SODA itera.
2. **Copilot Endpoint (`/api/copilotkit`)**: Cuando CopilotKit Python está disponible, expone las **Copilot Actions** como `resume_project(project_id)` y maneja el estado de conversación del agente.

*(Para ver el código backend, revisa `ui/server.py` y el agente `kernel/intelligence/copilot_consultant.py` que inyecta pausas y sugerencias en el Orquestador).*

### Activación del backend Copilot

El backend actual usa import dinámico. No hace falta editar código para activarlo.

Pasos:

1. Instala la librería Python de CopilotKit compatible con FastAPI en el mismo entorno virtual de SODA.
2. Inicia el servidor FastAPI normalmente.
3. Verifica que `/api/copilotkit` responda solo cuando esa dependencia exista.

Si el paquete falta, eso ya no es un error fatal del servidor. Es un modo degradado esperado.

### 2. El Frontend (React)

Para utilizar esta integración, debes generar un frontend React (ej. Vite).

```bash
npm create vite@latest soda-ui -- --template react
cd soda-ui
npm install @copilotkit/react-core @copilotkit/react-ui tailwindcss postcss autoprefixer
```

Ese frontend React es complementario. No reemplaza la UI actual basada en FastAPI + pywebview; funciona como una capa alternativa o futura para el Command Center.

**Código Fuente de la Interfaz (App.jsx):**

```jsx
import React, { useEffect, useState } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

function App() {
  // Estado para la columna izquierda (Logs del Orquestador)
  const [aiLogs, setAiLogs] = useState([]);

  useEffect(() => {
    // Conexión al WebSocket original de SODA para capturar el monólogo de IA
    const ws = new WebSocket("ws://localhost:8000/api/event");
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // Filtramos eventos técnicos para renderizar el "Streaming" de Claude/Qwen/Gemini
      if (["AI_WORKING", "MODULE_START", "LOG", "COPILOT_SUGGESTION", "REFERENCE_ANALYSIS"].includes(data.event_type)) {
        setAiLogs((prev) => [...prev, data]);
      }
    };
    
    return () => ws.close();
  }, []);

  return (
    <div className="flex h-screen w-full bg-slate-900 text-slate-100 overflow-hidden">
      
      {/* COLUMNA IZQUIERDA: SODA Brain Stream (Monólogo de IA) */}
      <div className="w-1/2 h-full flex flex-col border-r border-slate-700">
        <div className="bg-slate-800 p-4 font-bold border-b border-slate-700">
          🧠 SODA Orchestrator Stream
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
          {aiLogs.map((log, i) => (
            <div key={i} className="p-3 rounded bg-slate-800 shadow-sm border border-slate-700">
              <span className="text-blue-400 font-bold">[{log.event_type}]</span>
              <p className="mt-1">{log.message}</p>
              {/* Si es una IA trabajando, mostramos su nombre */}
              {log.data?.ai && <p className="text-xs text-slate-400 mt-2">Iterando con: {log.data.ai}</p>}
            </div>
          ))}
          {aiLogs.length === 0 && <p className="text-slate-500 italic">Esperando inicio del pipeline...</p>}
        </div>
      </div>

      {/* COLUMNA DERECHA: CopilotKit (Consultor e Interacción Humana) */}
      <div className="w-1/2 h-full flex flex-col relative">
        <div className="bg-slate-800 p-4 font-bold border-b border-slate-700">
          🤖 Copilot Consultant
        </div>
        
        {/* Aquí inyectamos el entorno completo de CopilotKit y forzamos a que ocupe todo el espacio de esta columna */}
        <div className="flex-1 overflow-hidden relative">
          <CopilotKit runtimeUrl="http://localhost:8000/api/copilotkit">
            <CopilotChat
              instructions="Eres el Consultor Senior de SODA. Estás asistiendo al usuario mientras el equipo de IAs (Claude, Gemini, Qwen) programa en la otra pantalla. Si ves que el pipeline de SODA pausa y sugiere un cambio de arquitectura, explícaselo al usuario y pregúntale si aplicamos la acción."
              labels={{
                title: "SODA Copilot",
                initial: "¿En qué te puedo ayudar con tu proyecto de software?"
              }}
              // En lugar de Sidebar, lo incrustamos (inline) para la columna
              style={{ height: '100%', width: '100%', borderRadius: 0 }}
            />
          </CopilotKit>
        </div>
      </div>

    </div>
  );
}

export default App;
```

## Señales que ya emite SODA

La integración actual ya puede aprovechar estas señales del backend:

- `AI_WORKING`: una IA está ejecutando una tarea concreta.
- `MODULE_START` y `MODULE_DONE`: inicio y fin de generación por módulo.
- `COPILOT_SUGGESTION`: el consultor propone mejorar blueprint o arquitectura.
- `REFERENCE_ANALYSIS`: análisis de referencias externas cuando el usuario pide cambios inspirados en otra app o URL.
- `HEALTH_WARN`: advertencias por referencias potencialmente rotas o por problemas del pipeline.

## Funcionalidad Esperada

* **Visualización Dinámica:** Verás en la pantalla izquierda textos como `[AI_WORKING] Gemini — global_architect` cuando Gemini esté generando el diseño en Python.
* **Supervisión Asíncrona:** Si el orquestador detecta una oportunidad de mejora en blueprint o arquitectura, emitirá `COPILOT_SUGGESTION` y la UI puede mostrar ese mensaje en la columna derecha o en el stream técnico.
* **Reanudación remota:** La acción `resume_project(project_id)` ya está registrada cuando CopilotKit Python está disponible, de modo que el frontend puede reanudar proyectos pausados o en checkpoint.
* **Observabilidad de cambios inspirados en referencias:** Si el usuario pide "hacelo como X" usando URLs o referencias a otros productos, SODA ya genera `REFERENCE_ANALYSIS` en la ruta de modificación.

## Limitaciones actuales

- Hoy el backend solo registra una acción explícita de CopilotKit: `resume_project`.
- Las sugerencias del consultor ya existen en el orquestador, pero la UX final de aprobación en un frontend React todavía depende de la implementación del lado cliente.
- La dependencia Python de CopilotKit no está declarada aún en [pyproject.toml](d:/Desktop/iacomp/SODA-PROJECT/pyproject.toml), por lo que su instalación sigue siendo opt-in.
