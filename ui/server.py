import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from ui.websocket_handler import manager
from kernel.resource_monitor import ResourceMonitor

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI()
monitor = ResourceMonitor()
CONFIG_FILE = "soda_config.json"

_pipeline_running = False

# Start Telegram bot if token is configured
from kernel.communication.telegram_gateway import TelegramGateway as _TG
_telegram = _TG()
if _telegram._token:
    _telegram.start_bot()


@app.get("/")
async def get_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


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
    if not description:
        return JSONResponse({"status": "error", "message": "Description is required"}, status_code=400)

    async def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            from kernel.orchestrator import SodaOrchestrator
            orchestrator = SodaOrchestrator()
            await orchestrator.run(description)
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
        finally:
            _pipeline_running = False

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

    projects_dir = Path(__file__).resolve().parent.parent / "projects"
    meta_path = projects_dir / project_id / "metadata.json"
    if not meta_path.exists():
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    project = Project(
        id=meta["id"],
        description=meta["description"],
        state=ProjectState(meta["state"]),
        workspace=projects_dir / project_id,
        blueprint=meta.get("blueprint", {}),
        architecture=meta.get("architecture", {}),
        skills=meta.get("skills", []),
        profile=meta.get("profile", ""),
    )

    orchestrator = SodaOrchestrator()
    result = await orchestrator.modify(project, user_request)
    return {"status": "ok", "result": result}


@app.get("/api/lineage")
async def get_lineage():
    from pathlib import Path
    from kernel.lineage.project_lineage import ProjectLineage
    lineage = ProjectLineage(Path(__file__).resolve().parent.parent)
    return {"history": lineage.get_history()}


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

    projects_dir = Path(__file__).resolve().parent.parent / "projects"
    meta_path = projects_dir / project_id / "metadata.json"
    if not meta_path.exists():
        return JSONResponse({"status": "error", "message": "project not found"}, status_code=404)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    project = Project(
        id=meta["id"], description=meta["description"],
        state=ProjectState(meta["state"]),
        workspace=projects_dir / project_id,
        blueprint=meta.get("blueprint", {}),
        architecture=meta.get("architecture", {}),
        skills=meta.get("skills", []),
        profile=meta.get("profile", ""),
    )

    async def _run():
        global _pipeline_running
        _pipeline_running = True
        try:
            orch = SodaOrchestrator()
            await orch.refound(project)
        except Exception as e:
            await manager.broadcast({"event_type": "FAILED", "message": str(e), "data": {}})
        finally:
            _pipeline_running = False

    asyncio.create_task(_run())
    return {"status": "started"}


@app.get("/api/telegram/pair")
async def telegram_pair():
    code = _telegram.generate_pairing_code()
    return {"code": code, "instruction": f"Send /pair {code} to your SODA bot on Telegram"}

@app.get("/api/telegram/status")
async def telegram_status():
    return {
        "configured": _telegram.is_configured(),
        "has_token": bool(_telegram._token),
        "chat_id": _telegram._chat_id,
    }

@app.get("/api/health")
async def get_health():
    return {"status": "ok"}


@app.post("/api/event")
async def receive_event(request: Request):
    payload = await request.json()
    await manager.broadcast(payload)
    return {"status": "ok"}


@app.post("/api/config")
async def set_config(request: Request):
    config = await request.json()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    return {"status": "updated"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
