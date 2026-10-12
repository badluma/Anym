from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .classes import *
from .store import store

HISTORY_ON_JOIN = 50  # messages replayed when someone joins


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.open()
    yield
    await store.close()

app = FastAPI(lifespan=lifespan)
# ponytail: wide open for dev; restrict to the client origin when deployed
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
manager = ConnectionManager()


def system(token: str, text: str) -> Message:
    """Join/leave notices: broadcast only, never stored."""
    return Message(name="system", color="#888888", token=token, message=text,
                   timestamp=datetime.now(timezone.utc))


@app.post("/chats")
async def create_chat():
    token, secret = await store.create()
    return {"token": token, "secret": secret}


@app.post("/chats/check")
async def check_chat(body: TokenBody):
    return await store.exists(body.token)


@app.websocket("/ws")
async def chat(websocket: WebSocket):
    """First msg {token, name, color}: join room (1008 close if unknown token),
    replay history. After: {message} -> broadcast to room only."""
    await websocket.accept()
    try:
        join = Join.model_validate_json(await websocket.receive_text())
    except ValidationError:
        return await websocket.close(code=1008)
    except WebSocketDisconnect:
        return
    token = join.token
    if not await store.exists(token):
        return await websocket.close(code=1008)

    for m in await store.history(token, limit=HISTORY_ON_JOIN):
        await manager.send_message(websocket, m)
    manager.join(token, websocket, join.name)
    await manager.broadcast(system(token, f"{join.name} joined"))
    try:
        while True:
            try:
                inc = Incoming.model_validate_json(await websocket.receive_text())
            except ValidationError:
                continue  # ignore bad frames
            msg = Message(name=join.name, color=join.color, token=token,
                          message=inc.message, timestamp=datetime.now(timezone.utc))
            await store.add(token, msg)
            await manager.broadcast(msg)
    except WebSocketDisconnect:
        pass
    finally:
        manager.leave(token, websocket)
        await manager.broadcast(system(token, f"{join.name} left"))


@app.post("/chats/messages")
async def chat_messages(body: HistoryBody):
    """Paginated history: pass oldest timestamp seen as `before` for next page."""
    if not await store.exists(body.token):
        raise HTTPException(404)
    msgs = await store.history(body.token, body.before, min(body.limit, 100))
    return [m.model_dump(mode="json", exclude={"token"}) for m in msgs]


@app.post("/chats/members")
async def chat_members(body: TokenBody):
    """Online usernames in room."""
    return manager.members(body.token)


@app.delete("/chats")
async def delete_chat(body: DeleteBody):
    """Delete chat. Requires creator secret."""
    if not await store.delete(body.token, body.secret):
        raise HTTPException(403)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"ok": True}
