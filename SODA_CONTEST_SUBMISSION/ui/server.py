import os
import re
import sys
import json
import asyncio
import importlib
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 stdout/stderr on Windows to avoid charmap errors with Unicode
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ui.websocket_handler import manager
from kernel.resource_monitor import ResourceMonitor
from kernel.execution.project_runner import ProjectRunner
from kernel.projects.project_manager import ProjectManager
from kernel.projects.project_types import ProjectTypeRegistry
from kernel.monitoring.usage_monitor import UsageMonitor
from kernel.monitoring.alert_manager import AlertManager
from kernel.capabilities.capability_packs import CapabilityPackRegistry
from kernel.communication.project_chat import ProjectChat
from kernel.external.web_researcher import WebResearcher
from kernel.external.system_actions import SystemActionsExecutor
from kernel.external.tool_registry import ExternalToolRegistry
from kernel.intelligence.reference_analyzer import ReferenceAnalyzer
from kernel.vision.vision_capturer import VisionCapturer
from kernel.vision.visual_inspector import VisualInspector
from kernel.orchestration.intensity_orchestrator import IntensityOrchestrator

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

_SERVER_PORT = int(os.environ.get("SODA_PORT", 8000))

from contextlib import asynccontextmanager

# Telegram gateway — bot starts on uvicorn startup, not on import
def _get_telegram():
    return _get_orchestrator()._get_shared_telegram()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Telegram bot
    tg = _get_telegram()
    if tg._token:
        tg.start_bot()
    yield
    # Shutdown: Kill all processes
    try:
        _project_runner.kill_all()
    except Exception:
        pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _copilotkit_telegram_bridge(request: Request, call_next):
    """Forward the latest user message from CopilotKit chat to Telegram."""
    if request.url.path.startswith("/api/copilotkit") and request.method == "POST":
        try:
            raw = await request.body()
            data = json.loads(raw)
            messages = data.get("messages") or data.get("inputs", {}).get("messages", [])
            for msg in reversed(messages):
                role = msg.get("role", "")
                if role == "user":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            c.get("text", "") for c in content if isinstance(c, dict)
                        )
                    content = (content or "").strip()
                    if content:
                        # Lazy import to avoid circular dependency at module load
                        async def _fwd(c=content):
                            try:
                                from ui.server import _telegram
                                await _get_telegram().send_from_loop(f"[Chat] {c[:400]}")
                            except Exception:
                                pass
                        asyncio.create_task(_fwd())
                    break
        except Exception:
            pass
        # Reconstruct request so the downstream handler can still read the body
        async def _receive(body=raw):
            return {"type": "http.request", "body": body, "more_body": False}
        request = Request(request.scope, _receive)
    return await call_next(request)

copilotkit = None
add_fastapi_endpoint = None
CopilotKitRemoteEndpoint = None
Action = None
_copilotkit_loaded = False

try:
    from copilotkit.integrations.fastapi import add_fastapi_endpoint
    from copilotkit import CopilotKitRemoteEndpoint, Action
    _copilotkit_loaded = True
    print("[OK] CopilotKit Remote Endpoint loaded successfully.")
except Exception as e:
    print(f"[WARN] Failed to load CopilotKit: {e}")

async def action_resume_project(project_id: str):
    from kernel.orchestrator import SodaOrchestrator
    try:
        orch = _get_orchestrator()
        asyncio.create_task(orch.resume(project_id))
        return f"Proceso de reanudación iniciado para {project_id}."
    except Exception as e:
        return f"Error al reanudar: {str(e)}"


async def action_create_project(
    project_name: str,
    description: str,
    copilot_temperature: str,
):
    """CopilotKit action: create a new project with chosen Copilot temperature."""
    global _active_orchestrator
    temp = (copilot_temperature or "media").strip().lower()
    if temp not in ("baja", "media", "alta"):
        temp = "media"

    async def _run():
        global _pipeline_running, _active_orchestrator
        if not await _try_acquire_pipeline():
            await _get_telegram().send_from_loop("❌ Pipeline ya en ejecución")
            return
        try:
            from kernel.orchestrator import SodaOrchestrator
            orch = _get_orchestrator(copilot_temperature=temp)
            _active_orchestrator = orch
            await orch.run(description, project_name=project_name)
            await _get_telegram().send_from_loop(f"✅ Proyecto '{project_name}' generado. Temperatura: {temp}")
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
            await _get_telegram().send_from_loop(f"❌ Pipeline falló: {str(e)[:200]}")
        finally:
            await _release_pipeline()

    asyncio.create_task(_run())
    labels = {"baja": "1 pasada", "media": "3 pasadas", "alta": "ilimitado"}
    return (
        f"Proyecto '{project_name}' iniciado con temperatura {temp} "
        f"({labels.get(temp, temp)}). "
        f"Te aviso cuando termine."
    )


if _copilotkit_loaded:
    sdk = CopilotKitRemoteEndpoint(
        actions=[
            Action(
                name="resume_project",
                description="Resume a paused or AWAITING_CHECKPOINT SODA project by ID.",
                handler=action_resume_project,
                parameters=[
                    {"name": "project_id", "type": "string",
                     "description": "The ID of the project to resume"}
                ]
            ),
            Action(
                name="create_project",
                description=(
                    "Create a new SODA software project. "
                    "MANDATORY: you MUST ask the user which copilot_temperature they want BEFORE calling this action. "
                    "Present all three options and wait for the user's explicit choice. "
                    "Never assume or default — only call after the user picks one."
                ),
                handler=action_create_project,
                parameters=[
                    {"name": "project_name", "type": "string",
                     "description": "Short identifier for the project (letters, numbers, underscores)"},
                    {"name": "description", "type": "string",
                     "description": "Full description of what the application should do"},
                    {"name": "copilot_temperature", "type": "string",
                     "enum": ["baja", "media", "alta"],
                     "description": "Copilot review intensity chosen by the user: 'baja' (1 pass, fast), 'media' (3 passes, balanced), 'alta' (unlimited, best quality). Must be explicitly selected by user."},
                ]
            ),
        ]
    )
    add_fastapi_endpoint(app, sdk, "/api/copilotkit")

monitor = ResourceMonitor()
CONFIG_FILE = "soda_config.json"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
ENV_KEYS = ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL", "TELEGRAM_BOT_TOKEN"]
SODA_CONFIG_PATH = Path(__file__).resolve().parent.parent / "soda_config.json"


def _read_config() -> dict:
    try:
        if SODA_CONFIG_PATH.exists():
            return json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_config(cfg: dict) -> None:
    SODA_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

_pipeline_running = False
_register_lock = asyncio.Lock()
_active_orchestrator = None  # Caché global — evita recrear 40 componentes en cada request

def _get_orchestrator(copilot_temperature: str = "media") -> 'SodaOrchestrator':
    """Retorna el orquestador cacheado. Crea uno nuevo solo si no existe.
    NOTA: copilot_temperature solo se usa en la primera creación.
    """
    global _active_orchestrator
    if _active_orchestrator is None:
        from kernel.orchestrator import SodaOrchestrator
        _active_orchestrator = SodaOrchestrator(copilot_temperature=copilot_temperature)
        
        # [CONECTIVIDAD REPARADA] Inyectar callback de broadcast para desacoplar el kernel de la UI
        async def _broadcast(payload):
            try:
                from ui.websocket_handler import manager as _manager
                await _manager.broadcast(payload)
            except Exception:
                pass
        
        _active_orchestrator.set_broadcast_callback(_broadcast)

    return _active_orchestrator


async def _try_acquire_pipeline() -> bool:
    """Intenta adquirir el lock del pipeline. Retorna True si se obtuvo."""
    global _pipeline_running
    async with _register_lock:
        if _pipeline_running:
            return False
        _pipeline_running = True
        return True


async def _release_pipeline() -> None:
    """Libera el lock del pipeline."""
    global _pipeline_running
    async with _register_lock:
        _pipeline_running = False

_project_runner = ProjectRunner()
_project_manager = ProjectManager(Path(__file__).resolve().parent.parent)
_project_type_registry = ProjectTypeRegistry()
_usage_monitor = UsageMonitor(Path(__file__).resolve().parent.parent / "data" / "usage_metrics.db")
_alert_manager = AlertManager(_usage_monitor)
_capability_pack_registry = CapabilityPackRegistry()
_project_chat = ProjectChat()
_system_actions = SystemActionsExecutor(_project_manager)
_tool_registry = ExternalToolRegistry()
_web_researcher = WebResearcher()
_reference_analyzer = ReferenceAnalyzer()
_vision_capturer = VisionCapturer()
_visual_inspector = VisualInspector()
_intensity_orchestrator = IntensityOrchestrator()

# Telegram gateway — bot starts on uvicorn startup, not on import
from kernel.communication.telegram_gateway import TelegramGateway as _TG
_telegram = _TG()


from fastapi.staticfiles import StaticFiles

_react_assets = os.path.join(os.path.dirname(__file__), "soda-react-ui", "dist", "assets")
if os.path.isdir(_react_assets):
    app.mount("/assets", StaticFiles(directory=_react_assets), name="assets")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/copilot")
