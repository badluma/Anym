from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import WebSocket

class Message(BaseModel):
    name: str
    color: str
    token: str
    message: str
    timestamp: datetime

class Join(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=32)
    color: str = Field(max_length=16)

class Incoming(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

class ConnectionManager:
    """Rooms: token -> {websocket: username}."""
    def __init__(self):
        self.rooms: dict[str, dict[WebSocket, str]] = {}

    def join(self, token: str, websocket: WebSocket, name: str):
        self.rooms.setdefault(token, {})[websocket] = name

    def leave(self, token: str, websocket: WebSocket):
        room = self.rooms.get(token, {})
        room.pop(websocket, None)
        if not room:
            self.rooms.pop(token, None)

    def members(self, token: str) -> list[str]:
        return sorted(self.rooms.get(token, {}).values())

    async def send_message(self, websocket: WebSocket, message: Message):
        await websocket.send_text(message.model_dump_json(exclude={"token"}))

    async def broadcast(self, message: Message):
        for ws in list(self.rooms.get(message.token, {})):
            try:
                await self.send_message(ws, message)
            except Exception:  # dead socket
                self.leave(message.token, ws)

# === Bodies ===
class TokenBody(BaseModel):
    token: str

class HistoryBody(TokenBody):
    before: datetime | None = None
    limit: int = 50

class DeleteBody(TokenBody):
    secret: str
