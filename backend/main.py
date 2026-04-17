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
CONFIG_ADMIN_USERNAME = os.getenv("CONFIG_ADMIN_USERNAME", "").strip()
CONFIG_ADMIN_KEY = os.getenv("CONFIG_ADMIN_KEY", "").strip()


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
    clear_rate_bonus: float = 0.0
    reward_bonus: float = 0.0
    boss_scale_delta: float = 0.0
    curse_value: float = 0.0
    greed_value: float = 0.0
    current_room_index: int = Field(default=0, ge=0, le=32)
    event_choices: dict[str, str] = Field(default_factory=dict)


class DungeonEngageRequest(BaseModel):
    dungeon_id: str = Field(min_length=1, max_length=24)
    current_room_index: int = Field(default=0, ge=0, le=32)
    event_choices: dict[str, str] = Field(default_factory=dict)


class GachaDrawRequest(BaseModel):
    pool: str = Field(min_length=1, max_length=24)  # normal / advanced
    count: int = Field(ge=1, le=10)


class SellRequest(BaseModel):
    inventory_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=99)


class FightCommitRequest(BaseModel):
    fight_id: str = Field(min_length=8, max_length=64)
    player_hp: int | None = Field(default=None, ge=0)
    monster_hp: int | None = Field(default=None, ge=0)


class BuySkillRequest(BaseModel):
    skill_id: str = Field(min_length=2, max_length=48)


class SkillSlotEntry(BaseModel):
    slot_index: int = Field(ge=0, le=5)
    skill_id: str | None = Field(default=None, max_length=48)


class SkillLoadoutSaveRequest(BaseModel):
    slots: list[SkillSlotEntry] = Field(default_factory=list)


class SkillShopRefreshRequest(BaseModel):
    force: bool = True


class SkillSpecializeRequest(BaseModel):
    skill_id: str = Field(min_length=2, max_length=48)
    branch: str = Field(min_length=2, max_length=16)  # burst / sustain / control


class SkillScrapRequest(BaseModel):
    skill_id: str = Field(min_length=2, max_length=48)


class SkillExchangeRequest(BaseModel):
    skill_id: str = Field(min_length=2, max_length=48)


class BatchSellRequest(BaseModel):
    min_level: int = Field(default=1, ge=1, le=50)
    max_level: int = Field(default=50, ge=1, le=50)
    qualities: list[str] = Field(default_factory=list)
    category: str = Field(default="equipment", min_length=2, max_length=24)
    include_equipped: bool = False


class BalanceConfigUpsertEntry(BaseModel):
    domain: str = Field(min_length=2, max_length=32)
    key_name: str = Field(min_length=2, max_length=64)
    value: Any


class BalanceConfigUpsertRequest(BaseModel):
    entries: list[BalanceConfigUpsertEntry] = Field(default_factory=list)


class DungeonEventRollRequest(BaseModel):
    dungeon_id: str = Field(min_length=1, max_length=24)
    room_index: int = Field(ge=0, le=32)
    node_type: str = Field(min_length=3, max_length=24)
    chosen_event_ids: list[str] = Field(default_factory=list)


SLOT_ORDER: list[str] = ["weapon", "helmet", "chest", "gloves", "pants", "boots"]
DUNGEON_NODE_LAYOUTS: dict[str, list[str]] = {
    "DUN30": ["normal", "elite", "treasure", "heal", "boss"],
    "DUN40": ["normal", "normal", "elite", "treasure", "boss"],
    "DUN50": ["normal", "elite", "heal", "elite", "boss"],
}
SLOT_LABELS_CN: dict[str, str] = {
    "weapon": "武器",
    "helmet": "头盔",
    "chest": "胸甲",
    "gloves": "手套",
    "pants": "护腿",
    "boots": "战靴",
}
EPIC_PLUS_QUALITIES: frozenset[str] = frozenset({"史诗", "传奇", "神话"})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def seed_balance_configs(conn: sqlite3.Connection) -> None:
    defaults: dict[tuple[str, str], Any] = {
        ("equipment", "quality_scale"): {"普通": 1.00, "优秀": 1.18, "精良": 1.40, "史诗": 1.75, "传奇": 2.05, "神话": 2.40},
        ("equipment", "level_growth_per_level"): 0.055,
        (
            "equipment",
            "slot_base_stats",
        ): {
            "weapon": {"attack": 20, "hp": 0, "defense": 0, "dodge": 0.0, "crit": 0.02, "block": 0.0, "lifesteal": 0.0},
            "helmet": {"attack": 0, "hp": 30, "defense": 12, "dodge": 0.01, "crit": 0.0, "block": 0.02, "lifesteal": 0.0},
            "chest": {"attack": 0, "hp": 60, "defense": 24, "dodge": 0.0, "crit": 0.0, "block": 0.03, "lifesteal": 0.0},
            "gloves": {"attack": 5, "hp": 12, "defense": 10, "dodge": 0.02, "crit": 0.03, "block": 0.0, "lifesteal": 0.0},
            "pants": {"attack": 0, "hp": 45, "defense": 18, "dodge": 0.01, "crit": 0.0, "block": 0.02, "lifesteal": 0.0},
            "boots": {"attack": 0, "hp": 20, "defense": 9, "dodge": 0.04, "crit": 0.0, "block": 0.0, "lifesteal": 0.0},
            "bag": {"attack": 0, "hp": 0, "defense": 0, "dodge": 0.0, "crit": 0.0, "block": 0.0, "lifesteal": 0.0},
        },
        (
            "equipment",
            "set_bonus_by_trait",
        ): {
            "arc": {"crit": 0.01, "dodge": 0.01},
            "hunt": {"attack_level_scale": 0.4, "attack_min": 6, "crit": 0.03},
            "pal": {"hp_level_scale": 1.8, "hp_min": 20, "block": 0.04},
            "iron": {"defense_level_scale": 0.6, "defense_min": 6, "hp_level_scale": 1.1, "hp_min": 10},
        },
        ("equipment", "epic_lifesteal_bonus"): 0.01,
        ("equipment", "sell_quality_base"): {"普通": 12, "优秀": 22, "精良": 45, "史诗": 120, "传奇": 260, "神话": 500},
        ("equipment", "sell_level_factor"): 2,
        ("equipment", "sell_power_divisor"): 3,
        ("equipment", "sell_consumable_bonus"): 15,
        ("equipment", "sell_affix_count_bonus"): 25,
        ("equipment", "sell_affix_atk_def_factor"): 0.6,
        ("equipment", "sell_affix_crit_damage_factor"): 120,
        ("equipment", "sell_affix_freeze_factor"): 90,
        ("equipment", "sell_min_price"): 5,
        ("monster", "map_level_cap"): {"M01": 12, "M02": 22, "M03": 32, "M04": 42, "M05": 50},
        (
            "monster",
            "reward_by_type",
        ): {
            "普通怪": {"exp": 32, "gold": 24, "power_scale": 1.0, "drop_source": "monster_normal", "ticket": [0.08, 0.0]},
            "精英怪": {"exp": 88, "gold": 70, "power_scale": 2.2, "drop_source": "monster_elite", "ticket": [0.35, 0.05]},
            "地图Boss": {"exp": 210, "gold": 180, "power_scale": 4.8, "drop_source": "boss_world", "ticket": [0.75, 0.20]},
        },
        (
            "monster",
            "combat_snapshot",
        ): {
            "hp_base": 150,
            "hp_level_gain": 42,
            "attack_base": 18,
            "attack_level_gain": 5,
            "defense_base": 10,
            "defense_level_gain": 3.2,
            "defense_scale_factor": 0.92,
            "dodge_base": 0.04,
            "dodge_scale_gain": 0.015,
            "dodge_cap": 0.28,
            "crit_base": 0.03,
            "crit_scale_gain": 0.02,
            "crit_cap": 0.30,
            "block_base": 0.02,
            "block_scale_gain": 0.01,
            "block_cap": 0.20,
        },
        (
            "monster",
            "score_formula",
        ): {
            "hp_w": 0.18,
            "attack_w": 2.7,
            "defense_w": 1.9,
            "dodge_w": 260,
            "crit_w": 230,
            "block_w": 220,
            "lifesteal_w": 320,
            "crit_damage_w": 170,
            "freeze_w": 160,
        },
        (
            "monster",
            "win_rate_formula",
        ): {"min": 0.03, "max": 0.95, "base": 0.08, "ratio_mult": 0.52, "fallback": 0.05},
        (
            "monster",
            "skill_templates",
        ): {
            "普通怪": [{"id": "m_basic", "name": "爪击", "mult": 1.0, "cd_ms": 1100, "trigger": "always"}],
            "精英怪": [
                {"id": "m_basic", "name": "撕裂", "mult": 1.0, "cd_ms": 1000, "trigger": "always"},
                {"id": "m_s1", "name": "重劈", "mult": 1.28, "cd_ms": 4200, "trigger": "after_basic_2"},
            ],
            "地图Boss": [
                {"id": "m_basic", "name": "压迫", "mult": 1.0, "cd_ms": 950, "trigger": "always"},
                {"id": "m_s1", "name": "印记猛击", "mult": 1.32, "cd_ms": 5500, "trigger": "after_basic_2"},
                {"id": "m_s2", "name": "地裂", "mult": 1.48, "cd_ms": 8200, "trigger": "hp_below_70"},
                {"id": "m_s3", "name": "终势", "mult": 1.62, "cd_ms": 12000, "trigger": "hp_below_35"},
            ],
        },
        (
            "monster",
            "ai_profiles",
        ): {
            "普通怪": {"trigger_priority": {"always": 10}, "combo_followup_bonus": 0},
            "精英怪": {"trigger_priority": {"after_basic_2": 120, "hp_below_70": 80, "always": 10}, "combo_followup_bonus": 15},
            "地图Boss": {
                "trigger_priority": {"hp_below_35": 220, "hp_below_70": 170, "after_basic_2": 130, "always": 10},
                "combo_followup_bonus": 20,
            },
        },
        ("drop", "skill_drop_rate_by_monster"): {"普通怪": 0.06, "精英怪": 0.14, "地图Boss": 0.28},
        ("drop", "dungeon_skill_drop_rate"): 0.16,
        (
            "drop",
            "item_quality_weights",
        ): {
            "monster_normal": [["普通", 45], ["优秀", 35], ["精良", 18], ["史诗", 2]],
            "monster_elite": [["普通", 20], ["优秀", 35], ["精良", 35], ["史诗", 10]],
            "boss_world": [["普通", 8], ["优秀", 22], ["精良", 50], ["史诗", 20]],
            "boss_dungeon": [["普通", 3], ["优秀", 10], ["精良", 52], ["史诗", 35]],
        },
        ("shop", "offer_count"): 4,
        ("shop", "refresh_base_cost"): 120,
        ("shop", "refresh_step_cost"): 90,
        ("shop", "daily_seed_user_factor"): 97,
        ("shop", "daily_seed_refresh_factor"): 131,
        ("shop", "skill_scrap_shard_gain"): 12,
        ("shop", "skill_exchange_shard_cost"): 30,
        ("skill", "basic_cd"): {"min": 480, "max": 1650, "base": 1580, "attack_factor": 1.15},
        ("skill", "mastery_level_thresholds"): [60, 180, 360, 600, 900],
        (
            "skill",
            "branch_adjustments",
        ): {
            "burst": {"dmg_per_level": 0.04, "heal_per_level": -0.004, "cd_factor_per_level": 0.0, "cd_floor_factor": 1.0},
            "sustain": {"dmg_per_level": 0.012, "heal_per_level": 0.01, "cd_factor_per_level": -0.02, "cd_floor_factor": 0.75},
            "control": {"dmg_per_level": 0.02, "heal_per_level": 0.0, "cd_factor_per_level": -0.035, "cd_floor_factor": 0.68},
        },
        (
            "dungeon",
            "event_pools",
        ): {
            "treasure": [
                {"id": "gold", "label": "贪婪宝箱", "weight": 40, "tags": ["greed"], "effect": {"rewardBonus": 0.12, "clearRateBonus": -0.03, "greedValue": 0.14}},
                {"id": "focus", "label": "战术卷轴", "weight": 34, "tags": ["safe"], "effect": {"clearRateBonus": 0.05, "curseValue": -0.05}},
                {"id": "risk", "label": "禁忌符石", "weight": 18, "tags": ["risk"], "effect": {"rewardBonus": 0.2, "bossScaleDelta": 0.08, "curseValue": 0.22, "greedValue": 0.12}},
                {"id": "echo", "label": "回响棱镜", "weight": 25, "tags": ["spell"], "effect": {"rewardBonus": 0.08, "clearRateBonus": 0.01, "greedValue": 0.08}},
            ],
            "heal": [
                {"id": "safe", "label": "圣泉休整", "weight": 40, "tags": ["safe"], "effect": {"clearRateBonus": 0.08, "curseValue": -0.08}},
                {"id": "blood", "label": "血祭强攻", "weight": 24, "tags": ["risk"], "effect": {"rewardBonus": 0.1, "clearRateBonus": 0.02, "curseValue": 0.12, "greedValue": 0.06}},
                {"id": "ward", "label": "护纹祈祷", "weight": 28, "tags": ["shield"], "effect": {"clearRateBonus": 0.04, "bossScaleDelta": -0.05, "curseValue": -0.04}},
            ],
            "elite": [
                {"id": "weaken", "label": "削弱精英", "weight": 36, "tags": ["safe"], "effect": {"clearRateBonus": 0.06, "rewardBonus": -0.04, "curseValue": -0.03}},
                {"id": "frenzy", "label": "挑战词缀", "weight": 24, "tags": ["risk"], "effect": {"rewardBonus": 0.14, "bossScaleDelta": 0.06, "curseValue": 0.16, "greedValue": 0.09}},
                {"id": "double", "label": "双刃契约", "weight": 20, "tags": ["risk", "greed"], "effect": {"rewardBonus": 0.18, "clearRateBonus": -0.05, "curseValue": 0.2, "greedValue": 0.16}},
            ],
        },
        ("dungeon", "event_offer_count"): 3,
        ("dungeon", "event_mutual_exclusive_tags"): ["risk"],
    }
    for (domain, key), value in defaults.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO game_balance_config (domain, key_name, value_json, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (domain, key, json.dumps(value, ensure_ascii=False), now_iso()),
        )