async def get_copilot_ui():
    """Sirve la nueva interfaz de React con CopilotKit."""
    react_index = os.path.join(os.path.dirname(__file__), "soda-react-ui", "dist", "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    return JSONResponse({"status": "error", "message": "Copilot UI not built yet."}, status_code=404)

@app.get("/")
async def get_index():
    response = FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/api/stats")
async def get_stats():
    return {
        "vram": monitor.get_vram_info(),
        "system": monitor.get_system_stats(),
        "recommendation": monitor.get_best_model(),
    }


@app.get("/api/ram_total")
async def get_ram_total():
    import psutil
    return {"ram_total_gb": psutil.virtual_memory().total / (1024 ** 3)}


@app.post("/api/run")
async def run_pipeline(request: Request):
    global _pipeline_running
    if _pipeline_running:
        return JSONResponse({"status": "busy", "message": "Pipeline already running"}, status_code=409)

    body = await request.json()
    description = (body.get("description") or "").strip()
    project_name = (body.get("project_name") or "").strip() or None
    copilot_temperature = (body.get("copilot_temperature") or "media").strip().lower()
    if copilot_temperature not in ("baja", "media", "alta"):
        copilot_temperature = "media"
    if not description:
        return JSONResponse({"status": "error", "message": "Description is required"}, status_code=400)
    if not project_name:
        return JSONResponse({"status": "error", "message": "project_name is required"}, status_code=400)

    async def _run():
        global _pipeline_running, _active_orchestrator
        _pipeline_running = True
        project_obj = None
        try:
            from kernel.orchestrator import SodaOrchestrator
            from kernel.drivers.gemini_driver import GeminiDriver
            from kernel.drivers.ollama_driver import OllamaDriver
            import asyncio
            from kernel.core.models_v2 import SodaContract, ContractInterface, DynamicPersona
            

            orchestrator = _get_orchestrator(copilot_temperature=copilot_temperature)
            _active_orchestrator = orchestrator
            project_obj = await orchestrator.run(description, project_name=project_name)
            await _get_telegram().send_from_loop(f"✅ Proyecto '{project_name}' generado exitosamente.")
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
            await _get_telegram().send_from_loop(f"❌ Pipeline falló: {str(e)[:200]}")
        finally:
            _pipeline_running = False

        # Auto-launch the generated project and stream output to the console.
        # Skip for docker-compose stacks — BootAgent already started the containers
        # in detached mode; re-running docker-compose would double-start them.
        if project_obj is not None:
            try:
                run_cmd = (project_obj.blueprint or {}).get("comando_ejecucion", "")
                source_dir = _project_manager.source_dir(project_obj.id)
                workspace = _project_manager.project_dir(project_obj.id)
                _is_compose = "docker-compose" in run_cmd or "docker compose" in run_cmd
                if run_cmd and source_dir.exists() and not _is_compose:
                    asyncio.create_task(
                        _stream_process(project_obj.id, run_cmd, str(source_dir), str(workspace))
                    )
            except Exception:
                pass

    asyncio.create_task(_run())
    return {"status": "started"}


@app.get("/api/status")
async def get_status():
    return {"running": _pipeline_running}


@app.post("/api/modify")
async def modify_project(request: Request):
    if _pipeline_running:
        return JSONResponse({"status": "busy"}, status_code=409)
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    user_request = (body.get("request") or "").strip()
    if not user_request:
        return JSONResponse({"status": "error", "message": "request is required"}, status_code=400)

    import json
    from pathlib import Path
    from kernel.orchestrator import SodaOrchestrator, Project, ProjectState

    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    meta = _project_manager.load_metadata(project_id)
    project = Project(
        id=meta["id"],
        description=meta["description"],
        state=ProjectState(meta["state"]),
        workspace=_project_manager.project_dir(project_id),
        blueprint=meta.get("blueprint", {}),
        architecture=meta.get("architecture", {}),
        skills=meta.get("skills", []),
        profile=meta.get("profile", ""),
    )

    orchestrator = _get_orchestrator()
    result = await orchestrator.modify(project, user_request)
    return {"status": "ok", "result": result}


@app.get("/api/lineage")
async def get_lineage():
    from pathlib import Path
    from kernel.lineage.project_lineage import ProjectLineage
    lineage = ProjectLineage(Path(__file__).resolve().parent.parent)
    projects_dir = Path(__file__).resolve().parent.parent / "projects"
    history = [
        e for e in lineage.get_history()
        if (projects_dir / e["project_id"] / "metadata.json").exists()
    ]
    return {"history": history}


@app.get("/api/lineage/{project_id}/branches")
async def get_branches(project_id: str):
    from pathlib import Path
    from kernel.lineage.branching import BranchManager
    bm = BranchManager(Path(__file__).resolve().parent.parent / "projects")
    return {"branches": bm.list_branches(project_id)}


@app.post("/api/refound")
async def refound_project(request: Request):
    if _pipeline_running:
        return JSONResponse({"status": "busy"}, status_code=409)
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        return JSONResponse({"status": "error", "message": "project_id required"}, status_code=400)

    import json
    from pathlib import Path
    from kernel.orchestrator import SodaOrchestrator, Project, ProjectState

    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    meta = _project_manager.load_metadata(project_id)
    project = Project(
        id=meta["id"], description=meta["description"],
        state=ProjectState(meta["state"]),
        workspace=_project_manager.project_dir(project_id),
        blueprint=meta.get("blueprint", {}),
        architecture=meta.get("architecture", {}),
        skills=meta.get("skills", []),
        profile=meta.get("profile", ""),
    )

    async def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            orch = _get_orchestrator()
            await orch.refound(project)
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
        finally:
            _pipeline_running = False

    asyncio.create_task(_run())
    return {"status": "started"}


@app.post("/api/resume")
async def resume_project(request: Request):
    global _pipeline_running, _active_orchestrator
    if _pipeline_running:
        return JSONResponse({"status": "busy"}, status_code=409)
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        return JSONResponse({"status": "error", "message": "project_id required"}, status_code=400)
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    async def _run():
        global _pipeline_running, _active_orchestrator
        _pipeline_running = True
        try:
            from kernel.orchestrator import SodaOrchestrator
            orch = _get_orchestrator()
            _active_orchestrator = orch
            await orch.resume(project_id)
            await _get_telegram().send_from_loop(f"Proyecto '{project_id}' reanudado y completado.")
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
        finally:
            if 'orch' in locals(): orch.cleanup_context()
            _pipeline_running = False

    asyncio.create_task(_run())
    return {"status": "started", "project_id": project_id}


@app.get("/api/projects/truncated")
async def get_truncated_projects():
    """Return projects that are in development/failed state (resumable)."""
    try:
        all_projects = _project_manager.list_all()
        resumable_states = {"development", "architecture", "requirements", "planning", "failed"}
        truncated = [
            p for p in all_projects
            if p.get("state") in resumable_states
        ]
        return {"projects": truncated}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/analyze_code")
async def analyze_code(request: Request):
    """Analyze user-provided code with Claude and return structured interpretation."""
    body = await request.json()
    code = (body.get("code") or "").strip()
    filename = (body.get("filename") or "main.py").strip()
    if not code:
        return JSONResponse({"status": "error", "message": "No se proporcionó código"}, status_code=400)

    from kernel.drivers.gemini_driver import GeminiDriver
    driver = GeminiDriver()

    system_prompt = (
        "Sos un experto en análisis de código. Analizás código fuente y devolvés EXCLUSIVAMENTE "
        "un JSON válido sin texto adicional, sin markdown, sin explicaciones."
    )
    user_prompt = f"""Analizá este código del archivo "{filename}" y devolvé un JSON con esta estructura exacta:
{{
  "language": "nombre del lenguaje principal",
  "frameworks": ["lista", "de", "frameworks", "detectados"],
  "stack": "descripción concisa del stack tecnológico",
  "summary": "descripción en 2-3 oraciones de qué hace este código",
  "capabilities": ["funcionalidad 1", "funcionalidad 2", "funcionalidad 3"],
  "architecture_type": "monolítico | microservicio | librería | CLI | API REST | etc",
  "entry_point": "archivo o función principal detectada",
  "dependencies": ["dep1", "dep2"],
  "install_command": "comando de instalación si se puede inferir (o vacío)",
  "run_command": "comando de ejecución si se puede inferir (o vacío)",
  "suggestions": [
    "Sugerencia 1 de qué se podría hacer con este código",
    "Sugerencia 2",
    "Sugerencia 3"
  ]
}}

CÓDIGO A ANALIZAR:
```
{code[:6000]}
```"""

    result = await driver.call(system_prompt, user_prompt, max_tokens=1024, temperature=0.1, response_format="json")
    content = result.content if hasattr(result, "content") else str(result)

    if content.startswith("ERROR:"):
        return JSONResponse({"status": "error", "message": content}, status_code=500)

    try:
        import json as _json
        analysis = _json.loads(content)
        return {"status": "ok", "analysis": analysis}
    except Exception:
        # Try to extract JSON from response
        import re, json as _json
        m = re.search(r'\{[\s\S]+\}', content)
        if m:
            try:
                analysis = _json.loads(m.group())
                return {"status": "ok", "analysis": analysis}
            except Exception:
                pass
        return JSONResponse({"status": "error", "message": "No se pudo parsear el análisis", "raw": content[:400]}, status_code=500)


@app.post("/api/run_from_code")
async def run_from_code(request: Request):
    """Start a SODA pipeline from user-provided existing code."""
    global _pipeline_running
    if _pipeline_running:
        return JSONResponse({"status": "busy", "message": "Pipeline en ejecución"}, status_code=409)

    body = await request.json()
    code         = (body.get("code") or "").strip()
    filename     = (body.get("filename") or "main.py").strip()
    intent       = (body.get("intent") or "").strip()
    project_name = (body.get("project_name") or "").strip()
    analysis     = body.get("analysis") or {}
    copilot_temperature = (body.get("copilot_temperature") or "media").strip().lower()

    if not code:
        return JSONResponse({"status": "error", "message": "No se proporcionó código"}, status_code=400)
    if not intent:
        return JSONResponse({"status": "error", "message": "Indicá qué querés hacer con el código"}, status_code=400)
    if not project_name:
        return JSONResponse({"status": "error", "message": "El nombre del proyecto es obligatorio"}, status_code=400)

    async def _run():
        global _pipeline_running, _active_orchestrator
        _pipeline_running = True
        try:
            from kernel.orchestrator import SodaOrchestrator
            from kernel.drivers.gemini_driver import GeminiDriver
            from kernel.drivers.ollama_driver import OllamaDriver
            import asyncio
            from kernel.core.models_v2 import SodaContract, ContractInterface, DynamicPersona
            

            orchestrator = _get_orchestrator(copilot_temperature=copilot_temperature)
            _active_orchestrator = orchestrator
            await orchestrator.import_from_code(code, filename, analysis, intent, project_name)
            await _get_telegram().send_from_loop(f"✅ Proyecto '{project_name}' generado desde código existente.")
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
            await _get_telegram().send_from_loop(f"❌ Pipeline desde código falló: {str(e)[:200]}")
        finally:
            _pipeline_running = False

    asyncio.create_task(_run())
    return {"status": "started"}


@app.get("/api/telegram/pair")
async def telegram_pair():
    code = _get_telegram().generate_pairing_code()
    return {"code": code, "instruction": f"Send /pair {code} to your SODA bot on Telegram"}

@app.get("/api/telegram/status")
async def telegram_status():
    return {
        "configured": _get_telegram().is_configured(),
        "has_token": bool(_get_telegram()._token),
        "chat_id": _get_telegram()._chat_id,
    }

def _build_setup_bat(project_id: str, cwd: Path, install_cmd: str, run_cmd: str) -> str:  # noqa: C901
    """
    Generate a robust Windows .bat launcher.
    - All paths use %~dp0 so they work regardless of where the shell starts.
    - Paths with spaces are quoted.
    - Errors are captured to _soda_errors.log.
    - Supports: Python, Node/npm, .NET, Go, Rust/Cargo, C++/CMake, HTML.
    """
    c_i = (install_cmd or "").lower()
    c_r = run_cmd.lower()
    log_file = "%~dp0_soda_errors.log"

    is_python = "pip" in c_i or any(x in c_r for x in ("python", "uvicorn", "flask", "gunicorn", "fastapi", "django", "manage.py"))
    is_node   = any(x in c_i for x in ("npm", "yarn", "pnpm")) or any(x in c_r for x in ("npm ", "yarn ", "node ", "npx "))
    is_dotnet = "dotnet" in c_i or "dotnet" in c_r
    is_go     = "go run" in c_r or "go build" in c_r or "go " in c_i
    is_rust   = "cargo " in c_r or "cargo " in c_i
    is_cmake  = "cmake" in c_r or "cmake" in c_i or (cwd / "CMakeLists.txt").exists()
    is_html   = (
        not any([is_python, is_node, is_dotnet, is_go, is_rust, is_cmake])
        and any(x in c_r for x in (".html", "abrir", "navegador", "browser", "open", "index"))
    )

    sep = "echo ================================================"
    # %~dp0 = directory of this .bat file (always correct even if shell cwd differs)
    header = [
        "@echo off",
        "chcp 65001 >nul 2>&1",
        f"title SODA — {project_id}",
        sep,
        f"echo   SODA — {project_id}",
        sep,
        "echo.",
        f"cd /d \"%~dp0\"",
        f"echo Directorio de trabajo: %~dp0",
        "echo.",
    ]

    def err_check(step: str) -> str:
        return (
            f"if errorlevel 1 ("
            f"echo ERROR en {step} >> \"{log_file}\" & "
            f"echo [%DATE% %TIME%] ERROR en {step} >> \"{log_file}\" & "
            f"echo ERROR en {step} - ver {log_file} para detalles & "
            f"pause & exit /b 1)"
        )

    if is_html:
        import re as _re
        html_match = _re.search(r'[\w./\\-]+\.html', run_cmd, _re.IGNORECASE)
        html_file  = html_match.group(0) if html_match else "index.html"
        abs_html   = str(cwd / html_file)
        lines = header + [
            f'echo Abriendo {html_file} en el navegador...',
            "echo.",
            f'start "" "{abs_html}"',
            "echo.",
            "echo Listo. Cerra esta ventana cuando termines.",
            "pause",
        ]

    elif is_python:
        req_candidates = [
            "requirements.txt", "requirements/base.txt",
            "requirements/main.txt", "requirements/prod.txt",
        ]
        req_file = next((f for f in req_candidates if (cwd / f).exists()), None)
        has_pkg  = (cwd / "pyproject.toml").exists() or (cwd / "setup.py").exists()

        # Redirect executables to venv — handle both "cmd arg" and "python -m cmd" patterns
        venv_run = run_cmd
        for exe in ("uvicorn", "flask", "gunicorn", "celery", "hypercorn", "daphne"):
            venv_run = venv_run.replace(f"{exe} ", f'"%~dp0venv\\Scripts\\{exe}" ')
        venv_run = (venv_run
                    .replace("python3 ", '"%~dp0venv\\Scripts\\python" ')
                    .replace("python ",  '"%~dp0venv\\Scripts\\python" '))

        if req_file:
            pip_cmd = f'call "%~dp0venv\\Scripts\\pip" install -r "{req_file}" --quiet'
        elif has_pkg:
            pip_cmd = f'call "%~dp0venv\\Scripts\\pip" install -e . --quiet'
        else:
            pip_cmd = None

        total = 3 if pip_cmd else 2
        lines = header + [
            f"if not exist \"%~dp0venv\" (",
            f"    echo [1/{total}] Creando entorno virtual Python...",
            # Try py launcher first (Windows standard), then python3, then python
            '    py -m venv "%~dp0venv" 2>nul || python3 -m venv "%~dp0venv" 2>nul || python -m venv "%~dp0venv"',
            f"    {err_check('crear venv')}",
            f") else (",
            f"    echo [1/{total}] Entorno virtual ya existe.",
            f")",
        ]
        if pip_cmd:
            lines += [
                f"echo [2/{total}] Instalando dependencias...",
                pip_cmd,
                err_check("instalar dependencias"),
                "echo Instalacion completa.",
                "echo.",
                f"echo [3/{total}] Iniciando aplicacion...",
                "echo.",
                venv_run,
            ]
        else:
            lines += [
                f"echo [2/{total}] Sin dependencias extra.",
                f"echo [{total}/{total}] Iniciando aplicacion...",
                "echo.",
                venv_run,
            ]

    elif is_node:
        pkg_mgr = "yarn" if "yarn" in c_i else ("pnpm" if "pnpm" in c_i else "npm")
        install  = install_cmd or f"{pkg_mgr} install"
        lines = header + [
            f"echo [1/2] Instalando dependencias ({pkg_mgr})...",
            install,
            err_check(f"{pkg_mgr} install"),
            "echo.",
            "echo [2/2] Iniciando aplicacion...",
            "echo.",
            run_cmd,
        ]

    elif is_dotnet:
        lines = header + [
            "echo [1/2] Restaurando paquetes NuGet...",
            "dotnet restore",
            err_check("dotnet restore"),
            "echo.",
            "echo [2/2] Iniciando aplicacion...",
            "echo.",
            run_cmd,
        ]

    elif is_cmake:
        build_dir = str(cwd / "build")
        lines = header + [
            f"if not exist \"{build_dir}\" mkdir \"{build_dir}\"",
            f"echo [1/3] Configurando con CMake...",
            f'cmake -S "%~dp0" -B "{build_dir}" -G "MinGW Makefiles"',
            err_check("cmake configure"),
            f"echo [2/3] Compilando...",
            f'cmake --build "{build_dir}" --config Release',
            err_check("cmake build"),
            "echo.",
            "echo [3/3] Ejecutando...",
            "echo.",
            run_cmd,
        ]

    elif is_rust:
        lines = header + [
            "echo [1/2] Compilando con Cargo...",
            "cargo build --release",
            err_check("cargo build"),
            "echo.",
            "echo [2/2] Ejecutando...",
            "echo.",
            run_cmd if "cargo run" in c_r else f"cargo run",
        ]

    elif is_go:
        lines = header + [
            "echo [1/2] Descargando modulos Go...",
            "go mod tidy",
            err_check("go mod tidy"),
            "echo.",
            "echo [2/2] Ejecutando...",
            "echo.",
            run_cmd,
        ]

    else:
        lines = header[:]
        if install_cmd:
            lines += [
                "echo [1/2] Instalando dependencias...",
                install_cmd,
                err_check("instalacion"),
                "echo.",
                "echo [2/2] Iniciando aplicacion...",
                "echo.",
                run_cmd,
            ]
        else:
            lines += ["echo Iniciando aplicacion...", "echo.", run_cmd]

    # Always append error-handling footer
    lines += [
        "echo.",
        "if errorlevel 1 (",
        f"    echo El proceso termino con error. Ver: {log_file}",
        "    pause",
        ")",
    ]
    return "\r\n".join(lines) + "\r\n"


def _find_manifest_dir(source_dir: Path, cmd: str) -> Path:
    """Return the best working directory by scanning for project manifest files."""
    c = cmd.lower()

    def first(patterns):
        for pat in patterns:
            hits = [p for p in source_dir.rglob(pat) if "node_modules" not in str(p)]
            if hits:
                return hits[0].parent
        return None

    if "dotnet" in c:
        found = first(["*.csproj", "*.fsproj", "*.vbproj"])
        if found:
            return found
    if any(x in c for x in ("npm ", "yarn ", "npx ", "node ")):
        found = first(["package.json"])
        if found:
            return found
    if "mvn" in c:
        found = first(["pom.xml"])
        if found:
            return found
    if "gradle" in c:
        found = first(["build.gradle", "build.gradle.kts"])
        if found:
            return found
    if "composer" in c:
        found = first(["composer.json"])
        if found:
            return found
    if any(x in c for x in ("go run", "go build")):
        found = first(["go.mod"])
        if found:
            return found
    if "cargo" in c:
        found = first(["Cargo.toml"])
        if found:
            return found
    return source_dir


@app.get("/api/project/{project_id}")
async def get_project_metadata(project_id: str):
    """Return project metadata including blueprint (run_command, install_command, etc.)."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "Proyecto no encontrado"}, status_code=404)
    try:
        meta = _project_manager.load_metadata(project_id)
        return {"project_id": project_id, "metadata": meta}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/project/{project_id}/status")
async def get_project_contract_status(project_id: str):
    """Return contract-level status for a project (pending/completed counts, source files)."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "Proyecto no encontrado"}, status_code=404)
    try:
        from kernel.orchestrator import SodaOrchestrator
        orch = _get_orchestrator()
        result = orch.get_project_status(project_id)
        if "error" in result:
            return JSONResponse({"status": "error", "message": result["error"]}, status_code=404)
        return result
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/projects/{project_id}/retry-boot")
async def retry_boot_project(project_id: str):
    """
    Reintenta el BootAgent en un proyecto con estado BOOT_FAILED o FAILED.
    Lanza el retry en background y retorna inmediatamente.
    """
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "Proyecto no encontrado"}, status_code=404)
    try:
        from kernel.orchestrator import SodaOrchestrator
        orch = _get_orchestrator()
        asyncio.create_task(orch.retry_boot(project_id))
        return {"status": "ok", "message": f"Retry de boot iniciado para {project_id}."}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/skills/add")
