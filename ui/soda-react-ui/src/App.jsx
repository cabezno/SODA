import React, { useCallback, useEffect, useRef, useState } from "react";
import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import "./App.css";

// --- XTerm.js imports ---
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";

// ── Interactive Terminal Component ──────────────────────────────────────────────
function InteractiveTerminal({ visible, projectId }) {
  const termRef = useRef(null);
  const xtermRef = useRef(null);
  const wsRef = useRef(null);
  const fitAddonRef = useRef(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (!termRef.current || initialized.current) return;
    initialized.current = true;

    const term = new Terminal({ theme: { background: '#0a0a0a' }, fontSize: 12, cursorBlink: true });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current);
    fitAddon.fit();
    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    const sessionId = "term_" + Date.now();
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    let url = `${proto}://${window.location.host}/ws/terminal/${sessionId}`;
    if (projectId) url += `?project_id=${projectId}`;
    
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = async (e) => {
      if (e.data instanceof Blob) {
        const text = await e.data.text();
        term.write(text);
      } else {
        term.write(e.data);
      }
    };

    term.onData(data => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    const handleResize = () => fitAddon.fit();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
      term.dispose();
      initialized.current = false;
    };
  }, [projectId]);

  useEffect(() => {
    if (visible && fitAddonRef.current) {
      setTimeout(() => fitAddonRef.current.fit(), 100);
    }
  }, [visible]);

  return <div ref={termRef} style={{ height: "100%", width: "100%", display: visible ? "block" : "none", padding: "8px" }} />;
}

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
function usePipelineEvents(speak, addSandboxLine, setN8nProjectId) {
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
        } else if (msg.event_type === "N8N_READY") {
          setN8nProjectId(msg.data?.project_id || null);
        }
        // Sandbox events → terminal panel
        if (msg.event_type?.startsWith("SANDBOX")) {
          const isError = msg.event_type === "SANDBOX_ERROR";
          addSandboxLine({ text: msg.message, error: isError, ts: new Date().toLocaleTimeString() });
        }
      } catch (_) {}
    };

    return () => ws.close();
  }, [speak, addSandboxLine, setN8nProjectId]);
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
  const [tab, setTab] = useState("logs"); // "logs" | "term"

  useEffect(() => {
    if (visible && bottomRef.current && tab === "logs") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, visible, tab]);

  return (
    <div style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 100,
      background: "#0a0a0a", borderTop: "1px solid #1a1a2e",
      transition: "height 0.2s ease",
      height: visible ? "280px" : "32px",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header bar */}
      <div
        style={{
          height: "32px", minHeight: "32px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 12px", cursor: "pointer",
          background: "#0f0f1a", borderBottom: visible ? "1px solid #1a1a2e" : "none",
          userSelect: "none",
        }}
      >
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <span onClick={onToggle} style={{ fontSize: "11px", color: "#7c7caf", fontFamily: "monospace", letterSpacing: "0.05em" }}>
            ▣ SANDBOX
          </span>
          {visible && (
            <>
              <span onClick={() => setTab("logs")} style={{ fontSize: "11px", color: tab === "logs" ? "#fff" : "#555", cursor: "pointer" }}>Logs {lines.length > 0 ? `(${lines.length})` : ""}</span>
              <span onClick={() => setTab("term")} style={{ fontSize: "11px", color: tab === "term" ? "#fff" : "#555", cursor: "pointer" }}>Interactive Terminal</span>
            </>
          )}
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          {visible && tab === "logs" && (
            <span
              onClick={(ev) => { ev.stopPropagation(); onClear(); }}
              style={{ fontSize: "11px", color: "#555", cursor: "pointer" }}
            >
              limpiar logs
            </span>
          )}
          <span onClick={onToggle} style={{ fontSize: "11px", color: "#7c7caf" }}>{visible ? "▼" : "▲"}</span>
        </div>
      </div>

      {/* Content */}
      {visible && (
        <div style={{ flex: 1, overflow: "hidden", display: "flex", position: "relative" }}>
          {tab === "logs" && (
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
          <InteractiveTerminal visible={tab === "term"} projectId="" />
        </div>
      )}
    </div>
  );
}

// ── Inner component ───────────────────────────────────────────────────────────
function SodaChat({ addSandboxLine, setN8nProjectId }) {
  const speak = useTTSPlayer();
  usePipelineEvents(speak, addSandboxLine, setN8nProjectId);
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
  const [finopsMode, setFinopsMode] = useState(true);
  const [n8nProjectId, setN8nProjectId] = useState(null);
  const hasNew = useRef(false);

  useEffect(() => {
    fetch("/api/finops/status")
      .then(r => r.json())
      .then(d => { if (d && typeof d.finops_mode === "boolean") setFinopsMode(d.finops_mode); })
      .catch(() => {});
  }, []);

  const toggleFinops = useCallback(() => {
    fetch("/api/finops/toggle", { method: "POST" })
      .then(r => r.json())
      .then(d => { if (d && typeof d.finops_mode === "boolean") setFinopsMode(d.finops_mode); })
      .catch(() => {});
  }, []);

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
      <header className="bmb-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="bmb-monogram">BMB</span>
          <span className="bmb-subtitle">BlackMagicBox Soda</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginRight: '16px' }}>
          {n8nProjectId && (
            <a
              href={`/api/projects/${n8nProjectId}/n8n_workflow`}
              download="n8n_workflow.json"
              title="Descargar workflow n8n para importar"
              onClick={() => setN8nProjectId(null)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                background: '#ff6d3b', color: '#fff',
                border: 'none', padding: '6px 14px', borderRadius: '6px',
                fontSize: '12px', fontWeight: '600', textDecoration: 'none',
                cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              ⬇ n8n workflow
            </a>
          )}
          <div
            title="Elige el modelo: FinOps (Económico/Rápido) o Premium (Máxima Calidad)"
            style={{ display: 'flex', background: '#1a1a2e', borderRadius: '8px', padding: '4px', gap: '4px' }}
          >
          <button 
            onClick={() => !finopsMode && toggleFinops()}
            style={{ 
              background: finopsMode ? '#34d399' : 'transparent', 
              color: finopsMode ? '#000' : '#a0aec0',
              border: 'none', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600',
              transition: 'all 0.2s'
            }}
          >
            ⚡ Flash (FinOps)
          </button>
          <button 
            onClick={() => finopsMode && toggleFinops()}
            style={{ 
              background: !finopsMode ? '#3b82f6' : 'transparent', 
              color: !finopsMode ? '#000' : '#a0aec0',
              border: 'none', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '600',
              transition: 'all 0.2s'
            }}
          >
            💎 Pro (Premium)
          </button>
          </div>
        </div>
      </header>

      <div style={{ flex: 1, overflow: "hidden", paddingBottom: terminalOpen ? "220px" : "32px" }}>
        <CopilotKit runtimeUrl="/api/copilotkit">
          <SodaChat addSandboxLine={addSandboxLine} setN8nProjectId={setN8nProjectId} />
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