def balance_value_from_conn(conn: sqlite3.Connection, domain: str, key: str, default: Any) -> Any:
    row = conn.execute(
        "SELECT value_json FROM game_balance_config WHERE domain = ? AND key_name = ?",
        (domain, key),
    ).fetchone()
    if not row:
        return default
    try:
        return json.loads(str(row["value_json"]))
    except (TypeError, json.JSONDecodeError):
        return default


def get_balance_value(domain: str, key: str, default: Any) -> Any:
    conn = get_db()
    try:
        return balance_value_from_conn(conn, domain, key, default)
    finally:
        conn.close()


def monster_ai_profile(monster_type: str) -> dict[str, Any]:
    cfg = get_balance_value("monster", "ai_profiles", {})
    if not isinstance(cfg, dict):
        return {"trigger_priority": {"always": 10}, "combo_followup_bonus": 0}
    picked = cfg.get(monster_type) or cfg.get("地图Boss") or {"trigger_priority": {"always": 10}, "combo_followup_bonus": 0}
    if not isinstance(picked, dict):
        return {"trigger_priority": {"always": 10}, "combo_followup_bonus": 0}
    return dict(picked)


def resolve_boss_mechanic(map_id: str | None = None, dungeon_id: str | None = None) -> dict[str, Any]:
    if dungeon_id:
        mapping = {
            "DUN30": {"id": "shield_phase", "name": "护盾阶段", "desc": "Boss 开场获得护盾，需持续输出压破护盾。"},
            "DUN40": {"id": "summon_phase", "name": "召唤阶段", "desc": "Boss 周期召唤援军，压制不及时会抬高输出压力。"},
            "DUN50": {"id": "enrage_phase", "name": "狂暴阶段", "desc": "Boss 低血进入狂暴，攻速与伤害显著提升。"},
        }
        return dict(mapping.get(dungeon_id, {"id": "shield_phase", "name": "护盾阶段", "desc": "Boss 护盾吸收部分伤害。"}))
    mapping_world = {
        "M03": {"id": "shield_phase", "name": "护盾阶段", "desc": "怪物低血前有护盾吸收层。"},
        "M04": {"id": "summon_phase", "name": "召唤阶段", "desc": "战斗中会触发额外召唤打击。"},
        "M05": {"id": "enrage_phase", "name": "狂暴阶段", "desc": "血量压低后伤害提高。"},
    }
    return dict(mapping_world.get(str(map_id or ""), {"id": "shield_phase", "name": "护盾阶段", "desc": "怪物具备护盾阶段。"}))


def roll_weighted_event_options(
    node_type: str,
    chosen_event_ids: list[str],
    offer_count: int,
    seed_num: int,
) -> list[dict[str, Any]]:
    pools = get_balance_value("dungeon", "event_pools", {})
    if not isinstance(pools, dict):
        return []
    all_options = pools.get(node_type) or []
    if not isinstance(all_options, list):
        return []
    chosen_set = {str(x) for x in chosen_event_ids}
    candidates = [dict(x) for x in all_options if isinstance(x, dict) and str(x.get("id")) not in chosen_set]
    if not candidates:
        return []
    mutual_tags_raw = get_balance_value("dungeon", "event_mutual_exclusive_tags", [])
    mutual_tags = {str(x) for x in mutual_tags_raw} if isinstance(mutual_tags_raw, list) else set()
    chosen_tags: set[str] = set()
    if mutual_tags:
        for ev in all_options:
            if not isinstance(ev, dict):
                continue
            if str(ev.get("id")) not in chosen_set:
                continue
            tags = ev.get("tags") or []
            if isinstance(tags, list):
                chosen_tags.update({str(t) for t in tags if str(t) in mutual_tags})
    if chosen_tags:
        candidates = [
            c
            for c in candidates
            if not (isinstance(c.get("tags"), list) and any(str(t) in chosen_tags for t in (c.get("tags") or [])))
        ]
    if not candidates:
        return []
    rng = random.Random(seed_num)
    picks: list[dict[str, Any]] = []
    want = max(1, min(offer_count, len(candidates)))
    pool = candidates[:]
    while pool and len(picks) < want:
        weights = [max(1, int(x.get("weight") or 1)) for x in pool]
        picked = rng.choices(pool, weights=weights, k=1)[0]
        picks.append(picked)
        pool = [x for x in pool if str(x.get("id")) != str(picked.get("id"))]
    return picks


