import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from ui.websocket_handler import manager
from kernel.resource_monitor import ResourceMonitor

app = FastAPI()
monitor = ResourceMonitor()
CONFIG_FILE = "soda_config.json"

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

@app.get("/api/stats")
async def get_stats():
    return {
        "vram": monitor.get_vram_info(),
        "system": monitor.get_system_stats(),
        "recommendation": monitor.get_best_model()
    }

@app.get("/api/ram_total")
async def get_ram_total():
    import psutil
    return {"ram_total_gb": psutil.virtual_memory().total / (1024 ** 3)}

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
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)