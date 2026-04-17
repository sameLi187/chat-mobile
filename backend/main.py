from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
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


def resolve_db_path() -> Path:
    """SQLite 文件路径。线上请设置 DATABASE_PATH 指向持久卷，避免重部署丢库。"""
    raw = (os.getenv("DATABASE_PATH") or os.getenv("SQLITE_DB_PATH") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return (BASE_DIR / "chat.db").resolve()


DB_PATH = resolve_db_path()
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


class EquipRequest(BaseModel):
    inventory_id: int = Field(ge=1)


class DungeonChallengeRequest(BaseModel):
    dungeon_id: str = Field(min_length=1, max_length=24)


class MonsterFightRequest(BaseModel):
    map_id: str = Field(min_length=1, max_length=24)
    monster_type: str = Field(min_length=1, max_length=24)


class DungeonSettleRequest(BaseModel):
    dungeon_id: str = Field(min_length=1, max_length=24)
    cleared: bool = True


class GachaDrawRequest(BaseModel):
    pool: str = Field(min_length=1, max_length=24)  # normal / advanced
    count: int = Field(ge=1, le=10)


class SellRequest(BaseModel):
    inventory_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=99)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_progress (
                user_id INTEGER PRIMARY KEY,
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_items (
                item_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slot TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'equipment',
                quality TEXT NOT NULL,
                level_required INTEGER NOT NULL,
                power INTEGER NOT NULL,
                hp INTEGER NOT NULL DEFAULT 0,
                attack INTEGER NOT NULL DEFAULT 0,
                defense INTEGER NOT NULL DEFAULT 0,
                dodge REAL NOT NULL DEFAULT 0,
                crit REAL NOT NULL DEFAULT 0,
                block REAL NOT NULL DEFAULT 0,
                lifesteal REAL NOT NULL DEFAULT 0,
                set_key TEXT,
                set_level INTEGER,
                bonus_trait TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS set_bonuses (
                set_key TEXT NOT NULL,
                tier INTEGER NOT NULL,
                bonus_desc TEXT NOT NULL,
                PRIMARY KEY (set_key, tier)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dungeons_game (
                dungeon_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                recommended_level INTEGER NOT NULL,
                difficulty_tier INTEGER NOT NULL,
                min_set_level INTEGER NOT NULL,
                min_set_pieces INTEGER NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                equipped INTEGER NOT NULL DEFAULT 0,
                quantity INTEGER NOT NULL DEFAULT 1,
                affix_json TEXT NOT NULL DEFAULT '[]',
                bonus_hp INTEGER NOT NULL DEFAULT 0,
                bonus_attack INTEGER NOT NULL DEFAULT 0,
                bonus_defense INTEGER NOT NULL DEFAULT 0,
                bonus_dodge REAL NOT NULL DEFAULT 0,
                bonus_crit REAL NOT NULL DEFAULT 0,
                bonus_block REAL NOT NULL DEFAULT 0,
                bonus_lifesteal REAL NOT NULL DEFAULT 0,
                bonus_crit_damage REAL NOT NULL DEFAULT 0,
                bonus_freeze REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (item_id) REFERENCES game_items(item_id)
            )
            """
        )
        # lightweight migration for existing DB
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(game_items)").fetchall()}
        if "category" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN category TEXT NOT NULL DEFAULT 'equipment'")
        if "hp" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN hp INTEGER NOT NULL DEFAULT 0")
        if "attack" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN attack INTEGER NOT NULL DEFAULT 0")
        if "defense" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN defense INTEGER NOT NULL DEFAULT 0")
        if "dodge" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN dodge REAL NOT NULL DEFAULT 0")
        if "crit" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN crit REAL NOT NULL DEFAULT 0")
        if "block" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN block REAL NOT NULL DEFAULT 0")
        if "lifesteal" not in columns:
            conn.execute("ALTER TABLE game_items ADD COLUMN lifesteal REAL NOT NULL DEFAULT 0")
        conn.execute("UPDATE game_items SET category = 'equipment' WHERE category IS NULL OR category = ''")
        inv_columns = {r["name"] for r in conn.execute("PRAGMA table_info(player_inventory)").fetchall()}
        if "affix_json" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN affix_json TEXT NOT NULL DEFAULT '[]'")
        if "bonus_hp" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_hp INTEGER NOT NULL DEFAULT 0")
        if "bonus_attack" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_attack INTEGER NOT NULL DEFAULT 0")
        if "bonus_defense" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_defense INTEGER NOT NULL DEFAULT 0")
        if "bonus_dodge" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_dodge REAL NOT NULL DEFAULT 0")
        if "bonus_crit" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_crit REAL NOT NULL DEFAULT 0")
        if "bonus_block" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_block REAL NOT NULL DEFAULT 0")
        if "bonus_lifesteal" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_lifesteal REAL NOT NULL DEFAULT 0")
        if "bonus_crit_damage" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_crit_damage REAL NOT NULL DEFAULT 0")
        if "bonus_freeze" not in inv_columns:
            conn.execute("ALTER TABLE player_inventory ADD COLUMN bonus_freeze REAL NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_wallet (
                user_id INTEGER PRIMARY KEY,
                gold INTEGER NOT NULL DEFAULT 0,
                normal_ticket INTEGER NOT NULL DEFAULT 0,
                advanced_ticket INTEGER NOT NULL DEFAULT 0,
                enhance_stone INTEGER NOT NULL DEFAULT 0,
                reroll_stone INTEGER NOT NULL DEFAULT 0,
                epic_shard INTEGER NOT NULL DEFAULT 0,
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
print(f"[db] sqlite path: {DB_PATH}", flush=True)
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


def compute_item_stats(
    slot: str,
    quality: str,
    level_required: int,
    set_key: str | None = None,
) -> dict[str, float]:
    quality_scale = {
        "普通": 1.00,
        "优秀": 1.18,
        "精良": 1.40,
        "史诗": 1.75,
        "传奇": 2.05,
        "神话": 2.40,
    }
    lv_scale = 1 + (level_required - 1) * 0.055
    q_scale = quality_scale.get(quality, 1.0)
    base = {
        "weapon": {"attack": 20, "hp": 0, "defense": 0, "dodge": 0.0, "crit": 0.02, "block": 0.0, "lifesteal": 0.0},
        "helmet": {"attack": 0, "hp": 30, "defense": 12, "dodge": 0.01, "crit": 0.0, "block": 0.02, "lifesteal": 0.0},
        "chest": {"attack": 0, "hp": 60, "defense": 24, "dodge": 0.0, "crit": 0.0, "block": 0.03, "lifesteal": 0.0},
        "gloves": {"attack": 5, "hp": 12, "defense": 10, "dodge": 0.02, "crit": 0.03, "block": 0.0, "lifesteal": 0.0},
        "pants": {"attack": 0, "hp": 45, "defense": 18, "dodge": 0.01, "crit": 0.0, "block": 0.02, "lifesteal": 0.0},
        "boots": {"attack": 0, "hp": 20, "defense": 9, "dodge": 0.04, "crit": 0.0, "block": 0.0, "lifesteal": 0.0},
        "bag": {"attack": 0, "hp": 0, "defense": 0, "dodge": 0.0, "crit": 0.0, "block": 0.0, "lifesteal": 0.0},
    }[slot]
    stats = {
        "attack": int(round(base["attack"] * lv_scale * q_scale)),
        "hp": int(round(base["hp"] * lv_scale * q_scale)),
        "defense": int(round(base["defense"] * lv_scale * q_scale)),
        "dodge": round(base["dodge"] * q_scale, 4),
        "crit": round(base["crit"] * q_scale, 4),
        "block": round(base["block"] * q_scale, 4),
        "lifesteal": round(base["lifesteal"] * q_scale, 4),
    }
    if set_key:
        if "arc" in set_key:
            stats["crit"] = round(stats["crit"] + 0.01, 4)
            stats["dodge"] = round(stats["dodge"] + 0.01, 4)
        elif "hunt" in set_key:
            stats["attack"] += max(6, int(level_required * 0.4))
            stats["crit"] = round(stats["crit"] + 0.03, 4)
        elif "pal" in set_key:
            stats["hp"] += max(20, int(level_required * 1.8))
            stats["block"] = round(stats["block"] + 0.04, 4)
        elif "iron" in set_key:
            stats["defense"] += max(6, int(level_required * 0.6))
            stats["hp"] += max(10, int(level_required * 1.1))
    if quality == "史诗":
        stats["lifesteal"] = round(stats["lifesteal"] + 0.01, 4)
    return stats


def build_combat_snapshot(level: int, scale: float) -> dict[str, Any]:
    return {
        "hp": int((150 + level * 42) * scale),
        "attack": int((18 + level * 5) * scale),
        "defense": int((10 + level * 3.2) * max(1.0, scale * 0.92)),
        "dodge": round(min(0.04 + scale * 0.015, 0.28), 4),
        "crit": round(min(0.03 + scale * 0.02, 0.3), 4),
        "block": round(min(0.02 + scale * 0.01, 0.2), 4),
    }


def calculate_combat_score(stats: dict[str, Any]) -> float:
    return (
        float(stats["hp"]) * 0.18
        + float(stats["attack"]) * 2.7
        + float(stats["defense"]) * 1.9
        + float(stats["dodge"]) * 260
        + float(stats["crit"]) * 230
        + float(stats["block"]) * 220
        + float(stats.get("lifesteal", 0)) * 320
        + float(stats.get("crit_damage", 0)) * 170
        + float(stats.get("freeze", 0)) * 160
    )


def roll_weapon_affixes(item: dict[str, Any]) -> dict[str, Any]:
    if str(item.get("quality")) != "史诗" or str(item.get("slot")) != "weapon":
        return {
            "affixes": [],
            "bonus_hp": 0,
            "bonus_attack": 0,
            "bonus_defense": 0,
            "bonus_dodge": 0.0,
            "bonus_crit": 0.0,
            "bonus_block": 0.0,
            "bonus_lifesteal": 0.0,
            "bonus_crit_damage": 0.0,
            "bonus_freeze": 0.0,
        }

    level_required = int(item.get("level_required") or 1)
    pool = [
        {
            "key": "crit_damage",
            "label": "暴伤",
            "roll": lambda: round(0.12 + level_required * 0.003 + random.random() * 0.08, 4),
            "apply": lambda v, out: out.__setitem__("bonus_crit_damage", out["bonus_crit_damage"] + v),
            "fmt": lambda v: f"暴伤+{round(v * 100, 1)}%",
        },
        {
            "key": "freeze",
            "label": "冰冻",
            "roll": lambda: round(0.05 + level_required * 0.0015 + random.random() * 0.05, 4),
            "apply": lambda v, out: out.__setitem__("bonus_freeze", out["bonus_freeze"] + v),
            "fmt": lambda v: f"冰冻几率+{round(v * 100, 1)}%",
        },
        {
            "key": "block",
            "label": "格挡",
            "roll": lambda: round(0.04 + level_required * 0.0018 + random.random() * 0.05, 4),
            "apply": lambda v, out: out.__setitem__("bonus_block", out["bonus_block"] + v),
            "fmt": lambda v: f"格挡+{round(v * 100, 1)}%",
        },
        {
            "key": "lifesteal",
            "label": "吸血",
            "roll": lambda: round(0.03 + level_required * 0.0015 + random.random() * 0.04, 4),
            "apply": lambda v, out: out.__setitem__("bonus_lifesteal", out["bonus_lifesteal"] + v),
            "fmt": lambda v: f"吸血+{round(v * 100, 1)}%",
        },
        {
            "key": "attack",
            "label": "锋锐",
            "roll": lambda: int(8 + level_required * 0.9 + random.randint(0, 12)),
            "apply": lambda v, out: out.__setitem__("bonus_attack", out["bonus_attack"] + int(v)),
            "fmt": lambda v: f"攻击+{int(v)}",
        },
        {
            "key": "crit",
            "label": "致命",
            "roll": lambda: round(0.03 + level_required * 0.0015 + random.random() * 0.04, 4),
            "apply": lambda v, out: out.__setitem__("bonus_crit", out["bonus_crit"] + v),
            "fmt": lambda v: f"暴击+{round(v * 100, 1)}%",
        },
    ]
    pick_count = random.choices([1, 2, 3], weights=[25, 50, 25], k=1)[0]
    chosen = random.sample(pool, k=pick_count)
    result = {
        "affixes": [],
        "bonus_hp": 0,
        "bonus_attack": 0,
        "bonus_defense": 0,
        "bonus_dodge": 0.0,
        "bonus_crit": 0.0,
        "bonus_block": 0.0,
        "bonus_lifesteal": 0.0,
        "bonus_crit_damage": 0.0,
        "bonus_freeze": 0.0,
    }
    for affix in chosen:
        value = affix["roll"]()
        affix["apply"](value, result)
        result["affixes"].append(
            {"key": affix["key"], "label": affix["label"], "value": value, "text": affix["fmt"](value)}
        )
    return result


def seed_game_content() -> None:
    conn = get_db()
    try:
        has_items = conn.execute("SELECT 1 FROM game_items LIMIT 1").fetchone()
        if not has_items:
            slots = [("weapon", 20), ("helmet", 12), ("chest", 24), ("gloves", 10), ("pants", 18), ("boots", 9)]
            slot_cn = {
                "weapon": "武器",
                "helmet": "头盔",
                "chest": "胸甲",
                "gloves": "手套",
                "pants": "裤子",
                "boots": "鞋子",
            }
            quality_scale = {"普通": 1.00, "优秀": 1.18, "精良": 1.40}
            levels = [1, 10, 20, 30, 40, 50]
            for lv in levels:
                lv_scale = 1 + (lv - 1) * 0.055
                for slot, base in slots:
                    for quality, q_scale in quality_scale.items():
                        power = int(round(base * lv_scale * q_scale))
                        stats = compute_item_stats(slot, quality, lv)
                        item_id = f"BASE-{slot.upper()}-{lv}-{quality}"
                        name = f"{quality}{slot_cn[slot]}·Lv{lv}"
                        conn.execute(
                            """
                            INSERT INTO game_items (item_id, name, slot, category, quality, level_required, power, hp, attack, defense, dodge, crit, block, lifesteal, set_key, set_level, bonus_trait)
                            VALUES (?, ?, ?, 'equipment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, '')
                            """,
                            (
                                item_id,
                                name,
                                slot,
                                quality,
                                lv,
                                power,
                                stats["hp"],
                                stats["attack"],
                                stats["defense"],
                                stats["dodge"],
                                stats["crit"],
                                stats["block"],
                                stats["lifesteal"],
                            ),
                        )

            epic_sets = {
                "set30_iron": ("铁壁战痕", 30, ("近战伤害+8%，减伤+6%", "连击3层触发震荡波", "终结技后4秒攻防+12%"), "均衡"),
                "set30_hunt": ("猎风断星", 30, ("暴击率+8%", "第3次命中追加穿刺", "每8秒下一次单体必暴击"), "单点爆发"),
                "set30_arc": ("霜火共鸣", 30, ("范围半径+12%", "AOE命中3目标回能", "AOE追加二次爆裂"), "范围AOE"),
                "set30_pal": ("圣辉庇护", 30, ("生命+10%", "低血触发护盾", "治疗溢出转护盾"), "坦度回复"),
                "set40_iron": ("不屈征伐", 40, ("近战伤害+12%", "震荡波强化", "终结技后6秒攻防+18%"), "均衡"),
                "set40_hunt": ("寂灭猎神", 40, ("暴击率+12%", "穿刺可弹射1目标", "第3次单体必暴击+暴伤"), "单点爆发"),
                "set40_arc": ("万象崩界", 40, ("范围+18%", "AOE触发连锁闪电", "AOE二次爆裂45%"), "范围AOE"),
                "set40_pal": ("誓约圣裁", 40, ("生命+15%", "护盾存在时持续回复", "治疗溢出转护盾并分担伤害"), "坦度回复"),
                "set50_iron": ("深渊统御", 50, ("近战伤害+16%", "连击震荡附破甲", "终结技后8秒攻防+25%"), "均衡"),
                "set50_hunt": ("终夜裁决", 50, ("暴击率+15%", "命中Boss叠猎印", "消耗猎印高倍率斩杀"), "单点爆发"),
                "set50_arc": ("虚空洪流", 50, ("范围+22%", "连锁额外弹射2次", "命中5目标触发全屏小爆"), "范围AOE"),
                "set50_pal": ("光耀圣域", 50, ("生命+20%", "护盾破裂回复已损生命", "开启圣域全队减伤"), "坦度回复"),
            }
            epic_slots = ["weapon", "helmet", "chest", "gloves", "pants", "boots"]
            for set_key, (set_name, set_level, bonuses, trait) in epic_sets.items():
                for tier, bonus_desc in ((2, bonuses[0]), (4, bonuses[1]), (6, bonuses[2])):
                    conn.execute(
                        "INSERT INTO set_bonuses (set_key, tier, bonus_desc) VALUES (?, ?, ?)",
                        (set_key, tier, bonus_desc),
                    )
                for slot in epic_slots:
                    power = int(round((22 if slot == "weapon" else 14) * (1 + (set_level - 1) * 0.055) * 1.75))
                    stats = compute_item_stats(slot, "史诗", set_level, set_key)
                    item_id = f"{set_key.upper()}-{slot.upper()}"
                    name = f"{set_name}{slot_cn[slot]}·Lv{set_level}"
                    conn.execute(
                        """
                        INSERT INTO game_items (item_id, name, slot, category, quality, level_required, power, hp, attack, defense, dodge, crit, block, lifesteal, set_key, set_level, bonus_trait)
                        VALUES (?, ?, ?, 'equipment', '史诗', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item_id,
                            name,
                            slot,
                            set_level,
                            power,
                            stats["hp"],
                            stats["attack"],
                            stats["defense"],
                            stats["dodge"],
                            stats["crit"],
                            stats["block"],
                            stats["lifesteal"],
                            set_key,
                            set_level,
                            trait,
                        ),
                    )

        consumables = [
            ("ITEM-POTION-SMALL", "小型生命药剂", "consumable", 1, 25),
            ("ITEM-POTION-MEDIUM", "中型生命药剂", "consumable", 20, 60),
            ("ITEM-ELIXIR-AOE", "范围增幅药剂", "consumable", 30, 90),
            ("ITEM-BOSS-SCROLL", "首领挑战卷轴", "consumable", 40, 120),
        ]
        for item_id, name, category, level_required, power in consumables:
            exists = conn.execute("SELECT 1 FROM game_items WHERE item_id = ?", (item_id,)).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO game_items (item_id, name, slot, category, quality, level_required, power, hp, attack, defense, dodge, crit, block, lifesteal, set_key, set_level, bonus_trait)
                    VALUES (?, ?, 'bag', ?, '优秀', ?, ?, 0, 0, 0, 0, 0, 0, 0, NULL, NULL, '消耗型道具')
                    """,
                    (item_id, name, category, level_required, power),
                )
        rows = conn.execute(
            "SELECT item_id, slot, quality, level_required, set_key FROM game_items"
        ).fetchall()
        for r in rows:
            stats = compute_item_stats(r["slot"], r["quality"], int(r["level_required"]), r["set_key"])
            conn.execute(
                """
                UPDATE game_items
                SET hp = ?, attack = ?, defense = ?, dodge = ?, crit = ?, block = ?, lifesteal = ?
                WHERE item_id = ?
                """,
                (
                    stats["hp"],
                    stats["attack"],
                    stats["defense"],
                    stats["dodge"],
                    stats["crit"],
                    stats["block"],
                    stats["lifesteal"],
                    r["item_id"],
                ),
            )

        has_dungeon = conn.execute("SELECT 1 FROM dungeons_game LIMIT 1").fetchone()
        if not has_dungeon:
            dungeons = [
                ("DUN30", "黑岩熔炉", 30, 30, 20, 4, "30级史诗副本，建议20级精良以上"),
                ("DUN40", "霜骨王庭", 40, 40, 30, 6, "40级史诗副本，要求30级史诗全套"),
                ("DUN50", "深渊裂隙", 50, 50, 40, 6, "50级终局副本，建议40级史诗全套"),
            ]
            for row in dungeons:
                conn.execute(
                    """
                    INSERT INTO dungeons_game
                    (dungeon_id, name, recommended_level, difficulty_tier, min_set_level, min_set_pieces, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
        conn.commit()
    finally:
        conn.close()


seed_game_content()


def init_player_game_state(user_id: int) -> None:
    conn = get_db()
    try:
        exists = conn.execute(
            "SELECT 1 FROM player_progress WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO player_progress (user_id, level, exp, created_at) VALUES (?, 1, 0, ?)",
                (user_id, now_iso()),
            )
            conn.execute(
                """
                INSERT INTO player_wallet
                (user_id, gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard)
                VALUES (?, 200, 1, 0, 10, 6, 0)
                """,
                (user_id,),
            )
            starter_ids = [
                "BASE-WEAPON-1-普通",
                "BASE-HELMET-1-普通",
                "BASE-CHEST-1-普通",
                "BASE-GLOVES-1-普通",
                "BASE-PANTS-1-普通",
                "BASE-BOOTS-1-普通",
            ]
            for item_id in starter_ids:
                conn.execute(
                    """
                    INSERT INTO player_inventory (user_id, item_id, equipped, quantity, created_at)
                    VALUES (?, ?, 1, 1, ?)
                    """,
                    (user_id, item_id, now_iso()),
                )
        conn.commit()
    finally:
        conn.close()


def level_need_exp(level: int) -> int:
    return 100 + (level - 1) * 35


def add_player_exp(user_id: int, gained_exp: int) -> dict[str, int]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT level, exp FROM player_progress WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            init_player_game_state(user_id)
            row = conn.execute(
                "SELECT level, exp FROM player_progress WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        level = int(row["level"])
        exp = int(row["exp"]) + max(0, gained_exp)
        while level < 50:
            need = level_need_exp(level)
            if exp < need:
                break
            exp -= need
            level += 1
        if level >= 50:
            level = 50
            exp = 0
        conn.execute(
            "UPDATE player_progress SET level = ?, exp = ? WHERE user_id = ?",
            (level, exp, user_id),
        )
        conn.commit()
        return {"level": level, "exp": exp}
    finally:
        conn.close()


def add_wallet_values(
    user_id: int,
    gold: int = 0,
    normal_ticket: int = 0,
    advanced_ticket: int = 0,
    enhance_stone: int = 0,
    reroll_stone: int = 0,
    epic_shard: int = 0,
) -> None:
    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE player_wallet
            SET gold = gold + ?,
                normal_ticket = normal_ticket + ?,
                advanced_ticket = advanced_ticket + ?,
                enhance_stone = enhance_stone + ?,
                reroll_stone = reroll_stone + ?,
                epic_shard = epic_shard + ?
            WHERE user_id = ?
            """,
            (gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def grant_item(user_id: int, item_id: str, equipped: int = 0, item_data: dict[str, Any] | None = None) -> dict[str, Any]:
    conn = get_db()
    try:
        source_item = item_data or conn.execute(
            "SELECT item_id, name, slot, category, quality, level_required, power FROM game_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        source_dict = dict(source_item) if source_item else {"item_id": item_id}
        affix_roll = roll_weapon_affixes(source_dict)
        conn.execute(
            """
            INSERT INTO player_inventory (
                user_id, item_id, equipped, quantity, affix_json,
                bonus_hp, bonus_attack, bonus_defense, bonus_dodge, bonus_crit, bonus_block,
                bonus_lifesteal, bonus_crit_damage, bonus_freeze, created_at
            )
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                item_id,
                equipped,
                json.dumps(affix_roll["affixes"], ensure_ascii=False),
                affix_roll["bonus_hp"],
                affix_roll["bonus_attack"],
                affix_roll["bonus_defense"],
                affix_roll["bonus_dodge"],
                affix_roll["bonus_crit"],
                affix_roll["bonus_block"],
                affix_roll["bonus_lifesteal"],
                affix_roll["bonus_crit_damage"],
                affix_roll["bonus_freeze"],
                now_iso(),
            ),
        )
        inventory_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        conn.commit()
        return {
            **source_dict,
            "inventory_id": inventory_id,
            "affixes": affix_roll["affixes"],
            "bonus_hp": affix_roll["bonus_hp"],
            "bonus_attack": affix_roll["bonus_attack"],
            "bonus_defense": affix_roll["bonus_defense"],
            "bonus_dodge": affix_roll["bonus_dodge"],
            "bonus_crit": affix_roll["bonus_crit"],
            "bonus_block": affix_roll["bonus_block"],
            "bonus_lifesteal": affix_roll["bonus_lifesteal"],
            "bonus_crit_damage": affix_roll["bonus_crit_damage"],
            "bonus_freeze": affix_roll["bonus_freeze"],
        }
    finally:
        conn.close()


def item_sell_price(item: dict[str, Any]) -> int:
    quality_base = {
        "普通": 12,
        "优秀": 22,
        "精良": 45,
        "史诗": 120,
        "传奇": 260,
        "神话": 500,
    }
    base = quality_base.get(str(item.get("quality")), 10)
    level_part = int(item.get("level_required") or 1) * 2
    power_part = int(item.get("power") or 0) // 3
    category_bonus = 15 if str(item.get("category")) == "consumable" else 0
    affix_bonus = 0
    affixes = item.get("affixes") or []
    if isinstance(affixes, str):
        try:
            affixes = json.loads(affixes)
        except json.JSONDecodeError:
            affixes = []
    affix_bonus += len(affixes) * 25
    affix_bonus += int((float(item.get("bonus_attack") or 0) + float(item.get("bonus_defense") or 0)) * 0.6)
    affix_bonus += int(float(item.get("bonus_crit_damage") or 0) * 120)
    affix_bonus += int(float(item.get("bonus_freeze") or 0) * 90)
    return max(5, base + level_part + power_part + category_bonus + affix_bonus)


def choose_drop_item(target_level: int, source_type: str) -> dict[str, Any] | None:
    quality_weights: dict[str, list[tuple[str, int]]] = {
        "monster_normal": [("普通", 45), ("优秀", 35), ("精良", 18), ("史诗", 2)],
        "monster_elite": [("普通", 20), ("优秀", 35), ("精良", 35), ("史诗", 10)],
        "boss_world": [("普通", 8), ("优秀", 22), ("精良", 50), ("史诗", 20)],
        "boss_dungeon": [("普通", 3), ("优秀", 10), ("精良", 52), ("史诗", 35)],
    }
    weights = quality_weights.get(source_type, quality_weights["monster_normal"])
    qualities = [q for q, _ in weights]
    probs = [w for _, w in weights]
    chosen_quality = random.choices(qualities, weights=probs, k=1)[0]

    conn = get_db()
    try:
        if chosen_quality == "史诗":
            rows = conn.execute(
                """
                SELECT item_id, name, slot, category, quality, level_required, power, set_key, bonus_trait
                FROM game_items
                WHERE quality = '史诗'
                  AND level_required <= ?
                  AND level_required >= ?
                """,
                (target_level, max(30, target_level - 10)),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT item_id, name, slot, category, quality, level_required, power, set_key, bonus_trait
                FROM game_items
                WHERE quality = ?
                  AND level_required <= ?
                """,
                (chosen_quality, target_level),
            ).fetchall()
        if not rows:
            return None
        row = random.choice(rows)
        return dict(row)
    finally:
        conn.close()


def choose_consumable_item(target_level: int) -> dict[str, Any] | None:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT item_id, name, slot, category, quality, level_required, power, set_key, bonus_trait
            FROM game_items
            WHERE category = 'consumable' AND level_required <= ?
            """,
            (target_level,),
        ).fetchall()
        if not rows:
            return None
        return dict(random.choice(rows))
    finally:
        conn.close()


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

    init_player_game_state(user_id)
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

    init_player_game_state(int(row["id"]))
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


def get_player_profile(user_id: int) -> dict[str, Any]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT level, exp FROM player_progress WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            init_player_game_state(user_id)
            row = conn.execute(
                "SELECT level, exp FROM player_progress WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        equipped_rows = conn.execute(
            """
            SELECT pi.id AS inventory_id, pi.affix_json, pi.bonus_hp, pi.bonus_attack, pi.bonus_defense, pi.bonus_dodge, pi.bonus_crit, pi.bonus_block, pi.bonus_lifesteal, pi.bonus_crit_damage, pi.bonus_freeze, gi.item_id, gi.name, gi.slot, gi.category, gi.quality, gi.level_required, gi.power, gi.hp, gi.attack, gi.defense, gi.dodge, gi.crit, gi.block, gi.lifesteal, gi.set_key, gi.set_level, gi.bonus_trait
            FROM player_inventory pi
            JOIN game_items gi ON gi.item_id = pi.item_id
            WHERE pi.user_id = ? AND pi.equipped = 1
            """,
            (user_id,),
        ).fetchall()
        equipped = []
        for r in equipped_rows:
            item = dict(r)
            try:
                item["affixes"] = json.loads(item.get("affix_json") or "[]")
            except json.JSONDecodeError:
                item["affixes"] = []
            equipped.append(item)
        total_power = sum(int(r["power"]) for r in equipped_rows)
        total_stats = {
            "hp": 120 + int(row["level"]) * 18,
            "attack": 12 + int(row["level"]) * 4,
            "defense": 8 + int(row["level"]) * 3,
            "dodge": 0.03,
            "crit": 0.05,
            "block": 0.02,
            "lifesteal": 0.0,
            "crit_damage": 0.5,
            "freeze": 0.0,
        }
        for r in equipped_rows:
            total_stats["hp"] += int(r["hp"] or 0)
            total_stats["attack"] += int(r["attack"] or 0)
            total_stats["defense"] += int(r["defense"] or 0)
            total_stats["dodge"] += float(r["dodge"] or 0)
            total_stats["crit"] += float(r["crit"] or 0)
            total_stats["block"] += float(r["block"] or 0)
            total_stats["lifesteal"] += float(r["lifesteal"] or 0)
            total_stats["hp"] += int(r["bonus_hp"] or 0)
            total_stats["attack"] += int(r["bonus_attack"] or 0)
            total_stats["defense"] += int(r["bonus_defense"] or 0)
            total_stats["dodge"] += float(r["bonus_dodge"] or 0)
            total_stats["crit"] += float(r["bonus_crit"] or 0)
            total_stats["block"] += float(r["bonus_block"] or 0)
            total_stats["lifesteal"] += float(r["bonus_lifesteal"] or 0)
            total_stats["crit_damage"] += float(r["bonus_crit_damage"] or 0)
            total_stats["freeze"] += float(r["bonus_freeze"] or 0)

        set_counts: dict[str, int] = {}
        for r in equipped_rows:
            if r["set_key"]:
                set_counts[r["set_key"]] = set_counts.get(r["set_key"], 0) + 1

        active_bonuses: list[dict[str, Any]] = []
        for set_key, count in set_counts.items():
            tiers = [2, 4, 6]
            for tier in tiers:
                if count >= tier:
                    bonus = conn.execute(
                        "SELECT bonus_desc FROM set_bonuses WHERE set_key = ? AND tier = ?",
                        (set_key, tier),
                    ).fetchone()
                    if bonus:
                        active_bonuses.append(
                            {
                                "set_key": set_key,
                                "tier": tier,
                                "bonus_desc": bonus["bonus_desc"],
                            }
                        )
        for bonus in active_bonuses:
            set_key = str(bonus["set_key"])
            tier = int(bonus["tier"])
            if "arc" in set_key:
                total_stats["attack"] += 8 * tier
                total_stats["crit"] += 0.01 * (tier / 2)
            elif "hunt" in set_key:
                total_stats["attack"] += 10 * tier
                total_stats["crit"] += 0.015 * (tier / 2)
                total_stats["dodge"] += 0.008 * (tier / 2)
            elif "pal" in set_key:
                total_stats["hp"] += 40 * tier
                total_stats["defense"] += 6 * tier
                total_stats["block"] += 0.015 * (tier / 2)
                total_stats["lifesteal"] += 0.005 * (tier / 2)
            elif "iron" in set_key:
                total_stats["hp"] += 24 * tier
                total_stats["attack"] += 7 * tier
                total_stats["defense"] += 7 * tier

        total_stats["dodge"] = round(min(total_stats["dodge"], 0.65), 4)
        total_stats["crit"] = round(min(total_stats["crit"], 0.75), 4)
        total_stats["block"] = round(min(total_stats["block"], 0.70), 4)
        total_stats["lifesteal"] = round(min(total_stats["lifesteal"], 0.25), 4)
        total_stats["crit_damage"] = round(min(total_stats["crit_damage"], 1.5), 4)
        total_stats["freeze"] = round(min(total_stats["freeze"], 0.45), 4)

        wallet_row = conn.execute(
            """
            SELECT gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard
            FROM player_wallet
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        wallet = dict(wallet_row) if wallet_row else {
            "gold": 0,
            "normal_ticket": 0,
            "advanced_ticket": 0,
            "enhance_stone": 0,
            "reroll_stone": 0,
            "epic_shard": 0,
        }

        return {
            "level": int(row["level"]),
            "exp": int(row["exp"]),
            "total_power": total_power,
            "equipped": equipped,
            "total_stats": total_stats,
            "set_counts": set_counts,
            "active_bonuses": active_bonuses,
            "wallet": wallet,
        }
    finally:
        conn.close()


@app.get("/game/bootstrap")
def game_bootstrap(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    get_user_id_from_header(authorization)
    maps = [
        {"map_id": "M01", "name": "雾隐林地", "level_range": "1-12"},
        {"map_id": "M02", "name": "断碑荒原", "level_range": "13-22"},
        {"map_id": "M03", "name": "黑岩峡谷", "level_range": "23-32"},
        {"map_id": "M04", "name": "霜骸墓园", "level_range": "33-42"},
        {"map_id": "M05", "name": "深渊边庭", "level_range": "43-50"},
    ]
    monsters = [
        {"type": "普通怪", "label": "游荡魔群", "hp_scale": 1.0, "atk_scale": 1.0},
        {"type": "精英怪", "label": "异化首目", "hp_scale": 2.4, "atk_scale": 1.5},
        {"type": "地图Boss", "label": "区域领主", "hp_scale": 5.0, "atk_scale": 2.2},
        {"type": "副本Boss", "label": "副本首领", "hp_scale": 10.0, "atk_scale": 2.2},
    ]
    dungeon_encounters = {
        "DUN30": {"trash": "灰烬铸奴", "elite": "熔链监工", "boss": "熔炉之心·格罗姆"},
        "DUN40": {"trash": "霜庭遗臣", "elite": "寒冠行刑者", "boss": "霜王遗骸·维尔萨"},
        "DUN50": {"trash": "裂隙吞徒", "elite": "深渊司判", "boss": "裂界魔君·阿扎克"},
    }
    conn = get_db()
    try:
        dungeons = [
            dict(r)
            for r in conn.execute(
                "SELECT dungeon_id, name, recommended_level, difficulty_tier, min_set_level, min_set_pieces, description FROM dungeons_game ORDER BY recommended_level"
            ).fetchall()
        ]
    finally:
        conn.close()
    return {
        "quality_rules": {
            "tiers": ["普通", "优秀", "精良", "史诗", "传奇", "神话"],
            "max_quality_pre_50": "史诗",
        },
        "maps": maps,
        "monsters": monsters,
        "dungeons": dungeons,
        "dungeon_encounters": dungeon_encounters,
    }


@app.get("/game/profile")
def game_profile(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    return {"profile": get_player_profile(user_id)}


@app.get("/game/inventory")
def game_inventory(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT pi.id AS inventory_id, pi.equipped, pi.quantity, pi.affix_json, pi.bonus_hp, pi.bonus_attack, pi.bonus_defense, pi.bonus_dodge, pi.bonus_crit, pi.bonus_block, pi.bonus_lifesteal, pi.bonus_crit_damage, pi.bonus_freeze, gi.item_id, gi.name, gi.slot, gi.category, gi.quality, gi.level_required, gi.power, gi.hp, gi.attack, gi.defense, gi.dodge, gi.crit, gi.block, gi.lifesteal, gi.set_key, gi.set_level, gi.bonus_trait
            FROM player_inventory pi
            JOIN game_items gi ON gi.item_id = pi.item_id
            WHERE pi.user_id = ?
            ORDER BY gi.level_required, gi.quality
            """,
            (user_id,),
        ).fetchall()
        inventory = []
        for r in rows:
            item = dict(r)
            try:
                item["affixes"] = json.loads(item.get("affix_json") or "[]")
            except json.JSONDecodeError:
                item["affixes"] = []
            inventory.append(item)
    finally:
        conn.close()
    return {"inventory": inventory}


@app.post("/game/equip")
def game_equip(
    body: EquipRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    profile = get_player_profile(user_id)
    conn = get_db()
    try:
        item = conn.execute(
            """
            SELECT pi.id AS inventory_id, gi.slot, gi.level_required
            FROM player_inventory pi
            JOIN game_items gi ON gi.item_id = pi.item_id
            WHERE pi.id = ? AND pi.user_id = ?
            """,
            (body.inventory_id, user_id),
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="背包物品不存在")
        if profile["level"] < int(item["level_required"]):
            raise HTTPException(status_code=400, detail="等级不足，无法装备")

        conn.execute(
            """
            UPDATE player_inventory
            SET equipped = 0
            WHERE user_id = ?
              AND item_id IN (SELECT item_id FROM game_items WHERE slot = ?)
            """,
            (user_id, item["slot"]),
        )
        conn.execute(
            "UPDATE player_inventory SET equipped = 1 WHERE id = ? AND user_id = ?",
            (body.inventory_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"ok": True, "profile": get_player_profile(user_id)}


@app.post("/game/sell")
def game_sell(
    body: SellRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT pi.id AS inventory_id, pi.quantity, pi.equipped, pi.affix_json, pi.bonus_attack, pi.bonus_defense, pi.bonus_crit_damage, pi.bonus_freeze, gi.item_id, gi.name, gi.category, gi.quality, gi.level_required, gi.power
            FROM player_inventory pi
            JOIN game_items gi ON gi.item_id = pi.item_id
            WHERE pi.id = ? AND pi.user_id = ?
            """,
            (body.inventory_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="背包物品不存在")
        if int(row["equipped"]) == 1:
            raise HTTPException(status_code=400, detail="已穿戴物品不能出售")
        if body.quantity > int(row["quantity"]):
            raise HTTPException(status_code=400, detail="出售数量超过持有数量")

        item = dict(row)
        try:
            item["affixes"] = json.loads(item.get("affix_json") or "[]")
        except json.JSONDecodeError:
            item["affixes"] = []
        price_each = item_sell_price(item)
        total_price = price_each * body.quantity
        remain = int(row["quantity"]) - body.quantity
        if remain <= 0:
            conn.execute("DELETE FROM player_inventory WHERE id = ? AND user_id = ?", (body.inventory_id, user_id))
        else:
            conn.execute(
                "UPDATE player_inventory SET quantity = ? WHERE id = ? AND user_id = ?",
                (remain, body.inventory_id, user_id),
            )
        conn.execute("UPDATE player_wallet SET gold = gold + ? WHERE user_id = ?", (total_price, user_id))
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "sold": {
            "inventory_id": body.inventory_id,
            "item_id": item["item_id"],
            "name": item["name"],
            "quantity": body.quantity,
            "price_each": price_each,
            "total_price": total_price,
        },
        "profile": get_player_profile(user_id),
    }


@app.post("/game/dungeon/challenge")
def game_dungeon_challenge(
    body: DungeonChallengeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    profile = get_player_profile(user_id)
    conn = get_db()
    try:
        dungeon = conn.execute(
            """
            SELECT dungeon_id, name, recommended_level, difficulty_tier, min_set_level, min_set_pieces, description
            FROM dungeons_game
            WHERE dungeon_id = ?
            """,
            (body.dungeon_id,),
        ).fetchone()
    finally:
        conn.close()
    if not dungeon:
        raise HTTPException(status_code=404, detail="副本不存在")

    if profile["level"] < int(dungeon["recommended_level"]):
        return {
            "ok": False,
            "reason": f"等级不足：需要 Lv{dungeon['recommended_level']}",
            "dungeon": dict(dungeon),
            "profile": profile,
        }

    min_set_level = int(dungeon["min_set_level"])
    min_set_pieces = int(dungeon["min_set_pieces"])
    stat_requirements = {
        "DUN30": {"hp": 900, "attack": 180, "defense": 120},
        "DUN40": {"hp": 1800, "attack": 340, "defense": 240},
        "DUN50": {"hp": 3000, "attack": 520, "defense": 360},
    }
    count_eligible = 0
    for eq in profile["equipped"]:
        if eq.get("quality") == "史诗" and (eq.get("set_level") or 0) >= min_set_level:
            count_eligible += 1

    if count_eligible < min_set_pieces:
        return {
            "ok": False,
            "reason": f"装备门槛不足：需要至少 {min_set_pieces} 件 Lv{min_set_level}+ 史诗装备",
            "dungeon": dict(dungeon),
            "profile": profile,
            "eligible_epic_pieces": count_eligible,
        }

    required_stats = stat_requirements.get(body.dungeon_id, {})
    current_stats = profile["total_stats"]
    missing_stats: list[str] = []
    for stat_key, required_value in required_stats.items():
        if float(current_stats.get(stat_key, 0)) < float(required_value):
            cn_name = {"hp": "生命", "attack": "攻击", "defense": "防御"}.get(stat_key, stat_key)
            missing_stats.append(f"{cn_name}<{required_value}")
    if missing_stats:
        return {
            "ok": False,
            "reason": f"属性门槛不足：需要 {' / '.join(missing_stats)}",
            "dungeon": dict(dungeon),
            "profile": profile,
            "required_stats": required_stats,
        }

    return {
        "ok": True,
        "result": "challenge_passed",
        "dungeon": dict(dungeon),
        "profile": profile,
        "required_stats": required_stats,
        "note": "满足挑战门槛，可进入副本战斗流程",
    }


@app.post("/game/fight/monster")
def game_fight_monster(
    body: MonsterFightRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    profile = get_player_profile(user_id)

    map_level_cap = {
        "M01": 12,
        "M02": 22,
        "M03": 32,
        "M04": 42,
        "M05": 50,
    }
    if body.map_id not in map_level_cap:
        raise HTTPException(status_code=404, detail="地图不存在")

    monster_cfg = {
        "普通怪": {"exp": 32, "gold": 24, "power_scale": 1.0, "drop_source": "monster_normal", "ticket": (0.08, 0.0)},
        "精英怪": {"exp": 88, "gold": 70, "power_scale": 2.2, "drop_source": "monster_elite", "ticket": (0.35, 0.05)},
        "地图Boss": {"exp": 210, "gold": 180, "power_scale": 4.8, "drop_source": "boss_world", "ticket": (0.75, 0.20)},
    }
    cfg = monster_cfg.get(body.monster_type)
    if not cfg:
        raise HTTPException(status_code=400, detail="怪物类型错误")

    target_level = min(map_level_cap[body.map_id], 50)
    player_stats = profile["total_stats"]
    monster_stats = build_combat_snapshot(target_level, cfg["power_scale"])
    player_score = calculate_combat_score(player_stats) + len(profile["active_bonuses"]) * 18
    required_score = calculate_combat_score(monster_stats)
    if player_score <= 0:
        win_rate = 0.05
    else:
        ratio = player_score / max(1, required_score)
        win_rate = max(0.03, min(0.95, 0.08 + ratio * 0.52))
    won = random.random() < win_rate

    if won:
        exp_gain = int(cfg["exp"] * (0.85 + random.random() * 0.3))
        gold_gain = int(cfg["gold"] * (0.85 + random.random() * 0.3))
        add_player_exp(user_id, exp_gain)
        add_wallet_values(user_id, gold=gold_gain)

        normal_ticket_gain = 1 if random.random() < cfg["ticket"][0] else 0
        advanced_ticket_gain = 1 if random.random() < cfg["ticket"][1] else 0
        add_wallet_values(user_id, normal_ticket=normal_ticket_gain, advanced_ticket=advanced_ticket_gain)

        dropped_item = choose_drop_item(target_level, cfg["drop_source"])
        if dropped_item:
            dropped_item = grant_item(user_id, dropped_item["item_id"], equipped=0, item_data=dropped_item)
        add_wallet_values(
            user_id,
            enhance_stone=random.randint(1, 3) if body.monster_type != "普通怪" else random.randint(0, 1),
            reroll_stone=random.randint(0, 2) if body.monster_type == "地图Boss" else random.randint(0, 1),
            epic_shard=1 if dropped_item and dropped_item["quality"] == "史诗" else 0,
        )
    else:
        exp_gain = int(cfg["exp"] * 0.25)
        gold_gain = int(cfg["gold"] * 0.2)
        add_player_exp(user_id, exp_gain)
        add_wallet_values(user_id, gold=gold_gain)
        dropped_item = None
        normal_ticket_gain = 0
        advanced_ticket_gain = 0

    return {
        "ok": True,
        "won": won,
        "map_id": body.map_id,
        "monster_type": body.monster_type,
        "player_score": round(player_score, 1),
        "monster_score": round(required_score, 1),
        "monster_stats": monster_stats,
        "win_rate_estimate": round(win_rate, 3),
        "rewards": {
            "exp": exp_gain,
            "gold": gold_gain,
            "normal_ticket": normal_ticket_gain,
            "advanced_ticket": advanced_ticket_gain,
            "item": dropped_item,
        },
        "profile": get_player_profile(user_id),
    }


@app.post("/game/dungeon/settle")
def game_dungeon_settle(
    body: DungeonSettleRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    gate = game_dungeon_challenge(DungeonChallengeRequest(dungeon_id=body.dungeon_id), authorization)
    if not gate["ok"]:
        return {"ok": False, "reason": "未满足副本挑战门槛", "gate": gate}

    dungeon = gate["dungeon"]
    target_level = int(dungeon["recommended_level"])
    is_boss_source = "boss_dungeon"
    profile = get_player_profile(user_id)
    dungeon_scale = {30: 4.8, 40: 7.2, 50: 9.2}.get(target_level, 5.0)
    boss_stats = build_combat_snapshot(target_level, dungeon_scale)
    player_score = calculate_combat_score(profile["total_stats"]) + len(profile["active_bonuses"]) * 24
    boss_score = calculate_combat_score(boss_stats)
    clear_rate = max(0.02, min(0.9, 0.05 + (player_score / max(1, boss_score)) * 0.5))
    if not body.cleared:
        add_player_exp(user_id, int(target_level * 2.2))
        add_wallet_values(user_id, gold=int(target_level * 10))
        return {
            "ok": True,
            "cleared": False,
            "clear_rate_estimate": round(clear_rate, 3),
            "boss_stats": boss_stats,
            "rewards": {"exp": int(target_level * 2.2), "gold": int(target_level * 10)},
            "profile": get_player_profile(user_id),
        }

    if random.random() > clear_rate:
        add_player_exp(user_id, int(target_level * 2.8))
        add_wallet_values(user_id, gold=int(target_level * 12))
        return {
            "ok": True,
            "cleared": False,
            "reason": "属性不足，副本首领将你击退",
            "clear_rate_estimate": round(clear_rate, 3),
            "boss_stats": boss_stats,
            "rewards": {"exp": int(target_level * 2.8), "gold": int(target_level * 12)},
            "profile": get_player_profile(user_id),
        }

    exp_gain = int(target_level * 7.5 + 140)
    gold_gain = int(target_level * 22 + 200)
    add_player_exp(user_id, exp_gain)
    add_wallet_values(
        user_id,
        gold=gold_gain,
        normal_ticket=random.randint(1, 2),
        advanced_ticket=1 if random.random() < (0.20 if target_level < 50 else 0.45) else 0,
        enhance_stone=random.randint(3, 6),
        reroll_stone=random.randint(1, 3),
    )
    item_count = 2 if target_level >= 40 else 1
    drops: list[dict[str, Any]] = []
    for _ in range(item_count):
        item = choose_drop_item(target_level, is_boss_source)
        if item:
            item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
            drops.append(item)
            if item["quality"] == "史诗":
                add_wallet_values(user_id, epic_shard=2)

    return {
        "ok": True,
        "cleared": True,
        "dungeon_id": body.dungeon_id,
        "clear_rate_estimate": round(clear_rate, 3),
        "boss_stats": boss_stats,
        "rewards": {"exp": exp_gain, "gold": gold_gain, "items": drops},
        "profile": get_player_profile(user_id),
    }


@app.post("/game/gacha/draw")
def game_gacha_draw(
    body: GachaDrawRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    pool = body.pool.lower()
    if pool not in {"normal", "advanced"}:
        raise HTTPException(status_code=400, detail="抽奖池仅支持 normal / advanced")

    profile = get_player_profile(user_id)
    wallet = profile["wallet"]
    ticket_field = "normal_ticket" if pool == "normal" else "advanced_ticket"
    cost = body.count
    if int(wallet[ticket_field]) < cost:
        raise HTTPException(status_code=400, detail="抽奖券不足")

    if pool == "normal":
        add_wallet_values(user_id, normal_ticket=-cost)
    else:
        add_wallet_values(user_id, advanced_ticket=-cost)

    rewards: list[dict[str, Any]] = []
    for _ in range(body.count):
        roll = random.random()
        if pool == "normal":
            if roll < 0.50:
                gold = random.randint(120, 260)
                add_wallet_values(user_id, gold=gold)
                rewards.append({"type": "gold", "amount": gold})
            elif roll < 0.78:
                stone = random.randint(1, 3)
                add_wallet_values(user_id, enhance_stone=stone)
                rewards.append({"type": "enhance_stone", "amount": stone})
            elif roll < 0.92:
                stone = random.randint(1, 2)
                add_wallet_values(user_id, reroll_stone=stone)
                rewards.append({"type": "reroll_stone", "amount": stone})
            elif roll < 0.97:
                item = choose_consumable_item(min(50, profile["level"] + 5))
                if item:
                    item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
                    rewards.append({"type": "item", "item": item})
            else:
                item = choose_drop_item(min(50, profile["level"] + 5), "monster_elite")
                if item:
                    item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
                    rewards.append({"type": "item", "item": item})
        else:
            if roll < 0.30:
                gold = random.randint(300, 520)
                add_wallet_values(user_id, gold=gold)
                rewards.append({"type": "gold", "amount": gold})
            elif roll < 0.52:
                shard = random.randint(2, 5)
                add_wallet_values(user_id, epic_shard=shard)
                rewards.append({"type": "epic_shard", "amount": shard})
            elif roll < 0.72:
                stone = random.randint(2, 4)
                add_wallet_values(user_id, reroll_stone=stone)
                rewards.append({"type": "reroll_stone", "amount": stone})
            elif roll < 0.82:
                item = choose_consumable_item(max(30, min(50, profile["level"] + 8)))
                if item:
                    item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
                    rewards.append({"type": "item", "item": item})
            else:
                item = choose_drop_item(max(30, min(50, profile["level"] + 8)), "boss_dungeon")
                if item:
                    item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
                    rewards.append({"type": "item", "item": item})

    return {"ok": True, "pool": pool, "count": body.count, "rewards": rewards, "profile": get_player_profile(user_id)}


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
