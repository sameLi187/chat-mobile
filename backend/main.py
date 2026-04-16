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


class FriendRequestBody(BaseModel):
    to_username: str = Field(min_length=1, max_length=24)


class FriendAcceptBody(BaseModel):
    from_user_id: int = Field(ge=1)


class GroupCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=48)


class GroupInviteBody(BaseModel):
    username: str = Field(min_length=1, max_length=24)


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS friend_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                UNIQUE(from_user_id, to_user_id),
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (group_id, user_id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
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


def get_user_id_from_header(authorization: str | None) -> int:
    token = parse_auth_token(authorization)
    payload = decode_token(token)
    return int(payload["sub"])


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_users: dict[str, dict[str, Any]] = {}
        self.user_clients: dict[int, set[str]] = {}

    async def connect(self, websocket: WebSocket, user_info: dict[str, Any]) -> str:
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        self.connection_users[client_id] = user_info
        uid = int(user_info["user_id"])
        self.user_clients.setdefault(uid, set()).add(client_id)
        return client_id

    def disconnect(self, client_id: str) -> None:
        user = self.connection_users.pop(client_id, None)
        self.active_connections.pop(client_id, None)
        if user:
            uid = int(user["user_id"])
            if uid in self.user_clients:
                self.user_clients[uid].discard(client_id)
                if not self.user_clients[uid]:
                    del self.user_clients[uid]

    def online_users(self) -> list[dict[str, Any]]:
        dedup: dict[int, dict[str, Any]] = {}
        for user in self.connection_users.values():
            dedup[user["user_id"]] = {
                "user_id": user["user_id"],
                "username": user["username"],
            }
        return list(dedup.values())

    async def broadcast_lobby(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        dead: list[str] = []
        for client_id, ws in self.active_connections.items():
            try:
                await ws.send_text(message)
            except RuntimeError:
                dead.append(client_id)
        for cid in dead:
            self.disconnect(cid)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        client_ids = list(self.user_clients.get(user_id, ()))
        dead: list[str] = []
        for client_id in client_ids:
            ws = self.active_connections.get(client_id)
            if not ws:
                dead.append(client_id)
                continue
            try:
                await ws.send_text(message)
            except RuntimeError:
                dead.append(client_id)
        for cid in dead:
            self.disconnect(cid)

    async def broadcast_group(self, member_user_ids: set[int], payload: dict[str, Any]) -> None:
        for uid in member_user_ids:
            await self.send_to_user(uid, payload)

    async def broadcast_online_snapshot(self) -> None:
        users = self.online_users()
        await self.broadcast_lobby(
            {
                "type": "online",
                "count": len(users),
                "users": users,
                "timestamp": now_iso(),
            }
        )


manager = ConnectionManager()
init_db()


def user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, username FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()


def are_friends(conn: sqlite3.Connection, a: int, b: int) -> bool:
    if a == b:
        return False
    row = conn.execute(
        """
        SELECT 1 FROM friend_requests
        WHERE status = 'accepted'
          AND ((from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?))
        """,
        (a, b, b, a),
    ).fetchone()
    return row is not None


def group_member_ids(conn: sqlite3.Connection, group_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT user_id FROM group_members WHERE group_id = ?",
        (group_id,),
    ).fetchall()
    return {int(r["user_id"]) for r in rows}


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


@app.post("/friends/request")
async def friend_request(
    body: FriendRequestBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    token = parse_auth_token(authorization)
    me_username = str(decode_token(token)["username"])
    conn = get_db()
    tid: int
    try:
        target = user_by_username(conn, body.to_username)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        tid = int(target["id"])
        if tid == me_id:
            raise HTTPException(status_code=400, detail="不能加自己为好友")

        existing = conn.execute(
            """
            SELECT id, status FROM friend_requests
            WHERE (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)
            """,
            (me_id, tid, tid, me_id),
        ).fetchone()
        if existing:
            st = existing["status"]
            if st == "accepted":
                raise HTTPException(status_code=409, detail="已是好友")
            if st == "pending":
                raise HTTPException(status_code=409, detail="已有待处理请求")
            if st == "rejected":
                conn.execute("DELETE FROM friend_requests WHERE id = ?", (existing["id"],))

        conn.execute(
            """
            INSERT INTO friend_requests (from_user_id, to_user_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (me_id, tid, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    await manager.send_to_user(
        tid,
        {
            "type": "friend_request",
            "from_user_id": me_id,
            "from_username": me_username,
            "timestamp": now_iso(),
        },
    )
    return {"ok": True, "message": "好友请求已发送"}


@app.post("/friends/accept")
async def friend_accept(
    body: FriendAcceptBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    me_username = str(decode_token(parse_auth_token(authorization))["username"])
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT id FROM friend_requests
            WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'
            """,
            (body.from_user_id, me_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="没有待处理的好友请求")
        conn.execute(
            "UPDATE friend_requests SET status = 'accepted' WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    await manager.send_to_user(
        body.from_user_id,
        {
            "type": "friend_accepted",
            "user_id": me_id,
            "username": me_username,
            "timestamp": now_iso(),
        },
    )
    return {"ok": True}


@app.get("/friends")
def friends_list(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.username
            FROM friend_requests fr
            JOIN users u ON (
                (fr.from_user_id = ? AND u.id = fr.to_user_id)
                OR (fr.to_user_id = ? AND u.id = fr.from_user_id)
            )
            WHERE fr.status = 'accepted' AND u.id != ?
            """,
            (me_id, me_id, me_id),
        ).fetchall()
        friends = [{"user_id": int(r["user_id"]), "username": r["username"]} for r in rows]
    finally:
        conn.close()
    return {"friends": friends}


@app.get("/friends/pending")
def friends_pending(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT fr.from_user_id AS user_id, u.username
            FROM friend_requests fr
            JOIN users u ON u.id = fr.from_user_id
            WHERE fr.to_user_id = ? AND fr.status = 'pending'
            """,
            (me_id,),
        ).fetchall()
        pending = [{"user_id": int(r["user_id"]), "username": r["username"]} for r in rows]
    finally:
        conn.close()
    return {"pending": pending}


@app.post("/groups")
def create_group(
    body: GroupCreateBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO groups (name, owner_id, created_at) VALUES (?, ?, ?)",
            (body.name.strip(), me_id, now_iso()),
        )
        gid = cur.lastrowid
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, joined_at) VALUES (?, ?, ?)",
            (gid, me_id, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"group_id": gid, "name": body.name.strip()}


@app.post("/groups/{group_id}/members")
def invite_group_member(
    group_id: int,
    body: GroupInviteBody,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        g = conn.execute(
            "SELECT id, owner_id FROM groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if not g:
            raise HTTPException(status_code=404, detail="群组不存在")
        if int(g["owner_id"]) != me_id:
            raise HTTPException(status_code=403, detail="仅群主可邀请成员")

        u = user_by_username(conn, body.username)
        if not u:
            raise HTTPException(status_code=404, detail="用户不存在")
        uid = int(u["id"])
        exists = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, uid),
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="已在群内")
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, joined_at) VALUES (?, ?, ?)",
            (group_id, uid, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/groups/my")
def my_groups(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    me_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT g.id, g.name, g.owner_id
            FROM groups g
            JOIN group_members gm ON gm.group_id = g.id AND gm.user_id = ?
            """,
            (me_id,),
        ).fetchall()
        groups = [
            {"group_id": int(r["id"]), "name": r["name"], "owner_id": int(r["owner_id"])}
            for r in rows
        ]
    finally:
        conn.close()
    return {"groups": groups}


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
    me_id = user_info["user_id"]
    client_id = await manager.connect(websocket, user_info)

    await manager.broadcast_lobby(
        {
            "type": "system",
            "scope": "lobby",
            "sender": "系统",
            "content": f'{user_info["username"]} (ID:{me_id}) 进入了世界大厅',
            "timestamp": now_iso(),
        }
    )
    await manager.broadcast_online_snapshot()

    try:
        while True:
            raw_data = await websocket.receive_text()
            raw = raw_data.strip()
            if not raw:
                continue

            action = "lobby"
            text = raw
            to_user_id: int | None = None
            group_id: int | None = None

            if raw.startswith("{"):
                try:
                    obj = json.loads(raw)
                    action = str(obj.get("action", "lobby")).lower()
                    text = str(obj.get("text", "")).strip()
                    if obj.get("to_user_id") is not None:
                        to_user_id = int(obj["to_user_id"])
                    if obj.get("group_id") is not None:
                        group_id = int(obj["group_id"])
                except (json.JSONDecodeError, ValueError, TypeError):
                    text = raw

            if not text:
                continue

            ts = now_iso()
            conn = get_db()

            if action == "lobby" or action == "world":
                await manager.broadcast_lobby(
                    {
                        "type": "chat",
                        "scope": "lobby",
                        "sender": user_info["username"],
                        "sender_id": me_id,
                        "content": text,
                        "timestamp": ts,
                    }
                )
                continue

            if action == "dm":
                if to_user_id is None:
                    continue
                conn_dm = get_db()
                try:
                    if not are_friends(conn_dm, me_id, to_user_id):
                        await manager.send_to_user(
                            me_id,
                            {
                                "type": "system",
                                "scope": "dm",
                                "sender": "系统",
                                "content": "对方不是好友，无法私聊",
                                "timestamp": ts,
                            },
                        )
                        continue
                finally:
                    conn_dm.close()

                msg = {
                    "type": "chat",
                    "scope": "dm",
                    "sender": user_info["username"],
                    "sender_id": me_id,
                    "peer_id": to_user_id,
                    "content": text,
                    "timestamp": ts,
                }
                await manager.send_to_user(me_id, msg)
                await manager.send_to_user(to_user_id, {**msg, "peer_id": me_id})
                continue

            if action == "group":
                if group_id is None:
                    continue
                conn_g = get_db()
                try:
                    members = group_member_ids(conn_g, group_id)
                finally:
                    conn_g.close()

                if me_id not in members:
                    await manager.send_to_user(
                        me_id,
                        {
                            "type": "system",
                            "scope": "group",
                            "group_id": group_id,
                            "sender": "系统",
                            "content": "你不在该群组中",
                            "timestamp": ts,
                        },
                    )
                    continue

                await manager.broadcast_group(
                    members,
                    {
                        "type": "chat",
                        "scope": "group",
                        "group_id": group_id,
                        "sender": user_info["username"],
                        "sender_id": me_id,
                        "content": text,
                        "timestamp": ts,
                    },
                )
                continue

            await manager.broadcast_lobby(
                {
                    "type": "chat",
                    "scope": "lobby",
                    "sender": user_info["username"],
                    "sender_id": me_id,
                    "content": text,
                    "timestamp": ts,
                }
            )
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast_lobby(
            {
                "type": "system",
                "scope": "lobby",
                "sender": "系统",
                "content": f'{user_info["username"]} (ID:{me_id}) 离开了世界大厅',
                "timestamp": now_iso(),
            }
        )
        await manager.broadcast_online_snapshot()
