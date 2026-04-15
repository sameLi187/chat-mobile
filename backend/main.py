from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Chat Mobile Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.user_names: dict[str, str] = {}

    async def connect(self, websocket: WebSocket, username: str) -> str:
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        self.user_names[client_id] = username
        return client_id

    def disconnect(self, client_id: str) -> None:
        self.active_connections.pop(client_id, None)
        self.user_names.pop(client_id, None)

    async def broadcast(self, payload: dict) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        dead_connections: list[str] = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except RuntimeError:
                dead_connections.append(client_id)

        for client_id in dead_connections:
            self.disconnect(client_id)


manager = ConnectionManager()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "online_users": len(manager.active_connections)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    username = websocket.query_params.get("username", "").strip() or "匿名用户"
    client_id = await manager.connect(websocket, username)

    await manager.broadcast(
        {
            "type": "system",
            "sender": "系统",
            "content": f"{username} 加入了聊天室",
            "timestamp": now_iso(),
        }
    )

    try:
        while True:
            raw_data = await websocket.receive_text()
            content = raw_data.strip()
            if not content:
                continue

            await manager.broadcast(
                {
                    "type": "chat",
                    "sender": manager.user_names.get(client_id, username),
                    "content": content,
                    "timestamp": now_iso(),
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(
            {
                "type": "system",
                "sender": "系统",
                "content": f"{username} 离开了聊天室",
                "timestamp": now_iso(),
            }
        )
