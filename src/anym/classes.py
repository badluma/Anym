from datetime import datetime
from pydantic import BaseModel
from fastapi import WebSocket

class Message(BaseModel):
    name: str
    token: str
    message: str
    timestamp: datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, websocket: WebSocket, message: Message):
        await websocket.send_text(message.model_dump_json(exclude={"token"}))

    async def broadcast(self, message: Message):
        for websocket in self.active_connections:
            await self.send_message(websocket, message)