async def add_community_skill(request: Request):
    """
    Convert a skills.sh SKILL.md URL (or raw markdown text) to SODA format.

    Body: {"url": "https://...", "target_lang": "python", "force": false}
      OR: {"text": "# SKILL: ...", "target_lang": "python"}
    """
    body = await request.json()
    url = (body.get("url") or "").strip()
    text = (body.get("text") or "").strip()
    target_lang = (body.get("target_lang") or "python").strip()
    force = bool(body.get("force", False))

    if not url and not text:
        return JSONResponse(
            {"status": "error", "message": "Se requiere 'url' o 'text'"},
            status_code=400,
        )

    try:
        from kernel.capabilities.skill_sh_adapter import SkillShAdapter, validate_community_skill
        adapter = SkillShAdapter()

        if url:
            skill_dir = await adapter.convert_from_url(url, target_lang=target_lang, force=force)
        else:
            skill_dir = await asyncio.to_thread(
                adapter.convert_from_text, text, target_lang, "", force
            )

        if skill_dir is None:
            return JSONResponse(
                {"status": "error", "message": "No se pudo parsear el SKILL.md (título vacío o descarga fallida)"},
                status_code=422,
            )

        report = validate_community_skill(skill_dir)
        return {
            "status": "ok",
            "skill_name": skill_dir.name,
            "skill_path": str(skill_dir),
            "quality": {
                "has_examples": report.has_examples,
                "has_keywords": report.has_keywords,
                "issues": report.issues,
                "is_acceptable": report.is_acceptable,
            },
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/projects/{project_id}/runtime_health")
async def get_project_runtime_health(project_id: str):
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    from kernel.orchestrator import SodaOrchestrator
    orch = _get_orchestrator()
    project = orch._project_from_disk(project_id)
    health_data = await orch._get_runtime_health(project)
    
    if health_data["status"] == "ok":
        return {
            "status": "ok", 
            "project_id": project_id, 
            "runtime_health": health_data["health"], 
            "runtime_smoke": health_data["smoke"]
        }
    else:
        return JSONResponse({
            "status": "error", 
            "message": health_data["reason"]
        }, status_code=500)


@app.get("/api/projects/{project_id}/files")
async def get_project_files(project_id: str):
    """Return all source files for a project as {filename: content} dict."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    source_dir = _project_manager.source_dir(project_id)
    if not source_dir.exists():
        return {"files": {}}
    text_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
                 ".yaml", ".yml", ".md", ".txt", ".sh", ".env", ".toml", ".cfg", ".ini"}
    files: dict[str, str] = {}
    for p in sorted(source_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in text_exts and "node_modules" not in str(p):
            rel = p.relative_to(source_dir).as_posix()
            try:
                files[rel] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return {"files": files}


@app.get("/api/projects/{project_id}/goal_tree")
async def get_project_goal_tree(project_id: str):
    """Return the project's goal tree JSON for UI rendering."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    project_dir = _project_manager.project_dir(project_id)
    
    # Try V2 Tree first
    v2_path = project_dir / "soda_v2_tree.json"
    if v2_path.exists():
        try:
            import json as _json
            data = _json.loads(v2_path.read_text(encoding="utf-8"))
            nodes = []
            for cid, contract in data.items():
                status_map = {
                    "PENDING_DECOMPOSITION": "planned",
                    "PENDING_EXECUTION": "planned",
                    "DECOMPOSED": "in_progress",
                    "COMPLETED": "implemented"
                }
                nodes.append({
                    "id": cid,
                    "description": contract.get("title", cid) + ": " + contract.get("description", ""),
                    "status": status_map.get(contract.get("status", "PENDING_EXECUTION"), "planned"),
                    "type": "atomic" if contract.get("is_atomic") else "module"
                })
            return {"root_id": "ROOT-000", "nodes": nodes}
        except Exception:
            pass

    # Fallback to V1
    gt_path = project_dir / "goal_tree.json"
    if not gt_path.exists():
        return {"nodes": [], "root_id": None}
    try:
        import json as _json
        data = _json.loads(gt_path.read_text(encoding="utf-8"))
        nodes = list(data.get("nodes", {}).values()) if isinstance(data.get("nodes"), dict) else data.get("nodes", [])
        return {"root_id": data.get("root_id"), "nodes": nodes}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/projects/{project_id}/runtime_smoke")
async def get_project_runtime_smoke(project_id: str):
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    project_dir = _project_manager.project_dir(project_id)
    meta = _project_manager.load_metadata(project_id)
    blueprint = meta.get("blueprint", {}) or {}
    run_command = (blueprint.get("comando_ejecucion") or "").strip()
    install_command = (blueprint.get("comando_instalacion") or "").strip()

    smoke = (await asyncio.to_thread(_project_runner.smoke_check, project_dir, run_command, install_command)).to_dict()
    return {"status": "ok", "project_id": project_id, "runtime_smoke": smoke}


def _ensure_csproj(cwd: Path, project_id: str) -> None:
    """Generate a minimal .csproj if none exists (dotnet projects only)."""
    if list(cwd.rglob("*.csproj")):
        return  # already exists somewhere
    cs_files = list(cwd.rglob("*.cs"))
    if not cs_files:
        return

    # Detect WinForms by presence of Designer files or Forms directory
    is_winforms = (
        any("designer" in f.name.lower() for f in cs_files)
        or any("form" in f.name.lower() for f in cs_files)
        or (cwd / "Forms").exists()
    )
    if is_winforms:
        content = (
            '<Project Sdk="Microsoft.NET.Sdk">\n'
            '  <PropertyGroup>\n'
            f'    <AssemblyName>{project_id}</AssemblyName>\n'
            '    <OutputType>WinExe</OutputType>\n'
            '    <TargetFramework>net8.0-windows</TargetFramework>\n'
            '    <UseWindowsForms>true</UseWindowsForms>\n'
            '    <Nullable>enable</Nullable>\n'
            '    <ImplicitUsings>enable</ImplicitUsings>\n'
            '  </PropertyGroup>\n'
            '</Project>\n'
        )
    else:
        content = (
            '<Project Sdk="Microsoft.NET.Sdk">\n'
            '  <PropertyGroup>\n'
            f'    <AssemblyName>{project_id}</AssemblyName>\n'
            '    <OutputType>Exe</OutputType>\n'
            '    <TargetFramework>net8.0</TargetFramework>\n'
            '    <Nullable>enable</Nullable>\n'
            '    <ImplicitUsings>enable</ImplicitUsings>\n'
            '  </PropertyGroup>\n'
            '</Project>\n'
        )
    (cwd / f"{project_id}.csproj").write_text(content, encoding="utf-8")


@app.post("/api/launch")
async def launch_project(request: Request):
    """Install dependencies and run the project in a new terminal window."""
    import subprocess
    from kernel.execution.execution_error_log import ExecutionErrorLog
    body = await request.json()
    project_id      = (body.get("project_id")      or "").strip()
    run_command     = (body.get("run_command")     or "").strip()
    install_command = (body.get("install_command") or "").strip()
    wait_for_smoke  = bool(body.get("wait_for_smoke", True))

    if not project_id:
        return JSONResponse({"status": "error", "message": "project_id requerido"}, status_code=400)

    # Look up run_command from project metadata if not provided in request
    if not run_command:
        try:
            meta = _project_manager.load_metadata(project_id)
            bp = meta.get("blueprint", {})
            run_command = bp.get("comando_ejecucion", "")
            if not install_command:
                install_command = bp.get("comando_instalacion", "")
        except Exception:
            pass
    if not run_command:
        return JSONResponse({"status": "error", "message": "No hay run_command para este proyecto."}, status_code=400)

    source_dir = _project_manager.source_dir(project_id)
    if not source_dir.exists():
        return JSONResponse({"status": "error", "message": "Carpeta del proyecto no encontrada"}, status_code=404)

    if not install_command:
        try:
            meta = _project_manager.load_metadata(project_id)
            install_command = meta.get("blueprint", {}).get("comando_instalacion", "")
        except Exception:
            pass

    cwd, cmd = _project_runner.resolve_working_dir(source_dir, run_command, install_command)
    runtime_health = (await asyncio.to_thread(_project_runner.preflight, _project_manager.project_dir(project_id), cmd, install_command)).to_dict()

    if "dotnet" in cmd.lower():
        _ensure_csproj(cwd, project_id)

    try:
        bat_content = _build_setup_bat(project_id, cwd, install_command, cmd)
        bat = cwd / "_soda_run.bat"
        try:
            bat.write_text(bat_content, encoding="utf-8")
        except PermissionError as pe:
            ExecutionErrorLog.record(project_id, "launch", f"Sin permisos para escribir BAT: {pe}", "PermissionError", {"path": str(bat)})
            return JSONResponse({"status": "error", "message": f"Sin permisos en {cwd} — intentá ejecutar SODA como administrador."}, status_code=403)

        proc = subprocess.Popen(
            ["cmd.exe", "/c", "start", "cmd.exe", "/k", str(bat)],
            cwd=str(cwd),
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        # Store the launcher pid (not the inner cmd, but tracks the spawn)
        ExecutionErrorLog.mark_resolved(project_id)

        if wait_for_smoke:
            runtime_smoke = (
                await _project_runner.smoke_check_with_retry(
                    _project_manager.project_dir(project_id),
                    cmd, install_command, attempts=5, delay_s=2.0,
                )
            ).to_dict()
        else:
            runtime_smoke = (await asyncio.to_thread(
                _project_runner.smoke_check,
                _project_manager.project_dir(project_id),
                cmd, install_command,
            )).to_dict()

        url = _project_runner.infer_runtime_url(cmd, _project_runner.detect_stack(cmd, install_command))
        return {
            "status": "launched",
            "pid": proc.pid,
            "url": url,
            "cwd": str(cwd),
            "command": cmd,
            "bat_path": str(bat),
            "launcher_pid": proc.pid,
            "runtime_health": runtime_health,
            "runtime_smoke": runtime_smoke,
        }
    except PermissionError as e:
        msg = f"Sin permisos de Windows: {e}"
        ExecutionErrorLog.record(project_id, "launch", msg, "PermissionError", {"cwd": str(cwd), "cmd": cmd})
        return JSONResponse({"status": "error", "message": msg + " — intentá ejecutar SODA como administrador."}, status_code=403)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        ExecutionErrorLog.record(project_id, "launch", str(e), type(e).__name__, {"cwd": str(cwd), "cmd": cmd, "tb": tb[:600]})
        print(f"  [LAUNCH ERROR] {project_id}: {e}\n{tb}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


_URL_PATTERNS = [
    r"https?://[^\s]+",
    r"running on (https?://[^\s]+)",
    r"localhost:(\d+)",
    r"0\.0\.0\.0:(\d+)",
    r"127\.0\.0\.1:(\d+)",
]
_URL_RE = __import__("re").compile(
    r"(?:running on |listening on |started on |serving at |server at )??(https?://[\w\.\-]+:\d+|https?://localhost(?::\d+)?)",
    __import__("re").IGNORECASE,
)
_PORT_RE = __import__("re").compile(
    r"(?:0\.0\.0\.0|127\.0\.0\.1|localhost):(\d+)",
    __import__("re").IGNORECASE,
)


def _detect_url_in_line(line: str) -> str | None:
    """Return the first server URL found in an output line, or None."""
    m = _URL_RE.search(line)
    if m:
        return m.group(1)
    m2 = _PORT_RE.search(line)
    if m2:
        return f"http://localhost:{m2.group(1)}"
    return None


async def _stream_process(project_id: str, run_cmd: str, cwd: str, workspace: str = "") -> None:
    """Run a project process and broadcast stdout/stderr line-by-line via WebSocket.

    Resolves executables from .soda_venv/Scripts before system PATH so that
    project-specific packages (uvicorn, fastapi, etc.) are always used.

    Broadcasts:
    - APP_OUTPUT  — each line of stdout/stderr
    - APP_RUNNING — when a server URL is detected in the output
    - APP_EXITED  — when the process ends

    Registers the process in ProjectRunner's registry so /api/processes can
    list it and /api/projects/{id}/kill can stop it. Also kills any previous
    instance for the same project_id before starting the new one.
    """
    from kernel.execution.project_runner import ProjectRunner, ProcessHandle
    from datetime import datetime as _dt

    # Kill any existing process for this project before starting a new one.
    # This prevents duplicate node/python workers when retry_boot or the
    # pipeline runs multiple times without an explicit stop.
    ProjectRunner.kill_process(project_id)

    _url_announced = False
    proc = None

    # Build env with venv Scripts prepended to PATH
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if workspace:
        venv_scripts = Path(workspace) / ".soda_venv" / "Scripts"
        if not venv_scripts.exists():
            # Venv missing (project from a previous session) — create + install now
            try:
                from kernel.sandbox.dynamic_env import DynamicEnvironment
                _env = DynamicEnvironment(project_id, Path(workspace), None)
                await _env.ensure_venv()
                await _env.install_requirements()
            except Exception:
                pass
        if venv_scripts.exists():
            env["PATH"] = str(venv_scripts) + os.pathsep + env.get("PATH", "")
            env["VIRTUAL_ENV"] = str(Path(workspace) / ".soda_venv")

    # Use shell mode on Windows so operators like && and cd work correctly.
    # On Linux/Mac use shlex.split + exec (avoids an extra shell process).
    import shlex as _shlex
    try:
        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_shell(
                run_cmd.strip(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
                env=env,
            )
        else:
            _cmd = _shlex.split(run_cmd.strip())
            proc = await asyncio.create_subprocess_exec(
                *_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
                env=env,
            )
        # Register in the global process registry so the UI can list/kill it.
        _log_path = str(Path(workspace) / "_soda_launch.log") if workspace else ""
        ProjectRunner.register_process(ProcessHandle(
            project_id=project_id,
            pid=proc.pid or 0,
            command=run_cmd.strip()[:120],
            cwd=cwd,
            started_at=_dt.utcnow().isoformat(),
            log_path=_log_path,
            proc=proc,
        ))

        await manager.broadcast({
            "event_type": "APP_OUTPUT",
            "message": f"[PROCESO] Iniciando: {run_cmd.strip()[:80]}",
            "data": {"project_id": project_id, "stream": "info"},
        })

        # After 8s without a URL, announce screenshot mode if the process is still alive
        async def _announce_screenshot_mode():
            await asyncio.sleep(8)
            if not _url_announced and proc.returncode is None:
                await manager.broadcast({
                    "event_type": "APP_RUNNING",
                    "message": "Aplicación corriendo (captura de pantalla activa)",
                    "data": {"project_id": project_id, "url": None, "mode": "screenshot"},
                })
        asyncio.create_task(_announce_screenshot_mode())

        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            await manager.broadcast({
                "event_type": "APP_OUTPUT",
                "message": line,
                "data": {"project_id": project_id},
            })
            if not _url_announced:
                url = _detect_url_in_line(line)
                if url:
                    _url_announced = True
                    await manager.broadcast({
                        "event_type": "APP_RUNNING",
                        "message": f"Aplicación corriendo en {url}",
                        "data": {"project_id": project_id, "url": url, "mode": "web"},
                    })

        await proc.wait()
        ProjectRunner.kill_process(project_id)   # deregister
        await manager.broadcast({
            "event_type": "APP_EXITED",
            "message": f"[PROCESO] Terminó (código {proc.returncode})",
            "data": {"project_id": project_id, "return_code": proc.returncode},
        })
    except Exception as exc:
        await manager.broadcast({
            "event_type": "APP_OUTPUT",
            "message": f"[ERROR] {exc}",
            "data": {"project_id": project_id, "stream": "error"},
        })
    finally:
        # Always deregister + kill on exit so no orphan processes remain.
        ProjectRunner.kill_process(project_id)
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass


@app.get("/api/processes")
async def list_processes():
    """Return all tracked running processes."""
    from kernel.execution.project_runner import ProjectRunner
    return {"processes": ProjectRunner.list_processes()}


@app.get("/api/projects/{project_id}/screenshot")
async def get_project_screenshot(project_id: str):
    """Capture the current screen and return it as JPEG (for non-web desktop apps)."""
    import io
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=72)
        buf.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            buf, media_type="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache", "Pragma": "no-cache"},
        )
    except ImportError:
        return JSONResponse({"error": "Pillow no instalado — pip install Pillow"}, status_code=501)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/projects/{project_id}/n8n_workflow")
async def download_n8n_workflow(project_id: str):
    """Download the n8n_workflow.json generated for this project."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"error": "project not found"}, status_code=404)
    workflow_path = _project_manager.project_dir(project_id) / "n8n_workflow.json"
    if not workflow_path.exists():
        return JSONResponse({"error": "n8n workflow not generated yet"}, status_code=404)
    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(workflow_path),
        media_type="application/json",
        filename="n8n_workflow.json",
    )


@app.get("/api/projects/{project_id}/graph")
async def get_project_graph(project_id: str, mode: str = "files"):
    """Return a Cytoscape-ready graph of the project's module or file dependencies."""
    workspace = _project_manager.project_dir(project_id)
    from kernel.graph.import_parser import parse_project_graph, module_graph_from_architecture

    if mode == "modules":
        arch_path = workspace / "architecture.json"
        if arch_path.exists():
            import json as _json
            arch = _json.loads(arch_path.read_text(encoding="utf-8"))
            graph = module_graph_from_architecture(arch)
            return {"nodes": graph.nodes, "edges": graph.edges, "mode": "modules"}
        return {"nodes": [], "edges": [], "mode": "modules"}

    # File-level graph parsed from source imports
    source_dir = workspace / "source"
    if not source_dir.exists():
        return {"nodes": [], "edges": [], "mode": "files"}
    graph = parse_project_graph(source_dir)
    return {"nodes": graph.nodes, "edges": graph.edges, "mode": "files"}


@app.put("/api/projects/{project_id}/files")
async def save_project_file(project_id: str, request: Request):
    """Save a file in the project's source directory."""
    body = await request.json()
    filepath: str = (body.get("filepath") or "").strip().lstrip("/\\")
    content: str = body.get("content") or ""
    if not filepath:
        return JSONResponse({"status": "error", "message": "filepath required"}, status_code=400)
    source_dir = _project_manager.project_dir(project_id) / "source"
    if not source_dir.exists():
        source_dir = _project_manager.project_dir(project_id)
    target = (source_dir / filepath).resolve()
    # Safety: must stay inside project dir
    try:
        target.relative_to(_project_manager.project_dir(project_id).resolve())
    except ValueError:
        return JSONResponse({"status": "error", "message": "path traversal denied"}, status_code=403)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"status": "saved", "filepath": filepath}


