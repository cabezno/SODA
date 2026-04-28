import React, { useCallback, useEffect, useRef, useState } from "react";
import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import "./App.css";

// ── F5-TTS player ─────────────────────────────────────────────────────────────
function useTTSPlayer() {
  const queue = useRef([]);
  const busy  = useRef(false);

  const processQueue = useCallback(async () => {
    if (busy.current || queue.current.length === 0) return;
    busy.current = true;
    const text = queue.current.shift();
    try {
      const res = await fetch("/api/tts/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        await new Promise((resolve) => {
          const audio = new Audio(url);
          audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
          audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
          audio.play().catch(resolve);
        });
      }
    } catch (_) {}
    busy.current = false;
    processQueue();
  }, []);

  const speak = useCallback((text) => {
    if (!text?.trim()) return;
    queue.current.push(text.trim());
    processQueue();
  }, [processQueue]);

  return speak;
}

// ── Pipeline event listener + sandbox events ──────────────────────────────────
function usePipelineEvents(speak, addSandboxLine) {
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event_type === "USER_QUESTION") {
          speak(msg.data?.question || msg.message);
        } else if (msg.event_type === "DONE") {
          speak("Proyecto terminado. El código está listo.");
        } else if (msg.event_type === "TTS_SPEAK") {
          speak(msg.message);
        }
        // Sandbox events → terminal panel
        if (msg.event_type?.startsWith("SANDBOX")) {
          const isError = msg.event_type === "SANDBOX_ERROR";
          addSandboxLine({ text: msg.message, error: isError, ts: new Date().toLocaleTimeString() });
        }
      } catch (_) {}
    };

    return () => ws.close();
  }, [speak, addSandboxLine]);
}

// ── CopilotKit chat response listener ─────────────────────────────────────────
function useChatTTS(speak) {
  const { visibleMessages } = useCopilotChat();
  const lastId = useRef(null);

  useEffect(() => {
    if (!visibleMessages?.length) return;
    const last = visibleMessages[visibleMessages.length - 1];
    if (!last || last.role !== "assistant") return;
    const id = last.id ?? last.content;
    if (id === lastId.current) return;
    lastId.current = id;
    let text = "";
    if (typeof last.content === "string") text = last.content;
    else if (Array.isArray(last.content)) text = last.content.map((c) => c?.text ?? "").join(" ");
    speak(text);
  }, [visibleMessages, speak]);
}

// ── Sandbox Terminal panel ─────────────────────────────────────────────────────
function SandboxTerminal({ lines, visible, onToggle, onClear }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    if (visible && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, visible]);

  return (
    <div style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 100,
      background: "#0a0a0a", borderTop: "1px solid #1a1a2e",
      transition: "height 0.2s ease",
      height: visible ? "220px" : "32px",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header bar */}
      <div
        onClick={onToggle}
        style={{
          height: "32px", minHeight: "32px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 12px", cursor: "pointer",
          background: "#0f0f1a", borderBottom: visible ? "1px solid #1a1a2e" : "none",
          userSelect: "none",
        }}
      >
        <span style={{ fontSize: "11px", color: "#7c7caf", fontFamily: "monospace", letterSpacing: "0.05em" }}>
          ▣ SANDBOX TERMINAL {lines.length > 0 ? `(${lines.length})` : ""}
        </span>
        <div style={{ display: "flex", gap: "12px" }}>
          {visible && (
            <span
              onClick={(ev) => { ev.stopPropagation(); onClear(); }}
              style={{ fontSize: "11px", color: "#555", cursor: "pointer" }}
            >
              limpiar
            </span>
          )}
          <span style={{ fontSize: "11px", color: "#7c7caf" }}>{visible ? "▼" : "▲"}</span>
        </div>
      </div>

      {/* Log output */}
      {visible && (
        <div style={{
          flex: 1, overflowY: "auto", padding: "6px 12px",
          fontFamily: "Consolas, monospace", fontSize: "12px", lineHeight: "1.5",
        }}>
          {lines.length === 0 ? (
            <span style={{ color: "#333" }}>Sin actividad del sandbox aún...</span>
          ) : (
            lines.map((l, i) => (
              <div key={i} style={{ color: l.error ? "#ff5555" : "#88c0d0", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                <span style={{ color: "#444", marginRight: "8px" }}>{l.ts}</span>
                {l.text}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

// ── Inner component ───────────────────────────────────────────────────────────
function SodaChat({ addSandboxLine }) {
  const speak = useTTSPlayer();
  usePipelineEvents(speak, addSandboxLine);
  useChatTTS(speak);

  return (
    <CopilotChat
      instructions={`Eres el asistente de BlackMagicBox SODA, sistema de generación automática de software.

REGLA OBLIGATORIA: antes de crear cualquier proyecto SIEMPRE preguntá al usuario qué temperatura de Copilot quiere usar y explicá las opciones:

  baja  — máximo 1 pasada de revisión. Generación rápida, bajo consumo de tokens.
  media — máximo 3 pasadas. Equilibrio entre calidad y tiempo. (recomendado)
  alta  — todas las pasadas necesarias. Código más refinado, pero más lento y costoso en tokens.

Solo después de que el usuario elija, usá la acción create_project con: project_name, description y copilot_temperature.

Para otros temas respondé en español de forma concisa.`}
      labels={{
        title: "",
        initial: "¡Hola! Puedo crear proyectos de software completos.\n¿Qué querés construir hoy?"
      }}
      style={{ height: "100%", width: "100%" }}
    />
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────
function App() {
  const [sandboxLines, setSandboxLines] = useState([]);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const hasNew = useRef(false);

  const addSandboxLine = useCallback((line) => {
    setSandboxLines((prev) => [...prev.slice(-500), line]);
    hasNew.current = true;
    // Auto-open on first error
    if (line.error) setTerminalOpen(true);
  }, []);

  return (
    <div style={{
      background: "#000000", color: "#ffffff",
      fontFamily: '"Segoe UI", sans-serif',
      height: "100vh", width: "100vw", overflow: "hidden",
      margin: 0, padding: 0, display: "flex", flexDirection: "column",
    }}>
      <header className="bmb-header">
        <span className="bmb-monogram">BMB</span>
        <span className="bmb-subtitle">BlackMagicBox Soda</span>
      </header>

      <div style={{ flex: 1, overflow: "hidden", paddingBottom: terminalOpen ? "220px" : "32px" }}>
        <CopilotKit runtimeUrl="/api/copilotkit">
          <SodaChat addSandboxLine={addSandboxLine} />
        </CopilotKit>
      </div>

      <SandboxTerminal
        lines={sandboxLines}
        visible={terminalOpen}
        onToggle={() => setTerminalOpen((v) => !v)}
        onClear={() => setSandboxLines([])}
      />
    </div>
  );
}

export default App;