def seed_game_skills(conn: sqlite3.Connection) -> None:
    rows = [
        # 基础通用技能（新手默认可通过商店购买）
        ("SK_W_SLASH", "刃裂斩", "武器位技能：对单体造成较高伤害。", 1200, 1.35, 0.0, 3200, "weapon", 0),
        ("SK_H_FOCUS", "战意凝聚", "头盔位技能：小幅伤害并回复生命。", 900, 1.12, 0.06, 4500, "helmet", 0),
        ("SK_C_FORT", "铁壁反击", "胸甲位技能：中额伤害。", 1100, 1.22, 0.0, 5200, "chest", 0),
        ("SK_G_STORM", "疾风连打", "手套位技能：高倍率爆发。", 1300, 1.44, 0.0, 3400, "gloves", 0),
        ("SK_P_SHADOW", "影袭", "护腿位技能：中速冷却。", 950, 1.2, 0.0, 3800, "pants", 0),
        ("SK_B_RUSH", "踏前斩", "战靴位技能：短冷却突进伤害。", 1000, 1.28, 0.0, 2800, "boots", 0),
        # 早期首领掉落技能（保留）
        ("SK_DROP_KING", "王权烙印", "首领掉落：极高爆发，仅限武器位。", 0, 1.58, 0.0, 9000, "weapon", 1),
        ("SK_DROP_ABYSS", "渊噬", "首领掉落：范围侵蚀，仅限手套位。", 0, 1.52, 0.0, 7800, "gloves", 1),
    ]

    # 职业特性技能书（每个特性至少20本）
    # 特性：iron=均衡战士 / hunt=单体猎杀号 / arc=AOE法能 / pal=坦辅回复
    trait_defs = {
        "iron": {
            "name": "铁壁",
            "dmg_base": 1.18,
            "heal_base": 0.02,
            "cd_base": 4100,
            "price_base": 1450,
            "desc": "铁壁系技能书：均衡输出与防守反击。",
            "slots": ["weapon", "chest", "helmet", "gloves", "pants", "boots"],
        },
        "hunt": {
            "name": "猎杀号",
            "dmg_base": 1.34,
            "heal_base": 0.0,
            "cd_base": 3600,
            "price_base": 1650,
            "desc": "猎杀号技能书：高爆发单体斩杀。",
            "slots": ["weapon", "gloves", "boots", "pants", "helmet", "chest"],
        },
        "arc": {
            "name": "崩界",
            "dmg_base": 1.3,
            "heal_base": 0.01,
            "cd_base": 3900,
            "price_base": 1580,
            "desc": "崩界系技能书：范围能量溅射与节奏压制。",
            "slots": ["gloves", "weapon", "helmet", "chest", "pants", "boots"],
        },
        "pal": {
            "name": "圣裁",
            "dmg_base": 1.16,
            "heal_base": 0.05,
            "cd_base": 4300,
            "price_base": 1500,
            "desc": "圣裁系技能书：续航、护体与团队生存倾向。",
            "slots": ["chest", "helmet", "weapon", "gloves", "pants", "boots"],
        },
    }

    tier_names = ["初卷", "战卷", "秘卷", "王卷", "终卷"]
    # 每个特性 20 本：5阶 * 4种式样
    forms = [
        ("斩", 0.00, 0.00, 0),
        ("袭", 0.08, 0.00, -250),
        ("印", -0.03, 0.03, 220),
        ("域", 0.04, 0.01, 420),
    ]
    for trait_key, cfg in trait_defs.items():
        skill_idx = 0
        for tier_i, tier_name in enumerate(tier_names, start=1):
            for form_name, dmg_add, heal_add, cd_add in forms:
                skill_idx += 1
                sid = f"SK_{trait_key.upper()}_{skill_idx:02d}"
                slot = cfg["slots"][(skill_idx - 1) % len(cfg["slots"])]
                name = f"{cfg['name']}{tier_name}{form_name}"
                dmg = round(cfg["dmg_base"] + dmg_add + tier_i * 0.03, 4)
                heal = round(max(0.0, cfg["heal_base"] + heal_add + tier_i * 0.003), 4)
                cd = int(max(2200, cfg["cd_base"] + cd_add - tier_i * 120))
                price = int(cfg["price_base"] + tier_i * 260 + skill_idx * 45)
                rows.append(
                    (
                        sid,
                        name,
                        f"{cfg['desc']}（{tier_name}{form_name}）",
                        price,
                        dmg,
                        heal,
                        cd,
                        slot,
                        0,
                    )
                )

    # 每个特性额外2本掉落技能（总计8本），用于碎片兑换/首领掉落扩展
    drop_trait_rows = [
        ("iron", "壁垒终断", "weapon"),
        ("iron", "钢魂战吼", "chest"),
        ("hunt", "猎神处决", "weapon"),
        ("hunt", "夜幕追猎", "boots"),
        ("arc", "万象湮灭", "gloves"),
        ("arc", "裂界回响", "helmet"),
        ("pal", "圣域赦令", "chest"),
        ("pal", "裁决恩赐", "helmet"),
    ]
    for i, (trait_key, n, slot) in enumerate(drop_trait_rows, start=1):
        rows.append(
            (
                f"SK_DROP_{trait_key.upper()}_{i:02d}",
                n,
                f"{trait_defs[trait_key]['name']}特性首领掉落技能书。",
                0,
                round(trait_defs[trait_key]["dmg_base"] + 0.22 + i * 0.01, 4),
                round(max(0.0, trait_defs[trait_key]["heal_base"] + 0.02), 4),
                int(max(2600, trait_defs[trait_key]["cd_base"] + 900)),
                slot,
                1,
            )
        )
    for row in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO game_skills
            (skill_id, name, description, gold_price, damage_mult, heal_pct_max, cooldown_ms, allowed_slot, drop_only)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )


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
                skill_shard INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        wallet_columns = {r["name"] for r in conn.execute("PRAGMA table_info(player_wallet)").fetchall()}
        if "skill_shard" not in wallet_columns:
            conn.execute("ALTER TABLE player_wallet ADD COLUMN skill_shard INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                gold_price INTEGER NOT NULL DEFAULT 0,
                damage_mult REAL NOT NULL DEFAULT 1.0,
                heal_pct_max REAL NOT NULL DEFAULT 0.0,
                cooldown_ms INTEGER NOT NULL DEFAULT 3000,
                allowed_slot TEXT NOT NULL DEFAULT 'any',
                drop_only INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_skills (
                user_id INTEGER NOT NULL,
                skill_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, skill_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (skill_id) REFERENCES game_skills(skill_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_skill_loadout (
                user_id INTEGER NOT NULL,
                slot_index INTEGER NOT NULL,
                skill_id TEXT,
                PRIMARY KEY (user_id, slot_index),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (skill_id) REFERENCES game_skills(skill_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_skill_mastery (
                user_id INTEGER NOT NULL,
                skill_id TEXT NOT NULL,
                mastery_exp INTEGER NOT NULL DEFAULT 0,
                branch TEXT NOT NULL DEFAULT 'burst',
                PRIMARY KEY (user_id, skill_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (skill_id) REFERENCES game_skills(skill_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_skill_shop_state (
                user_id INTEGER PRIMARY KEY,
                refresh_count INTEGER NOT NULL DEFAULT 0,
                refresh_seed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_fights (
                fight_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS game_balance_config (
                domain TEXT NOT NULL,
                key_name TEXT NOT NULL,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (domain, key_name)
            )
            """
        )
        seed_balance_configs(conn)
        seed_game_skills(conn)
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


def assert_config_admin(authorization: str | None, x_admin_key: str | None) -> None:
    token = parse_auth_token(authorization)
    payload = decode_token(token)
    username = str(payload.get("username") or "")
    if CONFIG_ADMIN_USERNAME and username != CONFIG_ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="仅配置管理员可访问")
    if CONFIG_ADMIN_KEY and (not x_admin_key or x_admin_key.strip() != CONFIG_ADMIN_KEY):
        raise HTTPException(status_code=403, detail="缺少或错误的管理员密钥")


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
    quality_scale = get_balance_value(
        "equipment",
        "quality_scale",
        {"普通": 1.00, "优秀": 1.18, "精良": 1.40, "史诗": 1.75, "传奇": 2.05, "神话": 2.40},
    )
    level_growth = float(get_balance_value("equipment", "level_growth_per_level", 0.055))
    slot_base_stats = get_balance_value("equipment", "slot_base_stats", {})
    lv_scale = 1 + (level_required - 1) * level_growth
    q_scale = float(quality_scale.get(quality, 1.0)) if isinstance(quality_scale, dict) else 1.0
    base_map = slot_base_stats if isinstance(slot_base_stats, dict) and slot_base_stats else {}
    base = dict(base_map.get(slot) or {"attack": 0, "hp": 0, "defense": 0, "dodge": 0.0, "crit": 0.0, "block": 0.0, "lifesteal": 0.0})
    stats = {
        "attack": int(round(base["attack"] * lv_scale * q_scale)),
        "hp": int(round(base["hp"] * lv_scale * q_scale)),
        "defense": int(round(base["defense"] * lv_scale * q_scale)),
        "dodge": round(base["dodge"] * q_scale, 4),
        "crit": round(base["crit"] * q_scale, 4),
        "block": round(base["block"] * q_scale, 4),
        "lifesteal": round(base["lifesteal"] * q_scale, 4),
    }
    set_bonus_by_trait = get_balance_value("equipment", "set_bonus_by_trait", {})
    if set_key and isinstance(set_bonus_by_trait, dict):
        for trait in ("arc", "hunt", "pal", "iron"):
            if trait in str(set_key):
                tb = set_bonus_by_trait.get(trait) or {}
                stats["crit"] = round(stats["crit"] + float(tb.get("crit", 0.0)), 4)
                stats["dodge"] = round(stats["dodge"] + float(tb.get("dodge", 0.0)), 4)
                if "attack_level_scale" in tb:
                    stats["attack"] += max(int(tb.get("attack_min", 0)), int(level_required * float(tb.get("attack_level_scale", 0.0))))
                if "hp_level_scale" in tb:
                    stats["hp"] += max(int(tb.get("hp_min", 0)), int(level_required * float(tb.get("hp_level_scale", 0.0))))
                if "defense_level_scale" in tb:
                    stats["defense"] += max(
                        int(tb.get("defense_min", 0)), int(level_required * float(tb.get("defense_level_scale", 0.0)))
                    )
                stats["block"] = round(stats["block"] + float(tb.get("block", 0.0)), 4)
                break
    if quality == "史诗":
        epic_lifesteal_bonus = float(get_balance_value("equipment", "epic_lifesteal_bonus", 0.01))
        stats["lifesteal"] = round(stats["lifesteal"] + epic_lifesteal_bonus, 4)
    return stats


def build_combat_snapshot(level: int, scale: float) -> dict[str, Any]:
    cfg = get_balance_value("monster", "combat_snapshot", {})
    hp_base = float(cfg.get("hp_base", 150))
    hp_gain = float(cfg.get("hp_level_gain", 42))
    atk_base = float(cfg.get("attack_base", 18))
    atk_gain = float(cfg.get("attack_level_gain", 5))
    def_base = float(cfg.get("defense_base", 10))
    def_gain = float(cfg.get("defense_level_gain", 3.2))
    def_scale_factor = float(cfg.get("defense_scale_factor", 0.92))
    dodge_base = float(cfg.get("dodge_base", 0.04))
    dodge_gain = float(cfg.get("dodge_scale_gain", 0.015))
    dodge_cap = float(cfg.get("dodge_cap", 0.28))
    crit_base = float(cfg.get("crit_base", 0.03))
    crit_gain = float(cfg.get("crit_scale_gain", 0.02))
    crit_cap = float(cfg.get("crit_cap", 0.3))
    block_base = float(cfg.get("block_base", 0.02))
    block_gain = float(cfg.get("block_scale_gain", 0.01))
    block_cap = float(cfg.get("block_cap", 0.2))
    return {
        "hp": int((hp_base + level * hp_gain) * scale),
        "attack": int((atk_base + level * atk_gain) * scale),
        "defense": int((def_base + level * def_gain) * max(1.0, scale * def_scale_factor)),
        "dodge": round(min(dodge_base + scale * dodge_gain, dodge_cap), 4),
        "crit": round(min(crit_base + scale * crit_gain, crit_cap), 4),
        "block": round(min(block_base + scale * block_gain, block_cap), 4),
    }


def calculate_combat_score(stats: dict[str, Any]) -> float:
    w = get_balance_value("monster", "score_formula", {})
    return (
        float(stats["hp"]) * float(w.get("hp_w", 0.18))
        + float(stats["attack"]) * float(w.get("attack_w", 2.7))
        + float(stats["defense"]) * float(w.get("defense_w", 1.9))
        + float(stats["dodge"]) * float(w.get("dodge_w", 260))
        + float(stats["crit"]) * float(w.get("crit_w", 230))
        + float(stats["block"]) * float(w.get("block_w", 220))
        + float(stats.get("lifesteal", 0)) * float(w.get("lifesteal_w", 320))
        + float(stats.get("crit_damage", 0)) * float(w.get("crit_damage_w", 170))
        + float(stats.get("freeze", 0)) * float(w.get("freeze_w", 160))
    )


def skill_slots_unlocked_from_equipped(equipped: list[dict[str, Any]]) -> list[bool]:
    sm = {str(e.get("slot")): e for e in equipped}
    return [bool(sm.get(s) and str(sm[s].get("quality")) in EPIC_PLUS_QUALITIES) for s in SLOT_ORDER]


def monster_skill_templates(monster_type: str) -> list[dict[str, Any]]:
    cfg = get_balance_value("monster", "skill_templates", {})
    if isinstance(cfg, dict):
        out = cfg.get(monster_type) or cfg.get("地图Boss")
        if isinstance(out, list):
            return [dict(x) for x in out if isinstance(x, dict)]
    return [{"id": "m_basic", "name": "爪击", "mult": 1.0, "cd_ms": 1100, "trigger": "always"}]


def player_basic_cd_ms(attack: int) -> int:
    cfg = get_balance_value("skill", "basic_cd", {})
    atk = max(1, int(attack))
    min_cd = int(cfg.get("min", 480))
    max_cd = int(cfg.get("max", 1650))
    base_cd = float(cfg.get("base", 1580))
    atk_factor = float(cfg.get("attack_factor", 1.15))
    return int(max(min_cd, min(max_cd, base_cd - atk * atk_factor)))


def battle_balance_mods(score_ratio: float) -> dict[str, float]:
    # 实时战斗中不再按“预判输赢”强行改倍率，只做轻微平衡，核心结果由操作与技能决定。
    ratio = max(0.3, min(2.5, float(score_ratio)))
    player_out = max(0.92, min(1.08, 1.0 + (ratio - 1.0) * 0.06))
    monster_out = max(0.92, min(1.08, 1.0 - (ratio - 1.0) * 0.05))
    regen = max(0.0, min(0.0035, 0.0012 + (ratio - 1.0) * 0.001))
    return {"player_out": round(player_out, 4), "monster_out": round(monster_out, 4), "regen": round(regen, 4)}


def build_skill_loadout(conn: sqlite3.Connection, user_id: int, equipped: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unlocks = skill_slots_unlocked_from_equipped(equipped)
    rows = conn.execute(
        "SELECT slot_index, skill_id FROM player_skill_loadout WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    by_slot = {int(r["slot_index"]): r["skill_id"] for r in rows}
    out: list[dict[str, Any]] = []
    for idx, slot_name in enumerate(SLOT_ORDER):
        sid = by_slot.get(idx)
        meta_row = None
        if sid:
            meta_row = conn.execute(
                """
                SELECT skill_id, name, description, gold_price, damage_mult, heal_pct_max, cooldown_ms, allowed_slot
                FROM game_skills WHERE skill_id = ?
                """,
                (sid,),
            ).fetchone()
        mastery_row = None
        if sid:
            mastery_row = conn.execute(
                "SELECT mastery_exp, branch FROM player_skill_mastery WHERE user_id = ? AND skill_id = ?",
                (user_id, sid),
            ).fetchone()
        owned = bool(
            sid
            and conn.execute(
                "SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?",
                (user_id, sid),
            ).fetchone()
        )
        allowed = True
        if meta_row and str(meta_row["allowed_slot"]) not in ("any", slot_name):
            allowed = False
        use_skill = bool(sid and meta_row and owned and allowed and unlocks[idx])
        skill_meta = dict(meta_row) if use_skill and meta_row else None
        if skill_meta:
            branch = str(mastery_row["branch"]) if mastery_row else "burst"
            level = mastery_level(int(mastery_row["mastery_exp"])) if mastery_row else 0
            skill_meta = apply_skill_branch_adjustments(skill_meta, branch, level)
        out.append(
            {
                "slot_index": idx,
                "slot": slot_name,
                "slot_label": SLOT_LABELS_CN.get(slot_name, slot_name),
                "unlocked": unlocks[idx],
                "skill_id": sid if use_skill else None,
                "name": (skill_meta["name"] if skill_meta else None),
                "description": (skill_meta["description"] if skill_meta else None),
                "damage_mult": float(skill_meta["damage_mult"]) if skill_meta else None,
                "heal_pct_max": float(skill_meta["heal_pct_max"]) if skill_meta else None,
                "cooldown_ms": int(skill_meta["cooldown_ms"]) if skill_meta else None,
                "branch": (skill_meta.get("branch") if skill_meta else None),
                "mastery_level": (skill_meta.get("mastery_level") if skill_meta else 0),
            }
        )
    return out


def roll_skill_drop(conn: sqlite3.Connection, user_id: int, monster_type: str, won: bool) -> str | None:
    if not won:
        return None
    rates = balance_value_from_conn(
        conn,
        "drop",
        "skill_drop_rate_by_monster",
        {"普通怪": 0.06, "精英怪": 0.14, "地图Boss": 0.28},
    )
    p = float((rates or {}).get(monster_type, 0.06))
    if random.random() > p:
        return None
    rows = conn.execute(
        "SELECT skill_id FROM game_skills WHERE drop_only = 1 ORDER BY skill_id"
    ).fetchall()
    owned = {
        str(r["skill_id"])
        for r in conn.execute("SELECT skill_id FROM player_skills WHERE user_id = ?", (user_id,)).fetchall()
    }
    pool = [str(r["skill_id"]) for r in rows if str(r["skill_id"]) not in owned]
    if not pool:
        return None
    return random.choice(pool)


def compute_world_monster_fight_payload(
    user_id: int,
    map_id: str,
    monster_type: str,
) -> dict[str, Any]:
    profile = get_player_profile(user_id)
    map_level_cap = get_balance_value("monster", "map_level_cap", {"M01": 12, "M02": 22, "M03": 32, "M04": 42, "M05": 50})
    if map_id not in map_level_cap:
        raise HTTPException(status_code=404, detail="地图不存在")
    monster_cfg = get_balance_value(
        "monster",
        "reward_by_type",
        {
            "普通怪": {"exp": 32, "gold": 24, "power_scale": 1.0, "drop_source": "monster_normal", "ticket": [0.08, 0.0]},
            "精英怪": {"exp": 88, "gold": 70, "power_scale": 2.2, "drop_source": "monster_elite", "ticket": [0.35, 0.05]},
            "地图Boss": {"exp": 210, "gold": 180, "power_scale": 4.8, "drop_source": "boss_world", "ticket": [0.75, 0.20]},
        },
    )
    cfg = monster_cfg.get(monster_type)
    if not cfg:
        raise HTTPException(status_code=400, detail="怪物类型错误")
    target_level = min(int(map_level_cap[map_id]), 50)
    player_stats = profile["total_stats"]
    monster_stats = build_combat_snapshot(target_level, cfg["power_scale"])
    player_score = calculate_combat_score(player_stats) + len(profile["active_bonuses"]) * 18
    required_score = calculate_combat_score(monster_stats)
    wr_cfg = get_balance_value("monster", "win_rate_formula", {"min": 0.03, "max": 0.95, "base": 0.08, "ratio_mult": 0.52, "fallback": 0.05})
    if player_score <= 0:
        win_rate = float(wr_cfg.get("fallback", 0.05))
        ratio = 0.0
    else:
        ratio = player_score / max(1, required_score)
        win_rate = max(
            float(wr_cfg.get("min", 0.03)),
            min(float(wr_cfg.get("max", 0.95)), float(wr_cfg.get("base", 0.08)) + ratio * float(wr_cfg.get("ratio_mult", 0.52))),
        )

    atk = int(player_stats["attack"])
    p_max = int(player_stats["hp"])
    m_max = int(max(monster_stats["hp"], 220) * 4 + int(monster_stats["attack"]) * 2)
    payload: dict[str, Any] = {
        "version": 1,
        "map_id": map_id,
        "monster_type": monster_type,
        "target_level": target_level,
        "player_score": round(player_score, 1),
        "monster_score": round(required_score, 1),
        "win_rate_estimate": round(win_rate, 3),
        "monster_stats": monster_stats,
        "display": {
            "player_max_hp": p_max,
            "monster_max_hp": m_max,
            "player_attack": atk,
            "player_defense": int(player_stats["defense"]),
            "monster_attack": int(monster_stats["attack"]),
            "monster_defense": int(monster_stats["defense"]),
            "basic_cd_ms": player_basic_cd_ms(atk),
            "balance": battle_balance_mods(ratio),
        },
    }
    return payload


def apply_world_monster_fight_payload(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if int(payload.get("version") or 0) != 1:
        raise HTTPException(status_code=400, detail="战斗数据版本无效")
    map_id = str(payload["map_id"])
    monster_type = str(payload["monster_type"])
    map_level_cap = get_balance_value("monster", "map_level_cap", {"M01": 12, "M02": 22, "M03": 32, "M04": 42, "M05": 50})
    monster_cfg = get_balance_value(
        "monster",
        "reward_by_type",
        {
            "普通怪": {"exp": 32, "gold": 24, "power_scale": 1.0, "drop_source": "monster_normal", "ticket": [0.08, 0.0]},
            "精英怪": {"exp": 88, "gold": 70, "power_scale": 2.2, "drop_source": "monster_elite", "ticket": [0.35, 0.05]},
            "地图Boss": {"exp": 210, "gold": 180, "power_scale": 4.8, "drop_source": "boss_world", "ticket": [0.75, 0.20]},
        },
    )
    cfg = monster_cfg.get(monster_type)
    if not cfg:
        raise HTTPException(status_code=400, detail="怪物类型错误")
    target_level = int(payload.get("target_level") or map_level_cap.get(map_id, 1))
    if bool(payload.get("resolved_by_hp")):
        won = bool(payload.get("won"))
    else:
        won = random.random() < float(payload.get("win_rate_estimate") or 0.0)

    if won:
        exp_gain = int(float(cfg["exp"]) * (0.85 + random.random() * 0.3))
        gold_gain = int(float(cfg["gold"]) * (0.85 + random.random() * 0.3))
        ticket = list(cfg["ticket"]) if isinstance(cfg.get("ticket"), (tuple, list)) else [0.0, 0.0]
        normal_ticket_gain = 1 if random.random() < float(ticket[0]) else 0
        advanced_ticket_gain = 1 if random.random() < float(ticket[1]) else 0
        enhance_stone = random.randint(1, 3) if monster_type != "普通怪" else random.randint(0, 1)
        reroll_stone = random.randint(0, 2) if monster_type == "地图Boss" else random.randint(0, 1)
        dropped_item = choose_drop_item(target_level, str(cfg["drop_source"]))
        epic_shard_extra = 1 if dropped_item and str(dropped_item.get("quality")) == "史诗" else 0
    else:
        exp_gain = int(float(cfg["exp"]) * 0.25)
        gold_gain = int(float(cfg["gold"]) * 0.2)
        normal_ticket_gain = 0
        advanced_ticket_gain = 0
        enhance_stone = 0
        reroll_stone = 0
        dropped_item = None
        epic_shard_extra = 0

    add_player_exp(user_id, exp_gain)
    add_wallet_values(
        user_id,
        gold=gold_gain,
        normal_ticket=normal_ticket_gain,
        advanced_ticket=advanced_ticket_gain,
        enhance_stone=enhance_stone,
        reroll_stone=reroll_stone,
        epic_shard=epic_shard_extra,
    )
    granted: dict[str, Any] | None = None
    if won and dropped_item and isinstance(dropped_item, dict) and dropped_item.get("item_id"):
        granted = grant_item(user_id, str(dropped_item["item_id"]), equipped=0, item_data=dropped_item)
    skill_drop_id: str | None = None
    conn = get_db()
    try:
        skill_drop_id = roll_skill_drop(conn, user_id, monster_type, won)
    finally:
        conn.close()
    if skill_drop_id:
        conn = get_db()
        try:
            exists = conn.execute(
                "SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?",
                (user_id, str(skill_drop_id)),
            ).fetchone()
            sk = conn.execute("SELECT 1 FROM game_skills WHERE skill_id = ?", (str(skill_drop_id),)).fetchone()
            if sk and not exists:
                conn.execute(
                    "INSERT INTO player_skills (user_id, skill_id, created_at) VALUES (?, ?, ?)",
                    (user_id, str(skill_drop_id), now_iso()),
                )
                conn.commit()
        finally:
            conn.close()
    conn = get_db()
    try:
        add_mastery_exp_for_loadout(conn, user_id, 12 if won else 4)
        conn.commit()
    finally:
        conn.close()

    profile = get_player_profile(user_id)
    return {
        "ok": True,
        "won": won,
        "map_id": map_id,
        "monster_type": monster_type,
        "player_score": payload.get("player_score"),
        "monster_score": payload.get("monster_score"),
        "monster_stats": payload.get("monster_stats"),
        "win_rate_estimate": payload.get("win_rate_estimate"),
        "rewards": {
            "exp": exp_gain,
            "gold": gold_gain,
            "normal_ticket": normal_ticket_gain,
            "advanced_ticket": advanced_ticket_gain,
            "item": granted,
            "skill_id": str(skill_drop_id) if skill_drop_id else None,
        },
        "profile": profile,
    }


def roll_dungeon_skill_drop(conn: sqlite3.Connection, user_id: int) -> str | None:
    p = float(balance_value_from_conn(conn, "drop", "dungeon_skill_drop_rate", 0.16))
    if random.random() > p:
        return None
    rows = conn.execute("SELECT skill_id FROM game_skills WHERE drop_only = 1 ORDER BY skill_id").fetchall()
    owned = {
        str(r["skill_id"])
        for r in conn.execute("SELECT skill_id FROM player_skills WHERE user_id = ?", (user_id,)).fetchall()
    }
    pool = [str(r["skill_id"]) for r in rows if str(r["skill_id"]) not in owned]
    if not pool:
        return None
    return random.choice(pool)


def add_mastery_exp_for_loadout(conn: sqlite3.Connection, user_id: int, amount: int) -> None:
    if amount <= 0:
        return
    skills = conn.execute(
        "SELECT skill_id FROM player_skill_loadout WHERE user_id = ? AND skill_id IS NOT NULL",
        (user_id,),
    ).fetchall()
    for r in skills:
        sid = str(r["skill_id"])
        conn.execute(
            """
            INSERT INTO player_skill_mastery (user_id, skill_id, mastery_exp, branch)
            VALUES (?, ?, ?, 'burst')
            ON CONFLICT(user_id, skill_id) DO UPDATE SET mastery_exp = player_skill_mastery.mastery_exp + excluded.mastery_exp
            """,
            (user_id, sid, amount),
        )


def mastery_level(exp: int) -> int:
    thresholds = get_balance_value("skill", "mastery_level_thresholds", [60, 180, 360, 600, 900])
    if not isinstance(thresholds, list):
        return 0
    level = 0
    for idx, v in enumerate(thresholds, start=1):
        if exp >= int(v):
            level = idx
    return level


def apply_skill_branch_adjustments(skill: dict[str, Any], branch: str, level: int) -> dict[str, Any]:
    out = dict(skill)
    dmg = float(out.get("damage_mult") or 1.0)
    heal = float(out.get("heal_pct_max") or 0.0)
    cd = int(out.get("cooldown_ms") or 3000)
    cfg = get_balance_value("skill", "branch_adjustments", {})
    bcfg = (cfg.get(branch) or {}) if isinstance(cfg, dict) else {}
    dmg += float(bcfg.get("dmg_per_level", 0.0)) * level
    heal = max(0.0, heal + float(bcfg.get("heal_per_level", 0.0)) * level)
    cd = int(cd * max(float(bcfg.get("cd_floor_factor", 1.0)), 1 + float(bcfg.get("cd_factor_per_level", 0.0)) * level))
    out["damage_mult"] = round(dmg, 4)
    out["heal_pct_max"] = round(heal, 4)
    out["cooldown_ms"] = int(max(800, cd))
    out["branch"] = branch
    out["mastery_level"] = level
    return out


def get_skill_shop_offers(conn: sqlite3.Connection, user_id: int) -> tuple[list[dict[str, Any]], int]:
    state = conn.execute(
        "SELECT refresh_count, refresh_seed FROM player_skill_shop_state WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not state:
        seed = 0
        refresh_count = 0
        conn.execute(
            "INSERT INTO player_skill_shop_state (user_id, refresh_count, refresh_seed, updated_at) VALUES (?, 0, 0, ?)",
            (user_id, now_iso()),
        )
        conn.commit()
    else:
        seed = int(state["refresh_seed"])
        refresh_count = int(state["refresh_count"])
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT skill_id, name, description, gold_price, damage_mult, heal_pct_max, cooldown_ms, allowed_slot, drop_only
            FROM game_skills
            WHERE gold_price > 0
            ORDER BY skill_id
            """
        ).fetchall()
    ]
    if not rows:
        return [], refresh_count
    user_factor = int(balance_value_from_conn(conn, "shop", "daily_seed_user_factor", 97))
    refresh_factor = int(balance_value_from_conn(conn, "shop", "daily_seed_refresh_factor", 131))
    offer_count = int(balance_value_from_conn(conn, "shop", "offer_count", 4))
    rng = random.Random((user_id * user_factor) + (seed * refresh_factor) + datetime.now(timezone.utc).timetuple().tm_yday)
    count = min(max(1, offer_count), len(rows))
    offers = rng.sample(rows, k=count)
    return offers, refresh_count


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
                (user_id, gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard, skill_shard)
                VALUES (?, 200, 1, 0, 10, 6, 0, 0)
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
    lv = max(1, int(level))
    return int(120 + lv * 32 + (lv**2) * 6.5)


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
    skill_shard: int = 0,
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
                epic_shard = epic_shard + ?,
                skill_shard = skill_shard + ?
            WHERE user_id = ?
            """,
            (gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard, skill_shard, user_id),
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
    quality_base_raw = get_balance_value(
        "equipment",
        "sell_quality_base",
        {"普通": 12, "优秀": 22, "精良": 45, "史诗": 120, "传奇": 260, "神话": 500},
    )
    quality_base = quality_base_raw if isinstance(quality_base_raw, dict) else {}
    base = quality_base.get(str(item.get("quality")), 10)
    level_part = int(item.get("level_required") or 1) * int(get_balance_value("equipment", "sell_level_factor", 2))
    power_part = int(item.get("power") or 0) // int(max(1, get_balance_value("equipment", "sell_power_divisor", 3)))
    category_bonus = int(get_balance_value("equipment", "sell_consumable_bonus", 15)) if str(item.get("category")) == "consumable" else 0
    affix_bonus = 0
    affixes = item.get("affixes") or []
    if isinstance(affixes, str):
        try:
            affixes = json.loads(affixes)
        except json.JSONDecodeError:
            affixes = []
    affix_bonus += len(affixes) * int(get_balance_value("equipment", "sell_affix_count_bonus", 25))
    affix_bonus += int(
        (float(item.get("bonus_attack") or 0) + float(item.get("bonus_defense") or 0))
        * float(get_balance_value("equipment", "sell_affix_atk_def_factor", 0.6))
    )
    affix_bonus += int(float(item.get("bonus_crit_damage") or 0) * float(get_balance_value("equipment", "sell_affix_crit_damage_factor", 120)))
    affix_bonus += int(float(item.get("bonus_freeze") or 0) * float(get_balance_value("equipment", "sell_affix_freeze_factor", 90)))
    return max(int(get_balance_value("equipment", "sell_min_price", 5)), base + level_part + power_part + category_bonus + affix_bonus)


def choose_drop_item(target_level: int, source_type: str) -> dict[str, Any] | None:
    quality_weights_raw = get_balance_value(
        "drop",
        "item_quality_weights",
        {
            "monster_normal": [["普通", 45], ["优秀", 35], ["精良", 18], ["史诗", 2]],
            "monster_elite": [["普通", 20], ["优秀", 35], ["精良", 35], ["史诗", 10]],
            "boss_world": [["普通", 8], ["优秀", 22], ["精良", 50], ["史诗", 20]],
            "boss_dungeon": [["普通", 3], ["优秀", 10], ["精良", 52], ["史诗", 35]],
        },
    )
    quality_weights = quality_weights_raw if isinstance(quality_weights_raw, dict) else {}
    fallback_weights = quality_weights.get("monster_normal") or [["普通", 100]]
    weights = quality_weights.get(source_type, fallback_weights)
    qualities = [q for q, _ in weights]
    probs = [w for _, w in weights]
    chosen_quality = random.choices(qualities, weights=probs, k=1)[0]

    conn = get_db()
    try:
        world_extra = ""
        if source_type == "boss_world":
            world_extra = " AND (set_key IS NULL OR set_key = '') "
        if chosen_quality == "史诗":
            rows = conn.execute(
                """
                SELECT item_id, name, slot, category, quality, level_required, power, set_key, bonus_trait
                FROM game_items
                WHERE quality = '史诗'
                  AND level_required <= ?
                  AND level_required >= ?
                  """
                + world_extra
                + """
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
                  """
                + world_extra
                + """
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
        lv = int(row["level"])
        total_stats = {
            "hp": 180 + lv * 30,
            "attack": int(15 + lv * 4.8),
            "defense": int(10 + lv * 3.7),
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
            SELECT gold, normal_ticket, advanced_ticket, enhance_stone, reroll_stone, epic_shard, skill_shard
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
            "skill_shard": 0,
        }

        skill_slots_unlocked = skill_slots_unlocked_from_equipped(equipped)
        skill_loadout = build_skill_loadout(conn, user_id, equipped)
        owned_skills = []
        owned_rows = conn.execute(
            """
            SELECT gs.skill_id, gs.name, gs.description, gs.damage_mult, gs.heal_pct_max, gs.cooldown_ms, gs.allowed_slot, gs.drop_only,
                   COALESCE(pm.mastery_exp, 0) AS mastery_exp, COALESCE(pm.branch, 'burst') AS branch
            FROM player_skills ps
            JOIN game_skills gs ON gs.skill_id = ps.skill_id
            LEFT JOIN player_skill_mastery pm ON pm.user_id = ps.user_id AND pm.skill_id = ps.skill_id
            WHERE ps.user_id = ?
            ORDER BY gs.allowed_slot, gs.skill_id
            """,
            (user_id,),
        ).fetchall()
        for row in owned_rows:
            base_skill = dict(row)
            lv = mastery_level(int(base_skill.get("mastery_exp") or 0))
            adjusted = apply_skill_branch_adjustments(base_skill, str(base_skill.get("branch") or "burst"), lv)
            adjusted["mastery_exp"] = int(base_skill.get("mastery_exp") or 0)
            owned_skills.append(adjusted)

        return {
            "level": int(row["level"]),
            "exp": int(row["exp"]),
            "total_power": total_power,
            "equipped": equipped,
            "total_stats": total_stats,
            "set_counts": set_counts,
            "active_bonuses": active_bonuses,
            "wallet": wallet,
            "skill_slots_unlocked": skill_slots_unlocked,
            "skill_loadout": skill_loadout,
            "owned_skills": owned_skills,
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

    return {
        "ok": True,
        "result": "challenge_passed",
        "dungeon": dict(dungeon),
        "profile": profile,
        "note": "等级满足，可进入副本（不再校验装备/套装/属性门槛）",
    }


@app.post("/game/fight/monster")
def game_fight_monster(
    body: MonsterFightRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """一键结算（兼容旧客户端）；新战斗 UI 请使用 /game/fight/engage + /game/fight/commit。"""
    user_id = get_user_id_from_header(authorization)
    payload = compute_world_monster_fight_payload(user_id, body.map_id, body.monster_type)
    return apply_world_monster_fight_payload(user_id, payload)


@app.post("/game/fight/engage")
def game_fight_engage(
    body: MonsterFightRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    payload = compute_world_monster_fight_payload(user_id, body.map_id, body.monster_type)
    fight_id = str(uuid.uuid4())
    conn = get_db()
    try:
        conn.execute("DELETE FROM pending_fights WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO pending_fights (fight_id, user_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (fight_id, user_id, json.dumps(payload, ensure_ascii=False), now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    profile = get_player_profile(user_id)
    monster_skills = monster_skill_templates(body.monster_type)
    disp = payload["display"]
    return {
        "ok": True,
        "fight_mode": "world",
        "fight_id": fight_id,
        "balance": disp["balance"],
        "monster": {
            "type": body.monster_type,
            "name": body.monster_type,
            "max_hp": disp["monster_max_hp"],
            "attack": disp["monster_attack"],
            "defense": disp["monster_defense"],
            "skills": monster_skills,
            "ai": monster_ai_profile(body.monster_type),
            "mechanic": (resolve_boss_mechanic(map_id=body.map_id) if body.monster_type == "地图Boss" else None),
        },
        "player": {
            "max_hp": disp["player_max_hp"],
            "attack": disp["player_attack"],
            "defense": disp["player_defense"],
            "basic_cd_ms": disp["basic_cd_ms"],
            "skill_bar": profile.get("skill_loadout") or [],
        },
        "win_rate_estimate": payload["win_rate_estimate"],
        "player_score": payload["player_score"],
        "monster_score": payload["monster_score"],
        "monster_stats": payload["monster_stats"],
        "profile": profile,
    }


@app.post("/game/fight/commit")
def game_fight_commit(
    body: FightCommitRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT fight_id, payload_json, created_at FROM pending_fights WHERE fight_id = ? AND user_id = ?",
            (body.fight_id.strip(), user_id),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="战斗会话不存在或已结算")
    try:
        created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - created > timedelta(minutes=20):
            conn = get_db()
            try:
                conn.execute("DELETE FROM pending_fights WHERE fight_id = ?", (body.fight_id.strip(),))
                conn.commit()
            finally:
                conn.close()
            raise HTTPException(status_code=400, detail="战斗会话已过期")
    except (TypeError, ValueError):
        pass
    try:
        payload: dict[str, Any] = json.loads(row["payload_json"])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="战斗数据损坏") from exc
    # 以实时战斗最终血量作为结算胜负依据，避免出现“已阵亡却判定胜利”。
    if body.player_hp is not None and body.monster_hp is not None:
        p_hp = max(0, int(body.player_hp))
        m_hp = max(0, int(body.monster_hp))
        payload["won"] = bool(m_hp <= 0 and p_hp > 0)
        payload["resolved_by_hp"] = True
    conn = get_db()
    try:
        conn.execute("DELETE FROM pending_fights WHERE fight_id = ?", (body.fight_id.strip(),))
        conn.commit()
    finally:
        conn.close()
    return apply_world_monster_fight_payload(user_id, payload)


@app.get("/game/balance/config")
def game_balance_config_list(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    assert_config_admin(authorization, x_admin_key)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT domain, key_name, value_json, updated_at FROM game_balance_config ORDER BY domain, key_name"
        ).fetchall()
    finally:
        conn.close()
    items: list[dict[str, Any]] = []
    for r in rows:
        value: Any
        try:
            value = json.loads(str(r["value_json"]))
        except (TypeError, json.JSONDecodeError):
            value = str(r["value_json"])
        items.append(
            {
                "domain": str(r["domain"]),
                "key_name": str(r["key_name"]),
                "value": value,
                "updated_at": str(r["updated_at"]),
            }
        )
    return {"items": items}


@app.post("/game/balance/config")
def game_balance_config_upsert(
    body: BalanceConfigUpsertRequest,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
) -> dict[str, Any]:
    assert_config_admin(authorization, x_admin_key)
    if not body.entries:
        raise HTTPException(status_code=400, detail="entries 不能为空")
    conn = get_db()
    try:
        for ent in body.entries:
            conn.execute(
                """
                INSERT INTO game_balance_config (domain, key_name, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, key_name) DO UPDATE
                SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (
                    ent.domain.strip(),
                    ent.key_name.strip(),
                    json.dumps(ent.value, ensure_ascii=False),
                    now_iso(),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "updated": len(body.entries)}


@app.post("/game/dungeon/event-roll")
def game_dungeon_event_roll(
    body: DungeonEventRollRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    get_user_id_from_header(authorization)
    node_type = body.node_type.strip().lower()
    if node_type not in {"treasure", "heal", "elite"}:
        raise HTTPException(status_code=400, detail="该节点类型不支持事件抽取")
    offer_count = int(get_balance_value("dungeon", "event_offer_count", 3))
    seed_num = (
        sum(ord(c) for c in body.dungeon_id.strip())
        + body.room_index * 997
        + len(body.chosen_event_ids) * 313
    )
    options = roll_weighted_event_options(
        node_type=node_type,
        chosen_event_ids=body.chosen_event_ids,
        offer_count=offer_count,
        seed_num=seed_num,
    )
    return {
        "ok": True,
        "dungeon_id": body.dungeon_id.strip(),
        "room_index": body.room_index,
        "node_type": node_type,
        "options": options,
    }


@app.get("/game/skills/shop")
def game_skills_shop(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        owned = {
            str(r["skill_id"])
            for r in conn.execute("SELECT skill_id FROM player_skills WHERE user_id = ?", (user_id,)).fetchall()
        }
        rows, refresh_count = get_skill_shop_offers(conn, user_id)
        items = []
        for r in rows:
            rr = dict(r)
            items.append(
                {
                    **rr,
                    "owned": str(rr["skill_id"]) in owned,
                }
            )
        base_cost = int(balance_value_from_conn(conn, "shop", "refresh_base_cost", 120))
        step_cost = int(balance_value_from_conn(conn, "shop", "refresh_step_cost", 90))
        refresh_cost = base_cost + refresh_count * step_cost
    finally:
        conn.close()
    return {"skills": items, "refresh_cost": refresh_cost}


@app.post("/game/skills/buy")
def game_skills_buy(
    body: BuySkillRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        sk = conn.execute(
            "SELECT skill_id, name, gold_price, drop_only FROM game_skills WHERE skill_id = ?",
            (body.skill_id.strip(),),
        ).fetchone()
        if not sk or int(sk["gold_price"]) <= 0 or int(sk["drop_only"]) == 1:
            raise HTTPException(status_code=400, detail="该技能不可在商店购买")
        offers, _ = get_skill_shop_offers(conn, user_id)
        offer_ids = {str(o["skill_id"]) for o in offers}
        if str(sk["skill_id"]) not in offer_ids:
            raise HTTPException(status_code=400, detail="该技能不在本轮商店，请刷新后再试")
        exists = conn.execute(
            "SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, sk["skill_id"]),
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="已拥有该技能")
        w = conn.execute("SELECT gold FROM player_wallet WHERE user_id = ?", (user_id,)).fetchone()
        gold = int(w["gold"]) if w else 0
        price = int(sk["gold_price"])
        if gold < price:
            raise HTTPException(status_code=400, detail="金币不足")
        conn.execute("UPDATE player_wallet SET gold = gold - ? WHERE user_id = ?", (price, user_id))
        conn.execute(
            "INSERT INTO player_skills (user_id, skill_id, created_at) VALUES (?, ?, ?)",
            (user_id, sk["skill_id"], now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "skill_id": body.skill_id.strip(), "profile": get_player_profile(user_id)}


@app.post("/game/skills/loadout")
def game_skills_save_loadout(
    body: SkillLoadoutSaveRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    profile = get_player_profile(user_id)
    unlocks: list[bool] = list(profile.get("skill_slots_unlocked") or [False] * 6)
    conn = get_db()
    try:
        owned = {
            str(r["skill_id"])
            for r in conn.execute("SELECT skill_id FROM player_skills WHERE user_id = ?", (user_id,)).fetchall()
        }
        for ent in body.slots:
            idx = int(ent.slot_index)
            if idx < 0 or idx > 5:
                raise HTTPException(status_code=400, detail="技能栏位非法")
            if not unlocks[idx]:
                raise HTTPException(status_code=400, detail=f"部位 {SLOT_LABELS_CN.get(SLOT_ORDER[idx], SLOT_ORDER[idx])} 需史诗及以上装备才解锁技能栏")
            sid = ent.skill_id.strip() if ent.skill_id else None
            if sid:
                if sid not in owned:
                    raise HTTPException(status_code=400, detail="未拥有该技能")
                meta = conn.execute(
                    "SELECT allowed_slot FROM game_skills WHERE skill_id = ?",
                    (sid,),
                ).fetchone()
                if not meta:
                    raise HTTPException(status_code=404, detail="技能不存在")
                al = str(meta["allowed_slot"])
                if al != "any" and al != SLOT_ORDER[idx]:
                    raise HTTPException(status_code=400, detail="该技能不能装备在此部位栏位")
            conn.execute(
                "INSERT INTO player_skill_loadout (user_id, slot_index, skill_id) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, slot_index) DO UPDATE SET skill_id = excluded.skill_id",
                (user_id, idx, sid),
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "profile": get_player_profile(user_id)}


@app.post("/game/skills/refresh")
def game_skills_refresh(
    body: SkillShopRefreshRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    if not body.force:
        return game_skills_shop(authorization)
    conn = get_db()
    try:
        st = conn.execute(
            "SELECT refresh_count, refresh_seed FROM player_skill_shop_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        refresh_count = int(st["refresh_count"]) if st else 0
        refresh_seed = int(st["refresh_seed"]) if st else 0
        base_cost = int(balance_value_from_conn(conn, "shop", "refresh_base_cost", 120))
        step_cost = int(balance_value_from_conn(conn, "shop", "refresh_step_cost", 90))
        cost = base_cost + refresh_count * step_cost
        w = conn.execute("SELECT gold FROM player_wallet WHERE user_id = ?", (user_id,)).fetchone()
        gold = int(w["gold"]) if w else 0
        if gold < cost:
            raise HTTPException(status_code=400, detail=f"金币不足，刷新需要 {cost}")
        conn.execute("UPDATE player_wallet SET gold = gold - ? WHERE user_id = ?", (cost, user_id))
        next_seed = refresh_seed + 1
        conn.execute(
            """
            INSERT INTO player_skill_shop_state (user_id, refresh_count, refresh_seed, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE
            SET refresh_count = excluded.refresh_count, refresh_seed = excluded.refresh_seed, updated_at = excluded.updated_at
            """,
            (user_id, refresh_count + 1, next_seed, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "spent_gold": cost, **game_skills_shop(authorization)}


@app.post("/game/skills/specialize")
def game_skills_specialize(
    body: SkillSpecializeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    branch = body.branch.strip().lower()
    if branch not in {"burst", "sustain", "control"}:
        raise HTTPException(status_code=400, detail="专精分支仅支持 burst / sustain / control")
    conn = get_db()
    try:
        own = conn.execute(
            "SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?",
            (user_id, body.skill_id.strip()),
        ).fetchone()
        if not own:
            raise HTTPException(status_code=404, detail="未拥有该技能")
        row = conn.execute(
            "SELECT mastery_exp FROM player_skill_mastery WHERE user_id = ? AND skill_id = ?",
            (user_id, body.skill_id.strip()),
        ).fetchone()
        exp = int(row["mastery_exp"]) if row else 0
        if mastery_level(exp) < 2:
            raise HTTPException(status_code=400, detail="技能熟练度不足，至少达到Lv2可切换专精")
        conn.execute(
            """
            INSERT INTO player_skill_mastery (user_id, skill_id, mastery_exp, branch)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, skill_id) DO UPDATE SET branch = excluded.branch
            """,
            (user_id, body.skill_id.strip(), exp, branch),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "profile": get_player_profile(user_id)}


@app.get("/game/skills/mastery")
def game_skills_mastery(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    profile = get_player_profile(user_id)
    return {
        "skills": [
            {
                "skill_id": s.get("skill_id"),
                "name": s.get("name"),
                "branch": s.get("branch"),
                "mastery_exp": int(s.get("mastery_exp") or 0),
                "mastery_level": int(s.get("mastery_level") or 0),
            }
            for s in (profile.get("owned_skills") or [])
        ]
    }


@app.post("/game/skills/scrap")
def game_skills_scrap(
    body: SkillScrapRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    sid = body.skill_id.strip()
    if sid in {"SK_W_SLASH", "SK_H_FOCUS", "SK_C_FORT", "SK_G_STORM", "SK_P_SHADOW", "SK_B_RUSH"}:
        raise HTTPException(status_code=400, detail="基础技能不可分解")
    conn = get_db()
    try:
        own = conn.execute("SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?", (user_id, sid)).fetchone()
        if not own:
            raise HTTPException(status_code=404, detail="未拥有该技能")
        conn.execute("DELETE FROM player_skills WHERE user_id = ? AND skill_id = ?", (user_id, sid))
        conn.execute("UPDATE player_skill_loadout SET skill_id = NULL WHERE user_id = ? AND skill_id = ?", (user_id, sid))
        conn.execute("DELETE FROM player_skill_mastery WHERE user_id = ? AND skill_id = ?", (user_id, sid))
        shard_gain = int(balance_value_from_conn(conn, "shop", "skill_scrap_shard_gain", 12))
        conn.execute("UPDATE player_wallet SET skill_shard = skill_shard + ? WHERE user_id = ?", (shard_gain, user_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "skill_id": sid, "gained_skill_shard": shard_gain, "profile": get_player_profile(user_id)}


@app.post("/game/skills/exchange")
def game_skills_exchange(
    body: SkillExchangeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    sid = body.skill_id.strip()
    conn = get_db()
    try:
        sk = conn.execute(
            "SELECT skill_id, drop_only FROM game_skills WHERE skill_id = ?",
            (sid,),
        ).fetchone()
        if not sk or int(sk["drop_only"]) != 1:
            raise HTTPException(status_code=400, detail="仅支持兑换Boss掉落技能")
        own = conn.execute("SELECT 1 FROM player_skills WHERE user_id = ? AND skill_id = ?", (user_id, sid)).fetchone()
        if own:
            raise HTTPException(status_code=409, detail="已拥有该技能")
        w = conn.execute("SELECT skill_shard FROM player_wallet WHERE user_id = ?", (user_id,)).fetchone()
        shard = int(w["skill_shard"]) if w else 0
        cost = int(balance_value_from_conn(conn, "shop", "skill_exchange_shard_cost", 30))
        if shard < cost:
            raise HTTPException(status_code=400, detail=f"技能碎片不足，需要 {cost}")
        conn.execute("UPDATE player_wallet SET skill_shard = skill_shard - ? WHERE user_id = ?", (cost, user_id))
        conn.execute(
            "INSERT INTO player_skills (user_id, skill_id, created_at) VALUES (?, ?, ?)",
            (user_id, sid, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "skill_id": sid, "spent_skill_shard": cost, "profile": get_player_profile(user_id)}


@app.post("/game/sell/batch")
def game_sell_batch(
    body: BatchSellRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    if body.min_level > body.max_level:
        raise HTTPException(status_code=400, detail="等级区间错误")
    allowed_qualities = {"普通", "优秀", "精良", "史诗", "传奇", "神话"}
    picked = [q for q in body.qualities if q in allowed_qualities]
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT pi.id AS inventory_id, pi.quantity, pi.equipped, pi.affix_json, pi.bonus_attack, pi.bonus_defense, pi.bonus_crit_damage, pi.bonus_freeze,
                   gi.item_id, gi.name, gi.category, gi.quality, gi.level_required, gi.power
            FROM player_inventory pi
            JOIN game_items gi ON gi.item_id = pi.item_id
            WHERE pi.user_id = ? AND gi.level_required BETWEEN ? AND ?
            """,
            (user_id, body.min_level, body.max_level),
        ).fetchall()
        total_gold = 0
        sold_count = 0
        sold_items: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            if str(item.get("category")) != body.category:
                continue
            if picked and str(item.get("quality")) not in picked:
                continue
            if not body.include_equipped and int(item.get("equipped") or 0) == 1:
                continue
            try:
                item["affixes"] = json.loads(item.get("affix_json") or "[]")
            except json.JSONDecodeError:
                item["affixes"] = []
            price_each = item_sell_price(item)
            qty = int(item.get("quantity") or 1)
            gain = price_each * qty
            total_gold += gain
            sold_count += qty
            sold_items.append({"name": item["name"], "quantity": qty, "gold": gain})
            conn.execute("DELETE FROM player_inventory WHERE id = ? AND user_id = ?", (item["inventory_id"], user_id))
        if total_gold > 0:
            conn.execute("UPDATE player_wallet SET gold = gold + ? WHERE user_id = ?", (total_gold, user_id))
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "sold_count": sold_count,
        "total_gold": total_gold,
        "sold_preview": sold_items[:12],
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
    layout = DUNGEON_NODE_LAYOUTS.get(body.dungeon_id, DUNGEON_NODE_LAYOUTS["DUN30"])
    if body.current_room_index < len(layout) - 1:
        return {"ok": False, "reason": "副本流程未完成，请推进到Boss房后再结算"}

    # 服务端根据玩家选择重算事件加成，忽略客户端直接上传的加成值，避免篡改。
    clear_rate_bonus = 0.0
    reward_bonus = 0.0
    boss_scale_delta = 0.0
    curse_value = 0.0
    greed_value = 0.0
    chosen_history: list[str] = []
    offer_count = int(get_balance_value("dungeon", "event_offer_count", 3))
    for idx, node_type in enumerate(layout):
        if node_type not in {"treasure", "heal", "elite"}:
            continue
        chosen_id = str((body.event_choices or {}).get(str(idx), "")).strip()
        if not chosen_id:
            return {"ok": False, "reason": f"第{idx + 1}房事件未选择，无法结算"}
        seed_num = sum(ord(c) for c in body.dungeon_id.strip()) + idx * 997 + len(chosen_history) * 313
        options = roll_weighted_event_options(node_type=node_type, chosen_event_ids=chosen_history, offer_count=offer_count, seed_num=seed_num)
        picked = None
        for op in options:
            if str(op.get("id")) == chosen_id:
                picked = op
                break
        if not picked:
            return {"ok": False, "reason": f"第{idx + 1}房事件选择无效（已重置，请重进副本）"}
        effect = picked.get("effect") or {}
        clear_rate_bonus += float(effect.get("clearRateBonus") or 0.0)
        reward_bonus += float(effect.get("rewardBonus") or 0.0)
        boss_scale_delta += float(effect.get("bossScaleDelta") or 0.0)
        curse_value += float(effect.get("curseValue") or 0.0)
        greed_value += float(effect.get("greedValue") or 0.0)
        chosen_history.append(chosen_id)

    clear_rate_bonus = max(-0.25, min(0.25, clear_rate_bonus))
    reward_bonus = max(-0.3, min(0.5, reward_bonus))
    boss_scale_delta = max(-0.25, min(0.25, boss_scale_delta))
    curse_value = max(0.0, min(1.5, curse_value))
    greed_value = max(0.0, min(1.5, greed_value))
    risk_scale = 1 + curse_value * 0.16 + greed_value * 0.08
    dungeon_scale = {30: 4.8, 40: 7.2, 50: 9.2}.get(target_level, 5.0) * (1 + boss_scale_delta) * risk_scale
    boss_stats = build_combat_snapshot(target_level, dungeon_scale)
    boss_mechanic = resolve_boss_mechanic(dungeon_id=body.dungeon_id)
    if boss_mechanic["id"] == "shield_phase":
        boss_stats["defense"] = int(boss_stats["defense"] * 1.2)
    elif boss_mechanic["id"] == "summon_phase":
        boss_stats["attack"] = int(boss_stats["attack"] * 1.15)
    elif boss_mechanic["id"] == "enrage_phase":
        boss_stats["attack"] = int(boss_stats["attack"] * 1.22)
        boss_stats["hp"] = int(boss_stats["hp"] * 1.1)
    player_score = calculate_combat_score(profile["total_stats"]) + len(profile["active_bonuses"]) * 24
    boss_score = calculate_combat_score(boss_stats)
    clear_rate = max(0.02, min(0.95, 0.05 + (player_score / max(1, boss_score)) * 0.5 + clear_rate_bonus - curse_value * 0.04))
    if not body.cleared:
        fail_exp = int((target_level * 2.2) * (1 + max(0.0, (profile["level"] - target_level) * 0.012)))
        add_player_exp(user_id, fail_exp)
        add_wallet_values(user_id, gold=int(target_level * 10))
        return {
            "ok": True,
            "cleared": False,
            "clear_rate_estimate": round(clear_rate, 3),
            "boss_stats": boss_stats,
            "rewards": {"exp": fail_exp, "gold": int(target_level * 10)},
            "mechanic": boss_mechanic,
            "profile": get_player_profile(user_id),
        }

    # 改为确定性判定，减少“随机输赢”并让养成/流程选择更可预期。
    if clear_rate < 0.5:
        fail_exp = int((target_level * 2.8) * (1 + max(0.0, (profile["level"] - target_level) * 0.012)))
        add_player_exp(user_id, fail_exp)
        add_wallet_values(user_id, gold=int(target_level * 12))
        return {
            "ok": True,
            "cleared": False,
            "reason": "属性不足，副本首领将你击退",
            "clear_rate_estimate": round(clear_rate, 3),
            "boss_stats": boss_stats,
            "rewards": {"exp": fail_exp, "gold": int(target_level * 12)},
            "mechanic": boss_mechanic,
            "profile": get_player_profile(user_id),
        }

    level_scale = 1 + max(0.0, (profile["level"] - target_level) * 0.015)
    exp_gain = int((target_level * 7.5 + 140) * level_scale * (1 + reward_bonus + greed_value * 0.12))
    gold_gain = int((target_level * 22 + 200) * (1 + reward_bonus + greed_value * 0.18))
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

    skill_sid: str | None = None
    conn = get_db()
    try:
        skill_sid = roll_dungeon_skill_drop(conn, user_id)
        if skill_sid:
            conn.execute(
                "INSERT INTO player_skills (user_id, skill_id, created_at) VALUES (?, ?, ?)",
                (user_id, skill_sid, now_iso()),
            )
            conn.commit()
        add_mastery_exp_for_loadout(conn, user_id, 18)
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "cleared": True,
        "dungeon_id": body.dungeon_id,
        "clear_rate_estimate": round(clear_rate, 3),
        "boss_stats": boss_stats,
        "mechanic": boss_mechanic,
        "risk_track": {"curse": round(curse_value, 3), "greed": round(greed_value, 3)},
        "rewards": {"exp": exp_gain, "gold": gold_gain, "items": drops, "skill_id": skill_sid},
        "profile": get_player_profile(user_id),
    }


@app.post("/game/dungeon/engage")
def game_dungeon_engage(
    body: DungeonEngageRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    gate = game_dungeon_challenge(DungeonChallengeRequest(dungeon_id=body.dungeon_id), authorization)
    if not gate["ok"]:
        return {"ok": False, "reason": "未满足副本挑战门槛", "gate": gate}
    layout = DUNGEON_NODE_LAYOUTS.get(body.dungeon_id, DUNGEON_NODE_LAYOUTS["DUN30"])
    if body.current_room_index < len(layout) - 1:
        return {"ok": False, "reason": "请先推进到Boss房再发起实时副本战斗"}

    clear_rate_bonus = 0.0
    reward_bonus = 0.0
    boss_scale_delta = 0.0
    curse_value = 0.0
    greed_value = 0.0
    chosen_history: list[str] = []
    offer_count = int(get_balance_value("dungeon", "event_offer_count", 3))
    for idx, node_type in enumerate(layout):
        if node_type not in {"treasure", "heal", "elite"}:
            continue
        chosen_id = str((body.event_choices or {}).get(str(idx), "")).strip()
        if not chosen_id:
            return {"ok": False, "reason": f"第{idx + 1}房事件未选择，无法发起Boss战"}
        seed_num = sum(ord(c) for c in body.dungeon_id.strip()) + idx * 997 + len(chosen_history) * 313
        options = roll_weighted_event_options(node_type=node_type, chosen_event_ids=chosen_history, offer_count=offer_count, seed_num=seed_num)
        picked = None
        for op in options:
            if str(op.get("id")) == chosen_id:
                picked = op
                break
        if not picked:
            return {"ok": False, "reason": f"第{idx + 1}房事件选择无效（请重进副本）"}
        effect = picked.get("effect") or {}
        clear_rate_bonus += float(effect.get("clearRateBonus") or 0.0)
        reward_bonus += float(effect.get("rewardBonus") or 0.0)
        boss_scale_delta += float(effect.get("bossScaleDelta") or 0.0)
        curse_value += float(effect.get("curseValue") or 0.0)
        greed_value += float(effect.get("greedValue") or 0.0)
        chosen_history.append(chosen_id)

    clear_rate_bonus = max(-0.25, min(0.25, clear_rate_bonus))
    reward_bonus = max(-0.3, min(0.5, reward_bonus))
    boss_scale_delta = max(-0.25, min(0.25, boss_scale_delta))
    curse_value = max(0.0, min(1.5, curse_value))
    greed_value = max(0.0, min(1.5, greed_value))

    dungeon = gate["dungeon"]
    target_level = int(dungeon["recommended_level"])
    risk_scale = 1 + curse_value * 0.16 + greed_value * 0.08
    dungeon_scale = {30: 4.8, 40: 7.2, 50: 9.2}.get(target_level, 5.0) * (1 + boss_scale_delta) * risk_scale
    boss_stats = build_combat_snapshot(target_level, dungeon_scale)
    boss_mechanic = resolve_boss_mechanic(dungeon_id=body.dungeon_id)
    if boss_mechanic["id"] == "shield_phase":
        boss_stats["defense"] = int(boss_stats["defense"] * 1.2)
    elif boss_mechanic["id"] == "summon_phase":
        boss_stats["attack"] = int(boss_stats["attack"] * 1.15)
    elif boss_mechanic["id"] == "enrage_phase":
        boss_stats["attack"] = int(boss_stats["attack"] * 1.22)
        boss_stats["hp"] = int(boss_stats["hp"] * 1.1)

    profile = get_player_profile(user_id)
    player_stats = profile["total_stats"]
    player_score = calculate_combat_score(player_stats) + len(profile["active_bonuses"]) * 24
    boss_score = calculate_combat_score(boss_stats)
    ratio = player_score / max(1, boss_score) if player_score > 0 else 0.0
    clear_rate = max(0.02, min(0.95, 0.05 + ratio * 0.5 + clear_rate_bonus - curse_value * 0.04))

    p_max = int(player_stats["hp"])
    m_max = int(max(boss_stats["hp"], 260) * 4 + int(boss_stats["attack"]) * 2)
    fight_payload: dict[str, Any] = {
        "version": 1,
        "mode": "dungeon",
        "dungeon_id": body.dungeon_id,
        "target_level": target_level,
        "reward_bonus": reward_bonus,
        "curse_value": curse_value,
        "greed_value": greed_value,
        "clear_rate_estimate": clear_rate,
        "boss_stats": boss_stats,
        "boss_mechanic": boss_mechanic,
    }
    fight_id = str(uuid.uuid4())
    conn = get_db()
    try:
        conn.execute("DELETE FROM pending_fights WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO pending_fights (fight_id, user_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (fight_id, user_id, json.dumps(fight_payload, ensure_ascii=False), now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "fight_mode": "dungeon",
        "fight_id": fight_id,
        "dungeon_id": body.dungeon_id,
        "balance": battle_balance_mods(ratio),
        "monster": {
            "type": "副本Boss",
            "name": str(dungeon["name"]),
            "max_hp": m_max,
            "attack": int(boss_stats["attack"]),
            "defense": int(boss_stats["defense"]),
            "skills": monster_skill_templates("地图Boss"),
            "ai": monster_ai_profile("地图Boss"),
            "mechanic": boss_mechanic,
        },
        "player": {
            "max_hp": p_max,
            "attack": int(player_stats["attack"]),
            "defense": int(player_stats["defense"]),
            "basic_cd_ms": player_basic_cd_ms(int(player_stats["attack"])),
            "skill_bar": profile.get("skill_loadout") or [],
        },
        "win_rate_estimate": round(clear_rate, 3),
    }


@app.post("/game/dungeon/commit")
def game_dungeon_commit(
    body: FightCommitRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = get_user_id_from_header(authorization)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT fight_id, payload_json, created_at FROM pending_fights WHERE fight_id = ? AND user_id = ?",
            (body.fight_id.strip(), user_id),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="副本战斗会话不存在或已结算")
    payload = json.loads(row["payload_json"])
    if str(payload.get("mode")) != "dungeon":
        raise HTTPException(status_code=400, detail="战斗会话类型错误")
    if body.player_hp is None or body.monster_hp is None:
        raise HTTPException(status_code=400, detail="副本结算需提交实时HP")
    won = bool(int(body.monster_hp) <= 0 and int(body.player_hp) > 0)
    conn = get_db()
    try:
        conn.execute("DELETE FROM pending_fights WHERE fight_id = ?", (body.fight_id.strip(),))
        conn.commit()
    finally:
        conn.close()

    target_level = int(payload.get("target_level") or 30)
    reward_bonus = float(payload.get("reward_bonus") or 0.0)
    greed_value = float(payload.get("greed_value") or 0.0)
    if won:
        profile = get_player_profile(user_id)
        level_scale = 1 + max(0.0, (profile["level"] - target_level) * 0.015)
        exp_gain = int((target_level * 7.5 + 140) * level_scale * (1 + reward_bonus + greed_value * 0.12))
        gold_gain = int((target_level * 22 + 200) * (1 + reward_bonus + greed_value * 0.18))
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
            item = choose_drop_item(target_level, "boss_dungeon")
            if item:
                item = grant_item(user_id, item["item_id"], equipped=0, item_data=item)
                drops.append(item)
                if item["quality"] == "史诗":
                    add_wallet_values(user_id, epic_shard=2)
        skill_sid: str | None = None
        conn = get_db()
        try:
            skill_sid = roll_dungeon_skill_drop(conn, user_id)
            if skill_sid:
                conn.execute(
                    "INSERT INTO player_skills (user_id, skill_id, created_at) VALUES (?, ?, ?)",
                    (user_id, skill_sid, now_iso()),
                )
            add_mastery_exp_for_loadout(conn, user_id, 20)
            conn.commit()
        finally:
            conn.close()
        return {
            "ok": True,
            "cleared": True,
            "dungeon_id": str(payload.get("dungeon_id") or ""),
            "mechanic": payload.get("boss_mechanic"),
            "clear_rate_estimate": float(payload.get("clear_rate_estimate") or 0.0),
            "rewards": {"exp": exp_gain, "gold": gold_gain, "items": drops, "skill_id": skill_sid},
            "profile": get_player_profile(user_id),
        }

    fail_exp = int(target_level * 2.8)
    add_player_exp(user_id, fail_exp)
    add_wallet_values(user_id, gold=int(target_level * 12))
    return {
        "ok": True,
        "cleared": False,
        "reason": "你在实时副本战斗中被击退",
        "dungeon_id": str(payload.get("dungeon_id") or ""),
        "mechanic": payload.get("boss_mechanic"),
        "clear_rate_estimate": float(payload.get("clear_rate_estimate") or 0.0),
        "rewards": {"exp": fail_exp, "gold": int(target_level * 12)},
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