@app.post("/api/kill/{project_id}")
async def kill_process(project_id: str):
    """Kill a running project process."""
    from kernel.execution.project_runner import ProjectRunner
    from kernel.execution.execution_error_log import ExecutionErrorLog
    killed = ProjectRunner.kill_process(project_id)
    if killed:
        ExecutionErrorLog.record(project_id, "launch", "Proceso terminado por el usuario.", "UserKill")
    return {"status": "ok" if killed else "not_found", "killed": killed}


@app.get("/api/execution_errors")
async def get_execution_errors(limit: int = 30):
    """Return recent execution errors across all projects."""
    from kernel.execution.execution_error_log import ExecutionErrorLog
    return {"errors": ExecutionErrorLog.get_recent_errors(limit=limit)}


@app.get("/api/execution_errors/{project_id}")
async def get_project_execution_errors(project_id: str, limit: int = 20):
    """Return execution errors for a specific project."""
    from kernel.execution.execution_error_log import ExecutionErrorLog
    return {"project_id": project_id, "errors": ExecutionErrorLog.get_project_errors(project_id, limit=limit)}


@app.post("/api/autofix")
async def autofix_project(request: Request):
    """Run 3-attempt auto-fix ladder for a project, falling back to Claude CLI."""
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    if not project_id:
        return JSONResponse({"status": "error", "message": "project_id requerido"}, status_code=400)

    try:
        meta = _project_manager.load_metadata(project_id)
    except Exception:
        meta = {}
    blueprint = meta.get("blueprint", {})
    run_command     = blueprint.get("comando_ejecucion", "")
    install_command = blueprint.get("comando_instalacion", "")
    project_workspace = _project_manager.project_dir(project_id)

    if not run_command:
        return JSONResponse({"status": "error", "message": "No hay run_command para este proyecto."}, status_code=400)

    async def _run_autofix():
        from kernel.execution.auto_fixer import AutoFixer

        def _notify(msg, ev_type, data):
            import asyncio as _aio
            payload = {"event_type": ev_type, "message": msg, "data": data or {}}
            try:
                loop = _aio.get_running_loop()
                loop.create_task(manager.broadcast(payload))
            except Exception:
                pass

        fixer = AutoFixer(notify_fn=_notify)
        result = await fixer.fix_and_run(project_id, project_workspace, run_command, install_command)
        final_ev = "LOG" if result["success"] else "HEALTH_WARN"
        status_msg = (
            f"Auto-Fix {'exitoso' if result['success'] else 'falló'} "
            f"(intento {result['attempt']}) — {result.get('url', '')}"
        )
        await manager.broadcast({"event_type": final_ev, "message": status_msg, "data": result})

    asyncio.create_task(_run_autofix())
    return {"status": "started", "project_id": project_id}


