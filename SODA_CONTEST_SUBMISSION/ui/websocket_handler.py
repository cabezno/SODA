import asyncio
from fastapi import WebSocket
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Single-user desktop app: close stale connections before adding new one
        stale = list(self.active_connections)
        self.active_connections.clear()
        for conn in stale:
            try:
                await conn.close(code=1001)
            except Exception:
                pass
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        # Evitar modificar la lista durante la iteración usando una copia de la lista
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                try:
                    self.active_connections.remove(connection)
                except ValueError:
                    pass

manager = ConnectionManager()