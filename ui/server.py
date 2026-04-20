import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, JSONResponse
from ui.websocket_handler import manager
from kernel.resource_monitor import ResourceMonitor

app = FastAPI()
monitor = ResourceMonitor()
CONFIG_FILE = "soda_config.json"

_pipeline_running = False


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