@app.get("/api/execution_precedents/{stack}")
async def get_precedents(stack: str):
    """Return execution precedents for a given stack."""
    from kernel.execution.execution_precedents import ExecutionPrecedents
    return {"stack": stack, "precedents": ExecutionPrecedents.get_for_stack(stack)}


# ── Embedded Terminal ──────────────────────────────────────────────────────────

@app.websocket("/ws/terminal/{session_id}")
async def terminal_ws(ws: WebSocket, session_id: str, project_id: str = "", command: str = ""):
    """
    WebSocket endpoint for the embedded terminal.
    Query params: project_id (optional), command (optional — defaults to cmd.exe)
    Client sends JSON: {type:"input"|"resize"|"kill", data:str, cols:int, rows:int}
    Server sends: raw bytes (terminal output) or JSON {type:"exit", code:N}
    """
    from kernel.execution.terminal_session import TerminalSession, TerminalSessionManager

    await ws.accept()

    # Resolve working directory
    cwd = str(Path(__file__).resolve().parent.parent)
    if project_id:
        try:
            src = _project_manager.source_dir(project_id)
            if src.exists():
                cwd = str(src)
            else:
                proj_dir = _project_manager.project_dir(project_id)
                if proj_dir.exists():
                    cwd = str(proj_dir)
        except Exception:
            pass

    # Default command: Windows CMD shell
    if not command:
        command = "cmd.exe"

    session = TerminalSessionManager.create(session_id, project_id or "soda", command, cwd)

    async def _send_output(data: bytes):
        try:
            await ws.send_bytes(data)
        except Exception:
            pass

    def _on_output(chunk: bytes):
        asyncio.create_task(_send_output(chunk))

    def _on_exit(code: int):
        msg = f"\r\n[SODA Terminal] Proceso terminado (código {code})\r\n".encode()
        asyncio.create_task(_send_output(msg))
        try:
            import json as _json
            asyncio.create_task(ws.send_text(_json.dumps({"type": "exit", "code": code})))
        except Exception:
            pass

    # Launch subprocess
    await TerminalSessionManager.launch(session, _on_output, _on_exit)
    await _send_output(f"[SODA Terminal] {command}\r\nCWD: {cwd}\r\n\r\n".encode())

    try:
        while True:
            raw = await ws.receive()
            if "bytes" in raw:
                # Raw keypresses from xterm.js
                await TerminalSessionManager.send_input(session, raw["bytes"].decode("utf-8", errors="replace"))
            elif "text" in raw:
                try:
                    msg = json.loads(raw["text"])
                    mtype = msg.get("type", "")
                    if mtype == "input":
                        await TerminalSessionManager.send_input(session, msg.get("data", ""))
                    elif mtype == "kill":
                        session.kill()
                        break
                    elif mtype == "command":
                        # Run a new command in the session's shell
                        await TerminalSessionManager.send_input(session, msg.get("data", "") + "\n")
                except Exception:
                    pass
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        session.kill()
        TerminalSessionManager.kill(session_id)


@app.get("/api/terminal/sessions")
async def list_terminal_sessions():
    """Return active terminal sessions."""
    from kernel.execution.terminal_session import TerminalSessionManager
    return {"sessions": TerminalSessionManager.list_sessions()}


@app.delete("/api/terminal/{session_id}")
async def kill_terminal_session(session_id: str):
    """Kill a terminal session."""
    from kernel.execution.terminal_session import TerminalSessionManager
    ok = TerminalSessionManager.kill(session_id)
    return {"killed": ok}


@app.post("/api/terminal/diagnose")
async def diagnose_terminal_output(request: Request):
    """
    Send terminal output to Claude/Gemini for AI diagnosis.
    Body: {project_id, output, session_id (optional)}
    Returns: {diagnosis, suggested_commands, root_cause}
    """
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    output = (body.get("output") or "").strip()
    session_id = (body.get("session_id") or "").strip()

    if not output:
        # Try to get from session buffer
        if session_id:
            from kernel.execution.terminal_session import TerminalSessionManager
            s = TerminalSessionManager.get(session_id)
            if s:
                output = s.get_output()

    if not output:
        return JSONResponse({"status": "error", "message": "No hay output para diagnosticar"}, status_code=400)

    # Get project context
    project_context = ""
    run_command = ""
    stack = ""
    if project_id:
        try:
            meta = _project_manager.load_metadata(project_id)
            bp = meta.get("blueprint", {})
            run_command = bp.get("comando_ejecucion", "")
            stack = bp.get("stack", bp.get("lenguaje", ""))
            project_context = (
                f"Proyecto: {project_id}\n"
                f"Stack: {stack}\n"
                f"Comando de ejecución: {run_command}\n"
                f"Descripción: {bp.get('descripcion', '')[:200]}\n"
            )
        except Exception:
            pass

    # Build AI prompt
    prompt = f"""Analizá la siguiente salida de terminal de un proyecto de software que falló al ejecutarse.

{project_context}

SALIDA DE TERMINAL (últimas líneas):
```
{output[-4000:]}
```

Respondé en JSON con este formato exacto:
{{
  "root_cause": "explicación concisa del problema raíz (1-2 oraciones)",
  "diagnosis": "explicación detallada del problema y por qué ocurre",
  "suggested_commands": [
    {{"label": "descripción de qué hace", "command": "comando exacto a ejecutar"}},
    ...
  ],
  "files_to_check": ["lista de archivos relevantes a revisar"],
  "severity": "critical|warning|info"
}}

Solo respondé con el JSON, sin texto adicional."""

    try:
        from kernel.drivers.gemini_driver import GeminiDriver
        driver = GeminiDriver()
        raw = await driver.prompt(
            "Sos un experto en diagnóstico de errores de ejecución de software en Windows. "
            "Analizás outputs de terminal y das soluciones concretas con comandos ejecutables.",
            prompt,
        )
        # Extract JSON from response
        import re as _re
        json_match = _re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"root_cause": raw[:300], "diagnosis": raw, "suggested_commands": [], "severity": "warning"}
    except Exception as e:
        # Fallback to Gemini
        try:
            from kernel.drivers.gemini_driver import GeminiDriver
            gemini = GeminiDriver()
            raw = await gemini.prompt(
                "Experto en diagnóstico de errores de terminal.",
                prompt,
            )
            import re as _re
            json_match = _re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"root_cause": raw[:300], "diagnosis": raw, "suggested_commands": [], "severity": "warning"}
        except Exception as e2:
            return JSONResponse({"status": "error", "message": f"AI no disponible: {e2}"}, status_code=503)

    return {"status": "ok", "project_id": project_id, "result": result}


# ── Open Existing Project ─────────────────────────────────────────────────────

@app.get("/api/open_project/browse")
async def browse_folder():
    """Open a native Windows folder/file dialog and return the selected path."""
    import threading
    result: dict = {}
    event = asyncio.Event()

    def _dialog():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root_tk = tk.Tk()
            root_tk.withdraw()
            root_tk.attributes('-topmost', True)
            path = filedialog.askdirectory(title="Seleccioná la carpeta del proyecto")
            if not path:
                # Fallback: try file picker
                path = filedialog.askopenfilename(
                    title="O seleccioná un archivo",
                    filetypes=[
                        ("Código fuente", "*.py *.js *.ts *.go *.rs *.java *.cs *.cpp *.c *.rb *.php"),
                        ("Todos los archivos", "*.*"),
                    ],
                )
            root_tk.destroy()
            result["path"] = path or ""
        except Exception as e:
            result["path"] = ""
            result["error"] = str(e)
        asyncio.get_event_loop().call_soon_threadsafe(event.set)

    threading.Thread(target=_dialog, daemon=True).start()
    await event.wait()
    return {"path": result.get("path", ""), "error": result.get("error", "")}


@app.post("/api/open_project/analyze")
async def analyze_open_project(request: Request):
    """
    Analyze an existing project at a given path.
    Body: {path: str, context?: str}
    Returns structured analysis JSON.
    """
    body = await request.json()
    path_str = (body.get("path") or "").strip()
    extra_context = (body.get("context") or "").strip()

    if not path_str:
        return JSONResponse({"status": "error", "message": "path requerido"}, status_code=400)

    target = Path(path_str)
    if not target.exists():
        return JSONResponse({"status": "error", "message": f"Ruta no encontrada: {path_str}"}, status_code=404)

    # If a file was selected, use its parent directory
    if target.is_file():
        target = target.parent

    try:
        from kernel.intelligence.project_analyzer import analyze_project
        analysis = await analyze_project(target, extra_context=extra_context)
        return {"status": "ok", "path": str(target), "analysis": analysis}
    except Exception as e:
        import traceback
        return JSONResponse({"status": "error", "message": str(e), "traceback": traceback.format_exc()[:500]}, status_code=500)


@app.post("/api/open_project/run")
async def run_open_project(request: Request):
    """
    Start processing an existing project with the chosen action.
    Body: {path, action, intent, project_name, analysis, target_language?}
    """
    body = await request.json()
    path_str       = (body.get("path") or "").strip()
    action         = (body.get("action") or "full_pipeline").strip()
    intent         = (body.get("intent") or "").strip()
    project_name   = (body.get("project_name") or "").strip()
    analysis       = body.get("analysis") or {}
    answers        = body.get("answers") or {}
    target_lang    = (body.get("target_language") or "").strip()

    if not path_str or not project_name:
        return JSONResponse({"status": "error", "message": "path y project_name requeridos"}, status_code=400)
    if not Path(path_str).exists():
        return JSONResponse({"status": "error", "message": "Ruta no encontrada"}, status_code=404)

    global _pipeline_running
    if _pipeline_running:
        return {"status": "busy", "message": "Pipeline en ejecución"}

    async def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            from kernel.orchestrator import SodaOrchestrator
            orch = _get_orchestrator()
            await orch.open_and_process(
                source_path=path_str,
                action=action,
                intent=intent,
                project_name=project_name,
                analysis=analysis,
                answers=answers,
                target_language=target_lang,
            )
        except Exception as e:
            await manager.broadcast({"event_type": "PIPELINE_ERROR", "message": str(e), "data": {}})
        finally:
            _pipeline_running = False

    asyncio.create_task(_run())
    return {"status": "started", "action": action, "project_name": project_name}


@app.get("/api/open_project/migration_targets")
async def get_migration_targets():
    """Return list of supported target languages for migration."""
    from kernel.execution.language_migrator import SUPPORTED_TARGETS
    return {"targets": SUPPORTED_TARGETS}


@app.post("/api/ollama/start")
async def start_ollama():
    """Launch `ollama serve` in a new console window and wait up to 8s for it to respond."""
    import subprocess, httpx
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    # Check if already running
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{ollama_url}/api/tags", timeout=2.0)
        if r.status_code == 200:
            return {"status": "already_running"}
    except Exception:
        pass

    # Launch in a new console window
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "Ollama", "cmd.exe", "/k", "ollama serve"],
            shell=False,
        )
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    # Poll up to 8 seconds
    import asyncio
    for _ in range(8):
        await asyncio.sleep(1)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{ollama_url}/api/tags", timeout=1.5)
            if r.status_code == 200:
                return {"status": "started"}
        except Exception:
            pass

    return {"status": "timeout", "message": "Ollama se está iniciando, esperá unos segundos más."}


@app.get("/api/health")
async def get_health():
    return {"status": "ok"}


