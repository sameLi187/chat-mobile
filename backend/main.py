from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Chat Mobile Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "chat.db"
JWT_SECRET = os.getenv("JWT_SECRET", "replace-this-in-production")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=128)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", maxsplit=1)
    except ValueError:
        return False

    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return hmac.compare_digest(actual, expected)


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="无效或过期 token") from exc
    return payload


def parse_auth_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer token")
    return authorization.split(" ", maxsplit=1)[1].strip()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_users: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, user_info: dict[str, Any]) -> str:
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        self.connection_users[client_id] = user_info
        return client_id

    def disconnect(self, client_id: str) -> None:
        self.active_connections.pop(client_id, None)
        self.connection_users.pop(client_id, None)

    def online_users(self) -> list[dict[str, Any]]:
        # 同一用户多端在线时去重，仅保留唯一 user_id
        dedup: dict[int, dict[str, Any]] = {}
        for user in self.connection_users.values():
            dedup[user["user_id"]] = {
                "user_id": user["user_id"],
                "username": user["username"],
            }
        return list(dedup.values())

    async def broadcast(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        dead_connections: list[str] = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except RuntimeError:
                dead_connections.append(client_id)

        for client_id in dead_connections:
            self.disconnect(client_id)

    async def broadcast_online_snapshot(self) -> None:
        users = self.online_users()
        await self.broadcast(
            {
                "type": "online",
                "count": len(users),
                "users": users,
                "timestamp": now_iso(),
            }
        )


manager = ConnectionManager()
init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "online_users": len(manager.online_users())}


@app.post("/auth/register")
def register(payload: RegisterRequest) -> dict[str, Any]:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    conn = get_db()
    try:
        cursor = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="用户名已存在")

        password_hash = hash_password(payload.password)
        created_at = now_iso()
        result = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, created_at),
        )
        conn.commit()
        user_id = result.lastrowid
    finally:
        conn.close()

    token = create_token(user_id, username)
    return {"token": token, "user": {"user_id": user_id, "username": username}}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    username = payload.username.strip()
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(row["id"], row["username"])
    return {
        "token": token,
        "user": {"user_id": row["id"], "username": row["username"]},
    }


@app.get("/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = parse_auth_token(authorization)
    payload = decode_token(token)
    return {
        "user": {
            "user_id": int(payload["sub"]),
            "username": payload["username"],
        }
    }


@app.get("/online")
def online(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = parse_auth_token(authorization)
    decode_token(token)
    users = manager.online_users()
    return {"count": len(users), "users": users}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "").strip()
    if not token:
        await websocket.close(code=1008, reason="缺少 token")
        return

    try:
        payload = decode_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason="无效 token")
        return

    user_info = {
        "user_id": int(payload["sub"]),
        "username": payload["username"],
    }
    client_id = await manager.connect(websocket, user_info)

    await manager.broadcast(
        {
            "type": "system",
            "sender": "系统",
            "content": f'{user_info["username"]} (ID:{user_info["user_id"]}) 加入了聊天室',
            "timestamp": now_iso(),
        }
    )
    await manager.broadcast_online_snapshot()

    try:
        while True:
            raw_data = await websocket.receive_text()
            content = raw_data.strip()
            if not content:
                continue

            await manager.broadcast(
                {
                    "type": "chat",
                    "sender": user_info["username"],
                    "sender_id": user_info["user_id"],
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
                "content": f'{user_info["username"]} (ID:{user_info["user_id"]}) 离开了聊天室',
                "timestamp": now_iso(),
            }
        )
        await manager.broadcast_online_snapshot()
