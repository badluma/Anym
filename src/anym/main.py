from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from . import config, classes

app = FastAPI()
manager = classes.ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Hello, World!"}

@app.websocket("/ws/{client_id}")
async def chat(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = classes.Message.model_validate_json(data)
            except ValidationError:
                await websocket.send_text("invalid message")
                continue
            await manager.broadcast(message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(classes.Message(
            name="server",
            token="",
            message=f"Client {client_id} disconnected",
            timestamp=datetime.now(),
        ))

import secrets
secrets.token_urlsafe(64)