@app.get("/api/ai/status")
async def get_ai_status():
    """Returns per-AI status with model, availability, avg latency and session cost."""
    import httpx

    # Pull session-level stats from usage monitor (keyed by provider name)
    grouped = {r["provider"]: r for r in _usage_monitor.grouped_summary()}

    def _entry(provider: str, configured: bool, model: str) -> dict:
        g = grouped.get(provider, {})
        return {
            "ok":           configured,
            "model":        model,
            "avg_latency_s": round(g.get("avg_latency_ms", 0) / 1000, 2) if g else None,
            "total_cost_usd": g.get("cost_usd", 0.0),
        }

    result = {
        "claude": _entry("claude", bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
                         os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")),
        "gemini": _entry("gemini", bool(os.getenv("GEMINI_API_KEY", "").strip()),
                         os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")),
    }

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{ollama_url}/api/tags", timeout=2.0)
        qwen_ok = r.status_code == 200
    except Exception:
        qwen_ok = False
    result["qwen"] = _entry("ollama", qwen_ok, ollama_model)

    return result


@app.get("/api/ai/test/{provider}")
async def test_ai_provider(provider: str):
    """Quick round-trip test for a specific AI provider."""
    import httpx, time
    t0 = time.monotonic()
    provider = provider.lower()

    if provider == "claude":
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return {"ok": False, "error": "ANTHROPIC_API_KEY no configurada"}
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=key)
            msg = await client.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens=10, messages=[{"role":"user","content":"ping"}]
            )
            return {"ok": True, "model": msg.model, "latency_ms": int((time.monotonic()-t0)*1000)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:120]}

    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            return {"ok": False, "error": "GEMINI_API_KEY no configurada"}
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=key)
            model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=model, contents="ping"
            )
            return {"ok": True, "model": model, "latency_ms": int((time.monotonic()-t0)*1000)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:120]}

    if provider == "ollama":
        url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                r = await client.get(f"{url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "model": ", ".join(models[:3]) or "Ollama OK", "latency_ms": int((time.monotonic()-t0)*1000)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:120]}

    return {"ok": False, "error": f"Proveedor desconocido: {provider}"}


@app.get("/api/config")
async def get_soda_config():
    """Return SODA model/provider preferences from soda_config.json."""
    try:
        if SODA_CONFIG_PATH.exists():
            return json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

@app.get("/api/models/gemini")
async def get_gemini_model():
    """Returns the current selected FinOps profile and available profiles."""
    available_profiles = ["auto", "economy", "balanced", "premium"]
    try:
        if SODA_CONFIG_PATH.exists():
            cfg = json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
            current = cfg.get("finops_profile", "auto")
            if current not in available_profiles:
                current = "auto"
            return {"current": current, "available": available_profiles}
    except Exception:
        pass
    return {"current": "auto", "available": available_profiles}

@app.post("/api/models/gemini")
async def set_gemini_model(request: Request):
    """Sets the preferred FinOps profile."""
    try:
        body = await request.json()
        profile_name = body.get("model", "auto").lower()
        
        cfg = {}
        if SODA_CONFIG_PATH.exists():
            cfg = json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
            
        cfg["finops_profile"] = profile_name
        SODA_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"status": "ok", "current": profile_name}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/finops/status")
async def get_finops_status():
    """Returns the current FinOps mode state (boolean for the React UI)."""
    try:
        if SODA_CONFIG_PATH.exists():
            cfg = json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
            current = cfg.get("finops_profile", "auto")
            finops_mode = current in ("auto", "economy", "balanced")
            return {"finops_mode": finops_mode}
    except Exception:
        pass
    return {"finops_mode": True}


@app.post("/api/finops/toggle")
async def toggle_finops_mode():
    """Toggles FinOps mode on/off (Auto/Economy vs Premium/None)."""
    try:
        cfg = {}
        if SODA_CONFIG_PATH.exists():
            cfg = json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
            
        current = cfg.get("finops_profile", "auto")
        if current in ("auto", "economy", "balanced"):
            new_profile = "premium"
            finops_mode = False
        else:
            new_profile = "auto"
            finops_mode = True
            
        cfg["finops_profile"] = new_profile
        SODA_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"finops_mode": finops_mode}
    except Exception as e:
        return {"error": str(e), "finops_mode": True}


@app.post("/api/config")
async def set_soda_config(request: Request):
    """Merge and save SODA model/provider preferences to soda_config.json."""
    body = await request.json()
    existing = {}
    try:
        if SODA_CONFIG_PATH.exists():
            existing = json.loads(SODA_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    existing.update(body)
    SODA_CONFIG_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    # Apply model env vars immediately AND persist to .env for restarts
    from dotenv import set_key as _set_key
    model_map = {
        "claude_model": "CLAUDE_MODEL", "gemini_model": "GEMINI_MODEL",
        "ollama_model": "OLLAMA_MODEL",
        "ollama_base_url": "OLLAMA_BASE_URL",
    }
    for cfg_key, env_key in model_map.items():
        if cfg_key in existing:
            os.environ[env_key] = existing[cfg_key]
            try:
                _set_key(str(ENV_PATH), env_key, existing[cfg_key])
            except Exception:
                pass
    return {"status": "saved"}


@app.post("/api/event")
async def receive_event(request: Request):
    payload = await request.json()
    await manager.broadcast(payload)
    
    # Reenviar a Telegram
    try:
        if _get_telegram().is_configured():
            await _get_telegram().send_event(
                event_type=payload.get("event_type", "LOG"),
                text=payload.get("message", ""),
                data=payload.get("data")
            )
    except Exception as e:
        print(f"  [Server] Error al reenviar evento a Telegram: {e}")
        
    return {"status": "ok"}


# ── Project Resources ────────────────────────────────────────────────────────

_PROJECTS_BASE = Path(__file__).resolve().parent.parent / "projects"


def _resources_dir(project_id: str) -> Path:
    return _PROJECTS_BASE / project_id / "resources"


def _resources_manifest(project_id: str) -> Path:
    return _PROJECTS_BASE / project_id / "resources_manifest.json"


def _load_manifest(project_id: str) -> dict:
    p = _resources_manifest(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_manifest(project_id: str, manifest: dict):
    p = _resources_manifest(project_id)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_resource_key(key: str) -> str:
    return re.sub(r"[^\w.\-]", "_", key)[:120]


@app.post("/api/projects/{project_id}/resources/upload")
async def upload_resource(project_id: str, file: UploadFile = File(...)):
    """Upload a file resource for a project."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    rdir = _resources_dir(project_id)
    rdir.mkdir(parents=True, exist_ok=True)

    filename = _safe_resource_key(file.filename or "resource")
    dest = rdir / filename
    # Avoid collisions
    if dest.exists():
        stem, _, ext = filename.rpartition(".")
        import uuid as _uuid
        filename = f"{stem}_{_uuid.uuid4().hex[:6]}.{ext}" if ext else f"{filename}_{_uuid.uuid4().hex[:6]}"
        dest = rdir / filename

    content = await file.read()
    dest.write_bytes(content)

    manifest = _load_manifest(project_id)
    import datetime as _dt
    manifest[filename] = {
        "type": "file",
        "filename": filename,
        "mime_type": file.content_type or "application/octet-stream",
        "size": len(content),
        "intent": "",
        "uploaded_at": _dt.datetime.utcnow().isoformat(),
    }
    _save_manifest(project_id, manifest)
    return {"status": "ok", "key": filename, "resource": manifest[filename]}


@app.post("/api/projects/{project_id}/resources/link")
async def add_resource_link(project_id: str, request: Request):
    """Add an external link or text snippet as a resource."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    body = await request.json()
    url = (body.get("url") or "").strip()
    text = (body.get("text") or "").strip()
    label = (body.get("label") or url or text[:60] or "recurso").strip()
    res_type = "link" if url else "text"

    if not url and not text:
        return JSONResponse({"status": "error", "message": "url or text required"}, status_code=400)

    _resources_dir(project_id).mkdir(parents=True, exist_ok=True)

    import uuid as _uuid, datetime as _dt
    key = f"{res_type}_{_uuid.uuid4().hex[:8]}"

    manifest = _load_manifest(project_id)
    manifest[key] = {
        "type": res_type,
        "key": key,
        "label": label,
        "url": url,
        "text": text,
        "intent": "",
        "added_at": _dt.datetime.utcnow().isoformat(),
    }
    _save_manifest(project_id, manifest)
    return {"status": "ok", "key": key, "resource": manifest[key]}


@app.get("/api/projects/{project_id}/resources")
async def list_resources(project_id: str):
    """List all resources for a project."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    return {"resources": _load_manifest(project_id)}


@app.get("/api/projects/{project_id}/resources/{key}")
async def serve_resource(project_id: str, key: str):
    """Serve a file resource."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    manifest = _load_manifest(project_id)
    entry = manifest.get(key)
    if not entry or entry.get("type") != "file":
        return JSONResponse({"status": "error", "message": "not found"}, status_code=404)
    path = _resources_dir(project_id) / key
    if not path.exists():
        return JSONResponse({"status": "error", "message": "file missing"}, status_code=404)
    return FileResponse(str(path), media_type=entry.get("mime_type", "application/octet-stream"))


@app.put("/api/projects/{project_id}/resources/{key}/intent")
async def set_resource_intent(project_id: str, key: str, request: Request):
    """Set or update the intent for a resource."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    body = await request.json()
    intent = (body.get("intent") or "").strip()
    manifest = _load_manifest(project_id)
    if key not in manifest:
        return JSONResponse({"status": "error", "message": "resource not found"}, status_code=404)
    manifest[key]["intent"] = intent
    _save_manifest(project_id, manifest)
    return {"status": "ok"}


@app.delete("/api/projects/{project_id}/resources/{key}")
async def delete_resource(project_id: str, key: str):
    """Delete a resource."""
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)
    manifest = _load_manifest(project_id)
    entry = manifest.pop(key, None)
    if entry and entry.get("type") == "file":
        try:
            (_resources_dir(project_id) / key).unlink(missing_ok=True)
        except Exception:
            pass
    _save_manifest(project_id, manifest)
    return {"status": "ok"}


@app.post("/api/projects/{project_id}/resources/apply")
async def apply_resources(project_id: str, request: Request):
    """Apply resource intents to the project via the modify pipeline."""
    global _pipeline_running
    if _pipeline_running:
        return JSONResponse({"status": "busy"}, status_code=409)
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    body = await request.json()
    keys = body.get("keys") or []  # specific keys to apply; empty = all with intent

    manifest = _load_manifest(project_id)
    items = [(k, v) for k, v in manifest.items() if v.get("intent") and (not keys or k in keys)]
    if not items:
        return JSONResponse({"status": "error", "message": "No hay recursos con intención definida"}, status_code=400)

    lines = []
    for key, v in items:
        label = v.get("label") or v.get("filename") or key
        intent = v["intent"]
        res_type = v.get("type", "file")
        if res_type == "file":
            lines.append(f"- Recurso '{label}' (archivo): {intent}")
        elif res_type == "link":
            lines.append(f"- Recurso '{label}' (enlace {v.get('url','')}): {intent}")
        else:
            lines.append(f"- Recurso '{label}' (texto): {intent}")

    composite_request = "Incorporar los siguientes recursos al proyecto:\n" + "\n".join(lines)

    from kernel.orchestrator import SodaOrchestrator, Project, ProjectState
    meta = _project_manager.load_metadata(project_id)
    project = Project(
        id=meta["id"], description=meta["description"],
        state=ProjectState(meta["state"]),
        workspace=_project_manager.project_dir(project_id),
        blueprint=meta.get("blueprint", {}),
        architecture=meta.get("architecture", {}),
        skills=meta.get("skills", []),
        profile=meta.get("profile", ""),
    )
    orchestrator = _get_orchestrator()
    result = await orchestrator.modify(project, composite_request)
    return {"status": "ok", "result": result}


# ── Connectivity (mobile QR pairing) ─────────────────────────────────────────

import secrets
import socket
import time as _time
from fastapi.responses import HTMLResponse

_connectivity_tokens: dict[str, dict] = {}  # pin → {expires_at, used}
_CONN_TOKEN_TTL = 300  # 5 minutes


def _get_local_ip() -> str:
    """Return LAN IP of this machine (not loopback)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _clean_expired_tokens():
    now = _time.time()
    expired = [k for k, v in _connectivity_tokens.items() if v["expires_at"] < now]
    for k in expired:
        del _connectivity_tokens[k]


@app.get("/api/connectivity/info")
async def connectivity_info():
    """Generate a one-time 6-digit PIN + LAN URL for QR-based mobile pairing."""
    _clean_expired_tokens()
    pin = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    _connectivity_tokens[pin] = {
        "expires_at": _time.time() + _CONN_TOKEN_TTL,
        "used": False,
    }
    ip = _get_local_ip()
    port = _SERVER_PORT
    connect_url = f"http://{ip}:{port}/connect?pin={pin}"
    return {
        "ip": ip,
        "port": port,
        "pin": pin,
        "connect_url": connect_url,
        "expires_in": _CONN_TOKEN_TTL,
    }


@app.get("/connect", response_class=HTMLResponse)
async def mobile_connect(pin: str = ""):
    """Mobile lands here after scanning QR. Validates PIN and serves redirect page."""
    now = _time.time()
    token = _connectivity_tokens.get(pin)

    if not token or token["expires_at"] < now:
        return HTMLResponse(_connect_page(
            ok=False,
            message="Código inválido o expirado. Generá uno nuevo desde la app.",
            redirect=None,
        ), status_code=403)

    if token["used"]:
        return HTMLResponse(_connect_page(
            ok=False,
            message="Este código ya fue utilizado. Generá uno nuevo.",
            redirect=None,
        ), status_code=403)

    token["used"] = True
    ip = _get_local_ip()
    app_url = f"http://{ip}:{_SERVER_PORT}/"
    # Broadcast to desktop UI
    await manager.broadcast({
        "event_type": "MOBILE_CONNECTED",
        "message": "Móvil conectado exitosamente",
        "data": {"pin": pin},
    })
    return HTMLResponse(_connect_page(ok=True, message="¡Conectado!", redirect=app_url))


def _connect_page(ok: bool, message: str, redirect: str | None) -> str:
    color = "#34d399" if ok else "#f87171"
    icon = "✓" if ok else "✕"
    redirect_script = (
        f'<script>setTimeout(()=>window.location.href="{redirect}",2000);</script>'
        if redirect else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SODA — Conectividad</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{font-family:'Inter',system-ui,sans-serif;background:#000;color:#fff;
       display:flex;align-items:center;justify-content:center;min-height:100vh;}}
  .card{{text-align:center;padding:48px 32px;background:#111;border:1px solid #222;
         border-radius:16px;max-width:340px;width:90%;}}
  .icon{{font-size:64px;color:{color};margin-bottom:20px;}}
  h1{{font-size:22px;font-weight:800;margin-bottom:12px;color:{color};}}
  p{{font-size:14px;color:#888;line-height:1.6;}}
  .sub{{font-size:12px;color:#555;margin-top:16px;}}
</style>
{redirect_script}
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{message}</h1>
    {'<p>Redirigiendo a SODA en 2 segundos…</p>' if redirect else '<p>Cerrá esta página e intentá de nuevo.</p>'}
    <p class="sub">SODA Mission Control</p>
  </div>
</body>
</html>"""


@app.get("/api/env")
async def get_env():
    """Returns which keys are configured (no values exposed)."""
    return {key: bool(os.getenv(key, "")) for key in ENV_KEYS}


@app.post("/api/env")
async def set_env(request: Request):
    """Save API keys to .env and reload in the current process."""
    from dotenv import set_key
    body = await request.json()
    for key, value in body.items():
        if key not in ENV_KEYS:
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        set_key(str(ENV_PATH), key, value.strip())
        os.environ[key] = value.strip()
    load_dotenv(ENV_PATH, override=True)
    return {"status": "saved"}


@app.get("/api/ai/providers")
async def list_custom_providers():
    """List all custom AI providers stored in soda_config.json (api_key redacted)."""
    cfg = _read_config()
    providers = cfg.get("custom_providers", [])
    safe = []
    for p in providers:
        safe.append({
            "name": p.get("name", ""),
            "display_name": p.get("display_name", p.get("name", "")),
            "model": p.get("model", ""),
            "base_url": p.get("base_url", ""),
            "driver_type": p.get("driver_type", "openai_compat"),
            "has_key": bool(p.get("api_key", "").strip()),
        })
    return {"providers": safe}


@app.post("/api/ai/providers")
async def add_custom_provider(request: Request):
    """Add or update a custom AI provider."""
    body = await request.json()
    name = (body.get("name") or "").strip().lower()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    api_key = (body.get("api_key") or "").strip()
    if not api_key:
        return JSONResponse({"error": "api_key is required"}, status_code=400)

    from kernel.drivers.driver_factory import get_default_base_url, get_default_model, detect_driver_type
    base_url = (body.get("base_url") or get_default_base_url(name) or "").strip()
    model = (body.get("model") or get_default_model(name) or "").strip()
    driver_type = (body.get("driver_type") or detect_driver_type(name, base_url)).strip()
    display_name = (body.get("display_name") or name.capitalize()).strip()

    cfg = _read_config()
    providers: list = cfg.setdefault("custom_providers", [])
    # Upsert by name
    existing = next((i for i, p in enumerate(providers) if p.get("name") == name), None)
    entry = {
        "name": name,
        "display_name": display_name,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "driver_type": driver_type,
    }
    if existing is not None:
        providers[existing] = entry
    else:
        providers.append(entry)
    _write_config(cfg)

    # Persist api key in .env as <UPPER_NAME>_API_KEY
    env_key = f"{name.upper()}_API_KEY"
    try:
        from dotenv import set_key as _set_key
        _set_key(str(ENV_PATH), env_key, api_key)
        os.environ[env_key] = api_key
    except Exception:
        pass

    return {"status": "saved", "name": name}


@app.delete("/api/ai/providers/{name}")
async def delete_custom_provider(name: str):
    """Remove a custom AI provider."""
    cfg = _read_config()
    providers: list = cfg.get("custom_providers", [])
    before = len(providers)
    cfg["custom_providers"] = [p for p in providers if p.get("name") != name.lower()]
    if len(cfg["custom_providers"]) == before:
        return JSONResponse({"error": f"Provider '{name}' not found"}, status_code=404)
    _write_config(cfg)
    return {"status": "deleted", "name": name}


@app.get("/api/ai/known-providers")
async def list_known_providers():
    """Return the catalog of known providers with their default config (no keys)."""
    from kernel.drivers.driver_factory import KNOWN_PROVIDERS
    return {
        "providers": [
            {
                "name": name,
                "display_name": info.get("display_name", name.capitalize()),
                "base_url": info["base_url"],
                "driver_type": info["type"],
                "default_model": info["default_model"],
            }
            for name, info in KNOWN_PROVIDERS.items()
        ]
    }


@app.get("/api/ai/test-custom/{name}")
async def test_custom_provider(name: str):
    """Quick connectivity test for a custom provider."""
    import time, httpx as _httpx
    cfg = _read_config()
    providers = cfg.get("custom_providers", [])
    entry = next((p for p in providers if p.get("name") == name.lower()), None)
    if not entry:
        return JSONResponse({"ok": False, "error": f"Provider '{name}' not found"}, status_code=404)

    t0 = time.monotonic()
    api_key = entry.get("api_key", "")
    base_url = (entry.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = entry.get("model") or "gpt-4o-mini"

    try:
        async with _httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
            )
        if r.status_code == 200:
            return {"ok": True, "model": model, "latency_ms": int((time.monotonic() - t0) * 1000)}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:120]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


# ── STT endpoint ──────────────────────────────────────────────────────────────

@app.post("/api/stt/transcribe")
async def stt_transcribe(request: Request):
    """Transcribe uploaded audio (webm/ogg/wav) and return text."""
    form = await request.form()
    audio_file = form.get("audio")
    if not audio_file:
        return JSONResponse({"error": "audio is required"}, status_code=400)
    try:
        from kernel.stt.whisper_stt import WhisperSTT, is_available as stt_ok
        if not stt_ok():
            return JSONResponse({"error": "faster-whisper not installed"}, status_code=503)
        import tempfile, shutil as _shutil
        suffix = Path(getattr(audio_file, "filename", None) or "rec.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            _shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = tmp.name
        text = WhisperSTT.get().transcribe_file(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return {"text": text}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── TTS endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/tts/status")
async def tts_status():
    """Returns TTS availability and current config."""
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available, tts_enabled
        available = is_available()
        if available:
            info = KokoroTTS.get().list_voices()
        else:
            info = {}
        return {"available": available, "enabled": tts_enabled(), **info}
    except Exception as e:
        return {"available": False, "enabled": False, "error": str(e)}


@app.post("/api/tts/toggle")
async def tts_toggle(request: Request):
    """Enable or disable TTS (persists to soda_config.json)."""
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    cfg = _read_config()
    cfg["tts_enabled"] = enabled
    _write_config(cfg)
    return {"status": "ok", "tts_enabled": enabled}


@app.get("/api/tts/voices")
async def tts_voices():
    """List available TTS voices."""
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        return KokoroTTS.get().list_voices()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tts/set_voice")
async def tts_set_voice(request: Request):
    """Set the active TTS voice."""
    body = await request.json()
    voice = (body.get("voice") or "").strip()
    if not voice:
        return JSONResponse({"error": "voice is required"}, status_code=400)
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        KokoroTTS.get().set_voice(voice)
        return {"status": "ok", "voice": voice}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tts/set_speed")
async def tts_set_speed(request: Request):
    """Set the TTS speech speed (0.5 – 2.0)."""
    body = await request.json()
    try:
        speed = float(body.get("speed", 1.0))
    except (TypeError, ValueError):
        return JSONResponse({"error": "speed must be a number"}, status_code=400)
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        KokoroTTS.get().set_speed(speed)
        return {"status": "ok", "speed": speed}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tts/generate")
async def tts_generate(request: Request):
    """Generate WAV audio for the given text and return it as audio/wav."""
    from fastapi.responses import Response as FastResponse
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    voice = body.get("voice") or None
    speed = body.get("speed") or None
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available, tts_enabled
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        if not tts_enabled():
            return JSONResponse({"error": "TTS disabled"}, status_code=503)
        wav = await KokoroTTS.get().generate_wav(text, voice_name=voice, speed=speed)
        if not wav:
            return JSONResponse({"error": "Empty audio generated"}, status_code=500)
        return FastResponse(content=wav, media_type="audio/wav")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tts/clone_voice")
async def tts_clone_voice(request: Request):
    """Register a reference voice for F5-TTS from an uploaded audio file + transcript."""
    import tempfile, shutil
    from fastapi.datastructures import UploadFile as UF
    form = await request.form()
    name_raw = str(form.get("name") or "").strip()
    ref_text = str(form.get("ref_text") or "").strip()
    audio_file: UF = form.get("audio")  # type: ignore
    if not name_raw or not audio_file:
        return JSONResponse({"error": "name and audio are required"}, status_code=400)
    import re as _re
    name = _re.sub(r"[^a-zA-Z0-9_\-]", "", name_raw)[:40]
    if not name:
        return JSONResponse({"error": "invalid voice name"}, status_code=400)
    try:
        from kernel.tts.kokoro_tts import is_available, VOICES_DIR
        from kernel.tts.voice_cloner import save_reference_voice
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        suffix = Path(audio_file.filename or "ref.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = tmp.name
        save_reference_voice(tmp_path, name, ref_text, VOICES_DIR)
        Path(tmp_path).unlink(missing_ok=True)
        return {"status": "ok", "voice": name}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/tts/voices/{voice_name}")
async def tts_delete_voice(voice_name: str):
    """Delete a custom voice."""
    try:
        from kernel.tts.kokoro_tts import KokoroTTS, is_available
        if not is_available():
            return JSONResponse({"error": "Edge TTS not installed"}, status_code=503)
        ok = KokoroTTS.get().delete_voice(voice_name)
        if not ok:
            return JSONResponse({"error": "Voice not found or is built-in"}, status_code=404)
        return {"status": "ok", "deleted": voice_name}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/answer")
async def submit_answer(request: Request):
    """Receive the user's answer to a pending USER_QUESTION and resume the pipeline."""
    from kernel.communication.user_interaction import get_gateway
    body = await request.json()
    text = (body.get("answer") or "").strip()
    project_id = body.get("project_id")
    
    gw = get_gateway()
    if gw.is_waiting:
        gw.answer(text)
        return {"status": "ok"}
        
    # Bridge Check: ¿Hay un proceso externo (script) esperando?
    if project_id:
        pdir = _PROJECTS_BASE / project_id
        q_file = pdir / ".pending_question"
        if q_file.exists():
            a_file = pdir / ".pending_answer"
            a_file.write_text(json.dumps({"answer": text, "timestamp": time.time()}), encoding="utf-8")
            # Notificar visualmente que se respondió (opcional)
            await manager.broadcast({"event_type": "QUESTION_ANSWERED", "message": "Respuesta enviada al motor externo.", "data": {}})
            return {"status": "ok", "bridged": True}

    return JSONResponse({"status": "error", "message": "No hay pregunta pendiente"}, status_code=409)


@app.post("/api/answer/extend")
async def extend_answer_timeout():
    """Reset the answer timeout — called while the user is actively typing."""
    from kernel.communication.user_interaction import get_gateway
    gw = get_gateway()
    extended = gw.extend()
    return {"extended": extended}


@app.get("/api/question")
async def get_current_question():
    """Returns the current pending question, if any, checking both memory and disk bridge."""
    global _pipeline_running, _active_orchestrator
    if not _pipeline_running:
        return {"waiting": False, "question": None}

    from kernel.communication.user_interaction import get_gateway
    gw = get_gateway()
    
    # 1. Check memory (Internal pipeline)
    if gw.is_waiting:
        return {"waiting": True, "question": gw.current_question}
        
    # 2. Check bridge (External pipeline/script)
    # We look for the active project with a pending question file
    active_project_id = None
    if _active_orchestrator and hasattr(_active_orchestrator, "_active_project") and _active_orchestrator._active_project:
        active_project_id = _active_orchestrator._active_project.id

    if active_project_id:
        try:
            pdir = _PROJECTS_BASE / active_project_id
            q_file = pdir / ".pending_question"
            if q_file.exists():
                data = json.loads(q_file.read_text(encoding="utf-8"))
                return {
                    "waiting": True, 
                    "question": data.get("question"),
                    "project_id": active_project_id
                }
        except Exception:
            pass

    return {"waiting": False, "question": None}


_OPEN_FILE_RE = re.compile(
    r'(?:abri[ró]?|abre|open|ver|muestra|mostrar|show)\s+(?:el\s+archivo\s+|archivo\s+|file\s+)?'
    r'([^\s"\']+\.[a-zA-Z0-9]{1,8})',
    re.IGNORECASE,
)


def _find_file_in_source(source_dir: Path, filename: str) -> tuple[str, str] | None:
    """Search source_dir for a file matching the name. Returns (rel_path, content) or None."""
    target = filename.lower()
    text_exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
                 ".yaml", ".yml", ".md", ".txt", ".sh", ".toml", ".cfg", ".ini", ".env"}
    for p in sorted(source_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in text_exts and "node_modules" not in str(p):
            if p.name.lower() == target or p.relative_to(source_dir).as_posix().lower() == target:
                rel = p.relative_to(source_dir).as_posix()
                try:
                    return rel, p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    return rel, ""
    return None


@app.post("/api/chat")
async def chat_project(request: Request):
    """Answer questions about a generated project using its blueprint + architecture as context."""
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    message = (body.get("message") or "").strip()
    if not message:
        return JSONResponse({"status": "error", "message": "Mensaje vacío"}, status_code=400)

    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "Proyecto no encontrado"}, status_code=404)

    source_dir = _project_manager.source_dir(project_id)

    # Open-file intent detection — intercept before AI call
    m = _OPEN_FILE_RE.search(message)
    if m and source_dir.exists():
        target_name = m.group(1)
        found = _find_file_in_source(source_dir, target_name)
        if found:
            rel_path, content = found
            await manager.broadcast({
                "event_type": "OPEN_FILE",
                "message": f"Abriendo {rel_path}",
                "data": {"filename": rel_path, "code": content},
            })
            return {"status": "ok", "answer": f"Abriendo `{rel_path}` en el editor.", "opened_file": rel_path}
        else:
            return {"status": "ok", "answer": f"No encontré el archivo `{target_name}` en el proyecto.", "opened_file": None}

    meta = _project_manager.load_metadata(project_id)

    from kernel.drivers.gemini_driver import GeminiDriver
    driver = GeminiDriver()
    response = await _project_chat.answer(driver, meta, source_dir, message)
    if _get_telegram().is_configured():
        asyncio.create_task(
            _get_telegram().send_from_loop(f"[Chat/{project_id}]\nQ: {message[:300]}\nA: {response[:300]}")
        )
    return {"status": "ok", "answer": response}


@app.post("/api/open_in_editor")
async def open_in_editor(request: Request):
    """Open a specific project file in the Monaco editor via WebSocket broadcast."""
    body = await request.json()
    project_id = (body.get("project_id") or "").strip()
    filepath = (body.get("filepath") or "").strip()
    if not project_id or not filepath:
        return JSONResponse({"status": "error", "message": "project_id and filepath required"}, status_code=400)
    if not _project_manager.exists(project_id):
        return JSONResponse({"status": "error", "message": "Proyecto no encontrado"}, status_code=404)

    source_dir = _project_manager.source_dir(project_id)
    target = (source_dir / filepath).resolve()
    if not str(target).startswith(str(source_dir.resolve())):
        return JSONResponse({"status": "error", "message": "Ruta inválida"}, status_code=400)
    if not target.exists():
        return JSONResponse({"status": "error", "message": "Archivo no encontrado"}, status_code=404)

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    rel = target.relative_to(source_dir).as_posix()
    await manager.broadcast({
        "event_type": "OPEN_FILE",
        "message": f"Abriendo {rel}",
        "data": {"filename": rel, "code": content},
    })
    return {"status": "ok", "filename": rel}


@app.get("/api/learning/stats")
async def learning_stats():
    """Return counts from the AI learning system — observations + knowledge base patterns."""
    try:
        from kernel.learning.behavior_observer import BehaviorObserver
        from kernel.learning.knowledge_base import KnowledgeBase
        obs = BehaviorObserver()
        kb = KnowledgeBase()
        return {
            "status": "ok",
            "observations": obs.stats(),
            "patterns": kb.stats(),
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/learning/synthesize")
async def learning_synthesize():
    """Manually trigger synthesis of raw observations into curated patterns."""
    try:
        from kernel.learning.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        added = kb.synthesize_from_observations()
        return {"status": "ok", "new_patterns": added, "total": kb.stats()}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/research")
async def research_web(request: Request):
    body = await request.json()
    url = (body.get("url") or "").strip()
    if not url:
        return JSONResponse({"status": "error", "message": "url is required"}, status_code=400)

    try:
        result = _web_researcher.fetch(url)
        return {
            "status": "ok",
            "result": {
                "url": result.url,
                "status_code": result.status_code,
                "title": result.title,
                "excerpt": result.excerpt,
            },
        }
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/references/analyze")
async def analyze_references(request: Request):
    body = await request.json()
    text = body.get("text") or ""
    report = _reference_analyzer.analyze(text)
    return {
        "status": "ok",
        "report": {
            "total_urls": report.total_urls,
            "unique_urls": report.unique_urls,
            "broken_candidates": report.broken_candidates,
        },
    }


@app.post("/api/vision/capture")
async def capture_vision(request: Request):
    body = await request.json()
    image_path = (body.get("image_path") or "").strip()
    if not image_path:
        return JSONResponse({"status": "error", "message": "image_path is required"}, status_code=400)

    capture = _vision_capturer.capture(Path(image_path))
    return {
        "status": "ok",
        "capture": {
            "path": capture.path,
            "exists": capture.exists,
            "size_bytes": capture.size_bytes,
        },
    }


@app.post("/api/vision/inspect")
async def inspect_visual(request: Request):
    body = await request.json()
    image_path = (body.get("image_path") or "").strip()
    if not image_path:
        return JSONResponse({"status": "error", "message": "image_path is required"}, status_code=400)

    inspection = _visual_inspector.inspect(Path(image_path))
    return {
        "status": "ok",
        "inspection": {
            "path": inspection.path,
            "format": inspection.format,
            "size_bytes": inspection.size_bytes,
            "valid_image": inspection.valid_image,
        },
    }


@app.post("/api/intensity")
async def estimate_intensity(request: Request):
    body = await request.json()
    text = body.get("text") or ""
    profile = _intensity_orchestrator.choose_profile(text)
    return {
        "status": "ok",
        "level": profile.label,
        "execution_level": profile.level,
        "profile": profile.to_dict(),
    }


@app.post("/api/system/action")
async def execute_system_action(request: Request):
    body = await request.json()
    action = (body.get("action") or "").strip()
    params = body.get("params") or {}
    if not action:
        return JSONResponse({"status": "error", "message": "action is required"}, status_code=400)

    try:
        result = _system_actions.execute(action, params)
        return {
            "status": "ok",
            "result": {
                "action": result.action,
                "target": result.target,
                "launched": result.launched,
                "message": result.message,
            },
        }
    except FileNotFoundError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/selfrepair/run")
async def selfrepair_run(request: Request):
    """Launch a self-repair cycle. Stages/apply_fixes are optional."""
    body = await request.json()
    stages = body.get("stages") or None          # list[str] or null = all
    apply_fixes = bool(body.get("apply_fixes", False))
    label = str(body.get("label") or "api")

    def _notify(msg, ev_type, data):
        import asyncio as _aio
        payload = {"event_type": ev_type, "message": msg, "data": data or {}}
        try:
            loop = _aio.get_running_loop()
            loop.create_task(manager.broadcast(payload))
        except Exception:
            pass

    async def _run():
        from kernel.selfrepair.system_healer import SystemHealer
        from kernel.drivers.gemini_driver import GeminiDriver
        try:
            base = Path(__file__).resolve().parent.parent
            healer = SystemHealer(base_dir=base, gemini_driver=GeminiDriver(), notify_fn=_notify)
            report = await healer.run(stages=stages, apply_fixes=apply_fixes, label=label)
            summary = report.to_dict()["summary"]
            _notify(
                f"AutoReparacion completada: {summary['files_analyzed']} archivos, "
                f"{summary['errors_found']} errores, {summary['improvements_suggested']} mejoras.",
                "SELFREPAIR_DONE",
                summary,
            )
        except Exception as e:
            import traceback
            _notify(f"AutoReparacion error: {e}", "SELFREPAIR_ERROR", {"traceback": traceback.format_exc()[-1000:]})

    asyncio.create_task(_run())
    return {"status": "started", "stages": stages or "all", "apply_fixes": apply_fixes}


@app.get("/api/selfrepair/backups")
async def selfrepair_backups():
    """List available backups."""
    from kernel.selfrepair.backup_manager import BackupManager
    base = Path(__file__).resolve().parent.parent
    return {"backups": BackupManager(base).list_backups()}


@app.post("/api/selfrepair/restore")
async def selfrepair_restore(request: Request):
    """Restore from a backup by name."""
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"status": "error", "message": "name is required"}, status_code=400)
    from kernel.selfrepair.backup_manager import BackupManager
    base = Path(__file__).resolve().parent.parent
    ok = BackupManager(base).restore(name)
    return {"status": "ok" if ok else "error", "restored": name}


@app.get("/api/tools/registry")
async def get_tool_registry(category: str | None = None, capability: str | None = None):
    return {
        "status": "ok",
        "items": _tool_registry.list_tools(category=category, capability=capability),
    }


@app.get("/api/tools/registry/{tool_key}")
async def get_tool_registry_item(tool_key: str):
    try:
        return {"status": "ok", "item": _tool_registry.get_tool(tool_key)}
    except KeyError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)


@app.get("/api/capability_packs")
async def get_capability_packs(domain: str | None = None):
    return {
        "status": "ok",
        "items": _capability_pack_registry.list_packs(domain=domain),
    }


@app.get("/api/capability_packs/{pack_key}")
async def get_capability_pack_item(pack_key: str):
    try:
        return {"status": "ok", "item": _capability_pack_registry.get_pack(pack_key)}
    except KeyError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)


@app.get("/api/project_types")
async def get_project_types():
    return {"status": "ok", "items": _project_type_registry.list_types()}


@app.get("/api/project_types/{project_type_key}")
async def get_project_type_item(project_type_key: str):
    try:
        return {"status": "ok", "item": _project_type_registry.get_type(project_type_key)}
    except KeyError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=404)


@app.get("/api/tokens")
async def get_tokens():
    """Returns token usage summary from the active orchestrator."""
    global _active_orchestrator
    if _active_orchestrator is None:
        return {"total_calls": 0, "total_tokens_estimate": 0, "error_count": 0, "health_level": 0, "health_reason": "no session"}
    return _active_orchestrator.health.summary()


@app.get("/api/usage/summary")
async def get_usage_summary():
    recent = _usage_monitor.recent_calls(limit=100)
    rows = [
        {
            "date":          r["timestamp"][:10] if r.get("timestamp") else "—",
            "driver":        r.get("provider", "—"),
            "model":         r.get("model", "—"),
            "tokens_in":     r.get("tokens_input", 0),
            "tokens_out":    r.get("tokens_output", 0),
            "avg_latency_s": round(r.get("latency_ms", 0) / 1000, 2),
            "total_cost_usd": r.get("cost_usd", 0.0),
        }
        for r in recent
    ]
    return {
        "summary": _usage_monitor.summary(),
        "by_provider_model": _usage_monitor.grouped_summary(),
        "rows": rows,
    }


@app.get("/api/usage/recent")
async def get_usage_recent(limit: int = 25):
    return {
        "items": _usage_monitor.recent_calls(limit=limit),
    }


@app.get("/api/alerts")
async def get_alerts():
    return {
        "status": "ok",
        "items": _alert_manager.evaluate(),
    }



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Replay any pending question so a fresh/reconnected browser doesn't miss it
    try:
        from kernel.communication.user_interaction import get_gateway as _get_gw
        gw = _get_gw()
        if gw.is_waiting and gw.current_question:
            q = gw.current_question
            await websocket.send_json({
                "event_type": "USER_QUESTION",
                "message": q,
                "data": {"question": q},
            })
    except Exception:
        pass
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
