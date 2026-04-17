import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";

const API_BASE = "https://chat-mobile-backend-production.up.railway.app";
const WS_BASE = "wss://chat-mobile-backend-production.up.railway.app/ws";

const GAME_MAPS = [
  { map_id: "M01", name: "雾隐林地", label: "雾隐林地(1-12)" },
  { map_id: "M02", name: "断碑荒原", label: "断碑荒原(13-22)" },
  { map_id: "M03", name: "黑岩峡谷", label: "黑岩峡谷(23-32)" },
  { map_id: "M04", name: "霜骸墓园", label: "霜骸墓园(33-42)" },
  { map_id: "M05", name: "深渊边庭", label: "深渊边庭(43-50)" },
];

const MONSTER_TYPES = [
  { type: "普通怪", shortLabel: "流寇群", label: "游荡魔群" },
  { type: "精英怪", shortLabel: "精英首目", label: "异化首目" },
  { type: "地图Boss", shortLabel: "区域领主", label: "区域领主" },
];
const DUNGEONS = [
  { id: "DUN30", name: "黑岩熔炉" },
  { id: "DUN40", name: "霜骨王庭" },
  { id: "DUN50", name: "深渊裂隙" },
];

const DUNGEON_ENCOUNTERS = {
  DUN30: { trash: "灰烬铸奴", elite: "熔链监工", boss: "熔炉之心·格罗姆" },
  DUN40: { trash: "霜庭遗臣", elite: "寒冠行刑者", boss: "霜王遗骸·维尔萨" },
  DUN50: { trash: "裂隙吞徒", elite: "深渊司判", boss: "裂界魔君·阿扎克" },
};

const DUNGEON_BACKGROUNDS = {
  DUN30: require("./assets/dungeons/backgrounds/DUN30.png"),
  DUN40: require("./assets/dungeons/backgrounds/DUN40.png"),
  DUN50: require("./assets/dungeons/backgrounds/DUN50.png"),
};

const DUNGEON_BOSS_IMAGES = {
  DUN30: require("./assets/dungeons/bosses/DUN30.png"),
  DUN40: require("./assets/dungeons/bosses/DUN40.png"),
  DUN50: require("./assets/dungeons/bosses/DUN50.png"),
};

const DUNGEON_NODE_ICONS = {
  normal: require("./assets/dungeons/nodes/normal.png"),
  elite: require("./assets/dungeons/nodes/elite.png"),
  treasure: require("./assets/dungeons/nodes/treasure.png"),
  heal: require("./assets/dungeons/nodes/heal.png"),
  boss: require("./assets/dungeons/nodes/boss.png"),
};
const MONSTER_PORTRAITS = {
  "普通怪": require("./assets/dungeons/nodes/normal.png"),
  "精英怪": require("./assets/dungeons/nodes/elite.png"),
  "地图Boss": require("./assets/dungeons/nodes/boss.png"),
};

const DUNGEON_NODE_LAYOUTS = {
  DUN30: ["normal", "elite", "treasure", "heal", "boss"],
  DUN40: ["normal", "normal", "elite", "treasure", "boss"],
  DUN50: ["normal", "elite", "heal", "elite", "boss"],
};

const NODE_TYPE_LABELS = {
  normal: "战斗房",
  elite: "精英房",
  treasure: "宝箱房",
  heal: "恢复房",
  boss: "Boss房",
};

const MAP_MONSTER_NAMES = {
  M01: { "普通怪": "雾牙幼兽", "精英怪": "腐爪监视者", "地图Boss": "迷雾树心魔" },
  M02: { "普通怪": "断碑掠夺者", "精英怪": "荒原血鬃", "地图Boss": "碎碑战将" },
  M03: { "普通怪": "黑岩蛮卒", "精英怪": "熔痕督军", "地图Boss": "裂炉巨像" },
  M04: { "普通怪": "霜墓巡魂", "精英怪": "寒棺守卫", "地图Boss": "白骨霜后" },
  M05: { "普通怪": "渊庭魔仆", "精英怪": "裂隙执刑官", "地图Boss": "边庭深渊主" },
};

const BASE_SHARED_ICONS = {
  weapon: require("./assets/equipment/base/shared/weapon.png"),
  helmet: require("./assets/equipment/base/shared/helmet.png"),
  chest: require("./assets/equipment/base/shared/chest.png"),
  gloves: require("./assets/equipment/base/shared/gloves.png"),
  pants: require("./assets/equipment/base/shared/pants.png"),
  boots: require("./assets/equipment/base/shared/boots.png"),
};

const EPIC_SET_ICONS = {
  set30_arc: {
    weapon: require("./assets/equipment/epic/set30_arc/weapon.png"),
    helmet: require("./assets/equipment/epic/set30_arc/helmet.png"),
    chest: require("./assets/equipment/epic/set30_arc/chest.png"),
    gloves: require("./assets/equipment/epic/set30_arc/gloves.png"),
    pants: require("./assets/equipment/epic/set30_arc/pants.png"),
    boots: require("./assets/equipment/epic/set30_arc/boots.png"),
  },
  set30_hunt: {
    weapon: require("./assets/equipment/epic/set30_hunt/weapon.png"),
    helmet: require("./assets/equipment/epic/set30_hunt/helmet.png"),
    chest: require("./assets/equipment/epic/set30_hunt/chest.png"),
    gloves: require("./assets/equipment/epic/set30_hunt/gloves.png"),
    pants: require("./assets/equipment/epic/set30_hunt/pants.png"),
    boots: require("./assets/equipment/epic/set30_hunt/boots.png"),
  },
  set30_iron: {
    weapon: require("./assets/equipment/epic/set30_iron/weapon.png"),
    helmet: require("./assets/equipment/epic/set30_iron/helmet.png"),
    chest: require("./assets/equipment/epic/set30_iron/chest.png"),
    gloves: require("./assets/equipment/epic/set30_iron/gloves.png"),
    pants: require("./assets/equipment/epic/set30_iron/pants.png"),
    boots: require("./assets/equipment/epic/set30_iron/boots.png"),
  },
  set30_pal: {
    weapon: require("./assets/equipment/epic/set30_pal/weapon.png"),
    helmet: require("./assets/equipment/epic/set30_pal/helmet.png"),
    chest: require("./assets/equipment/epic/set30_pal/chest.png"),
    gloves: require("./assets/equipment/epic/set30_pal/gloves.png"),
    pants: require("./assets/equipment/epic/set30_pal/pants.png"),
    boots: require("./assets/equipment/epic/set30_pal/boots.png"),
  },
  set40_arc: {
    weapon: require("./assets/equipment/epic/set40_arc/weapon.png"),
    helmet: require("./assets/equipment/epic/set40_arc/helmet.png"),
    chest: require("./assets/equipment/epic/set40_arc/chest.png"),
    gloves: require("./assets/equipment/epic/set40_arc/gloves.png"),
    pants: require("./assets/equipment/epic/set40_arc/pants.png"),
    boots: require("./assets/equipment/epic/set40_arc/boots.png"),
  },
  set40_hunt: {
    weapon: require("./assets/equipment/epic/set40_hunt/weapon.png"),
    helmet: require("./assets/equipment/epic/set40_hunt/helmet.png"),
    chest: require("./assets/equipment/epic/set40_hunt/chest.png"),
    gloves: require("./assets/equipment/epic/set40_hunt/gloves.png"),
    pants: require("./assets/equipment/epic/set40_hunt/pants.png"),
    boots: require("./assets/equipment/epic/set40_hunt/boots.png"),
  },
  set40_iron: {
    weapon: require("./assets/equipment/epic/set40_iron/weapon.png"),
    helmet: require("./assets/equipment/epic/set40_iron/helmet.png"),
    chest: require("./assets/equipment/epic/set40_iron/chest.png"),
    gloves: require("./assets/equipment/epic/set40_iron/gloves.png"),
    pants: require("./assets/equipment/epic/set40_iron/pants.png"),
    boots: require("./assets/equipment/epic/set40_iron/boots.png"),
  },
  set40_pal: {
    weapon: require("./assets/equipment/epic/set40_pal/weapon.png"),
    helmet: require("./assets/equipment/epic/set40_pal/helmet.png"),
    chest: require("./assets/equipment/epic/set40_pal/chest.png"),
    gloves: require("./assets/equipment/epic/set40_pal/gloves.png"),
    pants: require("./assets/equipment/epic/set40_pal/pants.png"),
    boots: require("./assets/equipment/epic/set40_pal/boots.png"),
  },
  set50_arc: {
    weapon: require("./assets/equipment/epic/set50_arc/weapon.png"),
    helmet: require("./assets/equipment/epic/set50_arc/helmet.png"),
    chest: require("./assets/equipment/epic/set50_arc/chest.png"),
    gloves: require("./assets/equipment/epic/set50_arc/gloves.png"),
    pants: require("./assets/equipment/epic/set50_arc/pants.png"),
    boots: require("./assets/equipment/epic/set50_arc/boots.png"),
  },
  set50_hunt: {
    weapon: require("./assets/equipment/epic/set50_hunt/weapon.png"),
    helmet: require("./assets/equipment/epic/set50_hunt/helmet.png"),
    chest: require("./assets/equipment/epic/set50_hunt/chest.png"),
    gloves: require("./assets/equipment/epic/set50_hunt/gloves.png"),
    pants: require("./assets/equipment/epic/set50_hunt/pants.png"),
    boots: require("./assets/equipment/epic/set50_hunt/boots.png"),
  },
  set50_iron: {
    weapon: require("./assets/equipment/epic/set50_iron/weapon.png"),
    helmet: require("./assets/equipment/epic/set50_iron/helmet.png"),
    chest: require("./assets/equipment/epic/set50_iron/chest.png"),
    gloves: require("./assets/equipment/epic/set50_iron/gloves.png"),
    pants: require("./assets/equipment/epic/set50_iron/pants.png"),
    boots: require("./assets/equipment/epic/set50_iron/boots.png"),
  },
  set50_pal: {
    weapon: require("./assets/equipment/epic/set50_pal/weapon.png"),
    helmet: require("./assets/equipment/epic/set50_pal/helmet.png"),
    chest: require("./assets/equipment/epic/set50_pal/chest.png"),
    gloves: require("./assets/equipment/epic/set50_pal/gloves.png"),
    pants: require("./assets/equipment/epic/set50_pal/pants.png"),
    boots: require("./assets/equipment/epic/set50_pal/boots.png"),
  },
};

const resolveEquipmentIcon = (item) => {
  if (!item || item.category !== "equipment") return null;
  if (item.quality === "史诗" && item.set_key && EPIC_SET_ICONS[item.set_key]?.[item.slot]) {
    return EPIC_SET_ICONS[item.set_key][item.slot];
  }
  return BASE_SHARED_ICONS[item.slot] || null;
};

const SLOT_LABELS = {
  weapon: "武器",
  helmet: "头盔",
  chest: "胸甲",
  gloves: "手套",
  pants: "护腿",
  boots: "战靴",
};

const rewardTitleByQuality = (quality) => {
  if (quality === "史诗") return "史诗掉落";
  if (quality === "精良") return "精良掉落";
  if (quality === "优秀") return "优秀掉落";
  return "战利品";
};

const getMapName = (mapId) => GAME_MAPS.find((m) => m.map_id === mapId)?.name || mapId;

const getDungeonName = (dungeonId) => DUNGEONS.find((d) => d.id === dungeonId)?.name || dungeonId;

const getDungeonBossName = (dungeonId) => DUNGEON_ENCOUNTERS[dungeonId]?.boss || "副本首领";

const getDungeonEncounter = (dungeonId) =>
  DUNGEON_ENCOUNTERS[dungeonId] || { trash: "未知敌人", elite: "未知精英", boss: "未知首领" };

const getMonsterDisplayName = (mapId, monsterType) =>
  MAP_MONSTER_NAMES[mapId]?.[monsterType] || monsterType;

export default function App() {
  const [authMode, setAuthMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  const [connected, setConnected] = useState(false);
  const [appMode, setAppMode] = useState("chat");
  const [activeTab, setActiveTab] = useState("lobby");
  const [dmPeer, setDmPeer] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState([]);
  const [onlineUsers, setOnlineUsers] = useState([]);

  const [friends, setFriends] = useState([]);
  const [pendingFriends, setPendingFriends] = useState([]);
  const [groups, setGroups] = useState([]);
  const [friendUsernameInput, setFriendUsernameInput] = useState("");
  const [newGroupName, setNewGroupName] = useState("");
  const [inviteUsername, setInviteUsername] = useState("");
  const [socialLoading, setSocialLoading] = useState(false);

  const [gameLoading, setGameLoading] = useState(false);
  const [gameActionLog, setGameActionLog] = useState([]);
  const [gameProfile, setGameProfile] = useState(null);
  const [gameInventory, setGameInventory] = useState([]);
  const [inventoryCategoryFilter, setInventoryCategoryFilter] = useState("all");
  const [inventoryQualityFilter, setInventoryQualityFilter] = useState("all");
  const [batchSellMaxLevel, setBatchSellMaxLevel] = useState("20");
  const [batchSellQualities, setBatchSellQualities] = useState(["普通", "优秀"]);
  const [selectedMap, setSelectedMap] = useState("M01");
  const [selectedMonsterType, setSelectedMonsterType] = useState("普通怪");
  const [selectedDungeon, setSelectedDungeon] = useState("DUN30");
  const [selectedPool, setSelectedPool] = useState("normal");
  const [shopSkills, setShopSkills] = useState([]);
  const [skillRefreshCost, setSkillRefreshCost] = useState(120);
  const [fightUiVisible, setFightUiVisible] = useState(false);
  const [fightSnapshot, setFightSnapshot] = useState(null);
  const [fightPlayerHp, setFightPlayerHp] = useState(0);
  const [fightMonsterHp, setFightMonsterHp] = useState(0);
  const [fightLog, setFightLog] = useState([]);
  const [fightEnded, setFightEnded] = useState(false);
  const [fightCommitting, setFightCommitting] = useState(false);
  const [autoBasicEnabled, setAutoBasicEnabled] = useState(true);
  const [basicReadyAt, setBasicReadyAt] = useState(0);
  const [skillReadyAts, setSkillReadyAts] = useState(Array(6).fill(0));
  const [monsterSkillReadyAts, setMonsterSkillReadyAts] = useState([]);
  const [playerActionLockedUntil, setPlayerActionLockedUntil] = useState(0);
  const [monsterComboBasicCount, setMonsterComboBasicCount] = useState(0);
  const [floatingTexts, setFloatingTexts] = useState([]);
  const [fightNow, setFightNow] = useState(Date.now());
  const [skillPickerVisible, setSkillPickerVisible] = useState(false);
  const [skillPickerSlot, setSkillPickerSlot] = useState(null);
  const [dungeonUiVisible, setDungeonUiVisible] = useState(false);
  const [dungeonRoomIndex, setDungeonRoomIndex] = useState(0);
  const [dungeonEventState, setDungeonEventState] = useState({});
  const [dungeonEventOptions, setDungeonEventOptions] = useState({});
  const [dungeonRunMods, setDungeonRunMods] = useState({
    clearRateBonus: 0,
    rewardBonus: 0,
    bossScaleDelta: 0,
    curseValue: 0,
    greedValue: 0,
  });
  const [, setLatestLootItems] = useState([]);
  const [, setLatestDrawRewards] = useState([]);
  const [equipModalSlot, setEquipModalSlot] = useState("");
  const [equipModalVisible, setEquipModalVisible] = useState(false);
  const [resultModalVisible, setResultModalVisible] = useState(false);
  const [resultModalTitle, setResultModalTitle] = useState("");
  const [resultModalItems, setResultModalItems] = useState([]);
  const [resultModalSummary, setResultModalSummary] = useState([]);
  const [gachaRevealPhase, setGachaRevealPhase] = useState("revealed");
  const [resultEpicStage, setResultEpicStage] = useState("detail");

  const socketRef = useRef(null);
  const epicPulseAnim = useRef(new Animated.Value(1)).current;
  const epicAppearAnim = useRef(new Animated.Value(0.88)).current;
  const gachaFlipAnim = useRef(new Animated.Value(0)).current;
  const playerHitFlash = useRef(new Animated.Value(0)).current;
  const monsterHitFlash = useRef(new Animated.Value(0)).current;
  const fightTimerRef = useRef(null);
  const monsterActionRef = useRef(null);
  const playerRegenRef = useRef(null);
  const wsUrl = useMemo(() => `${WS_BASE}?token=${encodeURIComponent(token)}`, [token]);
  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  const pushGameLog = (text) => {
    setGameActionLog((prev) => [`${new Date().toLocaleTimeString()} ${text}`, ...prev].slice(0, 30));
  };

  const formatPercent = (value) => `${Math.round((value || 0) * 1000) / 10}%`;

  const itemValueScore = (item) => {
    if (!item) return 0;
    const qv = { 普通: 1, 优秀: 2, 精良: 3, 史诗: 5, 传奇: 7, 神话: 9 }[item.quality] || 1;
    const affixCount = Array.isArray(item.affixes) ? item.affixes.length : 0;
    return qv * 10000 + Number(item.power || 0) * 15 + Number(item.level_required || 1) * 40 + affixCount * 120;
  };

  const openResultModal = (title, items = [], summary = []) => {
    const sortedItems = [...items].sort((a, b) => itemValueScore(b) - itemValueScore(a));
    const hasEpicPlus = sortedItems.some((it) => ["史诗", "传奇", "神话"].includes(String(it?.quality || "")));
    setResultEpicStage(hasEpicPlus ? "rarity" : "detail");
    setResultModalTitle(title);
    setResultModalItems(sortedItems);
    setResultModalSummary(summary);
    setGachaRevealPhase(title.includes("抽奖") ? "flipping" : "revealed");
    setResultModalVisible(true);
  };

  const callGameApi = useCallback(
    async (path, method = "GET", body = null) => {
      const options = { method, headers: authHeaders };
      if (body) options.body = JSON.stringify(body);
      const res = await fetch(`${API_BASE}${path}`, options);
      const data = await res.json();
      return { ok: res.ok, data };
    },
    [authHeaders],
  );

  const loadSocial = useCallback(async () => {
    if (!token) return;
    setSocialLoading(true);
    try {
      const [fr, pend, gr] = await Promise.all([
        fetch(`${API_BASE}/friends`, { headers: authHeaders }),
        fetch(`${API_BASE}/friends/pending`, { headers: authHeaders }),
        fetch(`${API_BASE}/groups/my`, { headers: authHeaders }),
      ]);
      const jf = await fr.json();
      const jp = await pend.json();
      const jg = await gr.json();
      if (fr.ok) setFriends(jf.friends || []);
      if (pend.ok) setPendingFriends(jp.pending || []);
      if (gr.ok) setGroups(jg.groups || []);
    } finally {
      setSocialLoading(false);
    }
  }, [token, authHeaders]);

  const refreshGameState = useCallback(async () => {
    if (!token) return;
    setGameLoading(true);
    try {
      const [profileRes, inventoryRes] = await Promise.all([
        callGameApi("/game/profile"),
        callGameApi("/game/inventory"),
      ]);
      if (profileRes.ok) setGameProfile(profileRes.data.profile);
      if (inventoryRes.ok) setGameInventory(inventoryRes.data.inventory || []);
    } finally {
      setGameLoading(false);
    }
  }, [token, callGameApi]);

  const loadSkillShop = useCallback(async () => {
    if (!token) return;
    const res = await callGameApi("/game/skills/shop");
    if (res.ok) {
      setShopSkills(res.data.skills || []);
      setSkillRefreshCost(Number(res.data.refresh_cost || 120));
    }
  }, [token, callGameApi]);

  useEffect(() => {
    if (!connected || !token) return undefined;
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;
    socket.onopen = () => {
      setMessages((prev) => [
        ...prev,
        { id: `sys-${Date.now()}`, type: "system", scope: "lobby", sender: "系统", content: "已连接世界大厅" },
      ]);
      loadSocial();
    };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "online") {
          setOnlineUsers(payload.users || []);
          return;
        }
        if (payload.type === "friend_request") {
          setMessages((prev) => [
            ...prev,
            {
              id: `fr-${Date.now()}`,
              type: "system",
              scope: "lobby",
              sender: "系统",
              content: `${payload.from_username} (ID:${payload.from_user_id}) 请求加你为好友`,
            },
          ]);
          loadSocial();
          return;
        }
        setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, ...payload }]);
      } catch {
        setMessages((prev) => [...prev, { id: `err-${Date.now()}`, type: "system", sender: "系统", content: "消息解析失败" }]);
      }
    };
    socket.onclose = () => setConnected(false);
    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [connected, token, wsUrl, loadSocial]);

  useEffect(() => {
    if (!token) return;
    refreshGameState();
    loadSkillShop();
  }, [token, refreshGameState, loadSkillShop]);

  useEffect(() => {
    if (!fightUiVisible) return undefined;
    fightTimerRef.current = setInterval(() => setFightNow(Date.now()), 120);
    return () => {
      if (fightTimerRef.current) clearInterval(fightTimerRef.current);
      fightTimerRef.current = null;
    };
  }, [fightUiVisible]);

  const submitAuth = async () => {
    const cleanName = username.trim();
    if (!cleanName || !password.trim()) {
      setAuthError("用户名和密码不能为空");
      return;
    }
    setAuthLoading(true);
    setAuthError("");
    try {
      const response = await fetch(`${API_BASE}/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: cleanName, password }),
      });
      const result = await response.json();
      if (!response.ok) {
        setAuthError(result.detail || "认证失败");
        return;
      }
      setToken(result.token);
      setCurrentUser(result.user);
      setConnected(true);
    } catch {
      setAuthError("请求失败，请检查服务端状态");
    } finally {
      setAuthLoading(false);
    }
  };

  const logout = () => {
    if (socketRef.current) socketRef.current.close();
    setToken("");
    setCurrentUser(null);
    setConnected(false);
    setMessages([]);
    setGameProfile(null);
    setGameInventory([]);
    setLatestLootItems([]);
    setLatestDrawRewards([]);
    setEquipModalVisible(false);
    setResultModalVisible(false);
  };

  const sendMessage = () => {
    const text = inputText.trim();
    if (!text || !socketRef.current || socketRef.current.readyState !== 1) return;
    if (activeTab === "lobby") socketRef.current.send(JSON.stringify({ action: "lobby", text }));
    else if (activeTab === "dm" && dmPeer)
      socketRef.current.send(JSON.stringify({ action: "dm", to_user_id: dmPeer.user_id, text }));
    else if (activeTab === "groups" && selectedGroup)
      socketRef.current.send(JSON.stringify({ action: "group", group_id: selectedGroup.group_id, text }));
    setInputText("");
  };

  const sendFriendRequest = async () => {
    const u = friendUsernameInput.trim();
    if (!u) return;
    const res = await callGameApi("/friends/request", "POST", { to_username: u });
    if (!res.ok) pushGameLog(`加好友失败: ${res.data.detail || "未知错误"}`);
    setFriendUsernameInput("");
    loadSocial();
  };

  const acceptFriend = async (fromUserId) => {
    await callGameApi("/friends/accept", "POST", { from_user_id: fromUserId });
    loadSocial();
  };

  const createGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    const res = await callGameApi("/groups", "POST", { name });
    if (res.ok) setSelectedGroup({ group_id: res.data.group_id, name: res.data.name });
    setNewGroupName("");
    loadSocial();
  };

  const inviteToGroup = async () => {
    if (!inviteUsername.trim() || !selectedGroup) return;
    const res = await callGameApi(`/groups/${selectedGroup.group_id}/members`, "POST", {
      username: inviteUsername.trim(),
    });
    pushGameLog(res.ok ? "邀请成功" : `邀请失败: ${res.data.detail || "未知错误"}`);
    setInviteUsername("");
  };

  const runMonsterFight = async () => {
    setGameLoading(true);
    try {
      const res = await callGameApi("/game/fight/monster", "POST", {
        map_id: selectedMap,
        monster_type: selectedMonsterType,
      });
      if (res.ok) {
        const lootItems = res.data.rewards?.item ? [res.data.rewards.item] : [];
        setLatestLootItems(lootItems);
        const mapName = getMapName(selectedMap);
        const monsterName = getMonsterDisplayName(selectedMap, selectedMonsterType);
        pushGameLog(
          `${mapName} - ${monsterName}: ${res.data.won ? "胜利" : "失败"}，胜率${Math.round((res.data.win_rate_estimate || 0) * 100)}%，经验+${res.data.rewards.exp} 金币+${res.data.rewards.gold}`,
        );
        pushGameLog(
          `本次对手属性 HP${res.data.monster_stats?.hp || 0} / ATK${res.data.monster_stats?.attack || 0} / DEF${res.data.monster_stats?.defense || 0}`,
        );
        if (res.data.rewards.item?.name) pushGameLog(`掉落装备: ${res.data.rewards.item.name}`);
        openResultModal(
          `${monsterName} 结果`,
          lootItems,
          [
            `${res.data.won ? "胜利" : "失败"} | 经验+${res.data.rewards.exp} | 金币+${res.data.rewards.gold}`,
            `胜率 ${Math.round((res.data.win_rate_estimate || 0) * 100)}%`,
          ],
        );
      } else {
        pushGameLog(`战斗失败: ${res.data.detail || "请求错误"}`);
      }
      await refreshGameState();
    } finally {
      setGameLoading(false);
    }
  };

  const appendFightLog = (line) => {
    setFightLog((prev) => [`${new Date().toLocaleTimeString()} ${line}`, ...prev].slice(0, 16));
  };

  const addFloatingText = (target, value, kind = "damage") => {
    const id = `${Date.now()}-${Math.random()}`;
    const color = kind === "heal" ? "#48d783" : target === "monster" ? "#ffcc66" : "#ff6f6f";
    setFloatingTexts((prev) => [...prev, { id, target, text: value, color }]);
    setTimeout(() => {
      setFloatingTexts((prev) => prev.filter((x) => x.id !== id));
    }, 620);
  };

  const finishRealtimeFight = async () => {
    if (!fightSnapshot?.fight_id || fightCommitting) return;
    setFightCommitting(true);
    try {
      const isDungeonFight = fightSnapshot?.fight_mode === "dungeon";
      const commitPath = isDungeonFight ? "/game/dungeon/commit" : "/game/fight/commit";
      const res = await callGameApi(commitPath, "POST", {
        fight_id: fightSnapshot.fight_id,
        player_hp: Math.max(0, Math.round(fightPlayerHp || 0)),
        monster_hp: Math.max(0, Math.round(fightMonsterHp || 0)),
      });
      if (res.ok) {
        const lootItems = res.data.rewards?.item ? [res.data.rewards.item] : [];
        const dungeonItems = res.data.rewards?.items || [];
        const itemsFinal = isDungeonFight ? dungeonItems : lootItems;
        const monsterName = isDungeonFight
          ? getDungeonBossName(selectedDungeon)
          : getMonsterDisplayName(selectedMap, selectedMonsterType);
        const wonFlag = isDungeonFight ? Boolean(res.data.cleared) : Boolean(res.data.won);
        if (res.data.rewards?.skill_id) appendFightLog(`获得技能掉落: ${res.data.rewards.skill_id}`);
        openResultModal(
          `${monsterName} 结果`,
          itemsFinal,
          [
            `${wonFlag ? "胜利" : "失败"} | 经验+${res.data.rewards.exp} | 金币+${res.data.rewards.gold}`,
            `胜率 ${Math.round(((res.data.win_rate_estimate ?? res.data.clear_rate_estimate) || 0) * 100)}%`,
            res.data.rewards?.skill_id ? `技能掉落: ${res.data.rewards.skill_id}` : "技能掉落: 无",
          ],
        );
        await refreshGameState();
        await loadSkillShop();
        if (isDungeonFight) setDungeonUiVisible(false);
      } else {
        pushGameLog(`战斗结算失败: ${res.data.detail || "请求错误"}`);
      }
    } finally {
      setFightCommitting(false);
      setFightSnapshot(null);
      setFightUiVisible(false);
      setFightEnded(false);
      setFightLog([]);
    }
  };

  const closeFightUi = () => {
    if (monsterActionRef.current) clearInterval(monsterActionRef.current);
    if (playerRegenRef.current) clearInterval(playerRegenRef.current);
    monsterActionRef.current = null;
    playerRegenRef.current = null;
    setFightUiVisible(false);
    setFightSnapshot(null);
    setFightLog([]);
    setFightEnded(false);
    setFloatingTexts([]);
    setPlayerActionLockedUntil(0);
    setMonsterComboBasicCount(0);
    playerHitFlash.setValue(0);
    monsterHitFlash.setValue(0);
  };

  const animateHit = (anim) => {
    anim.setValue(0);
    Animated.sequence([
      Animated.timing(anim, { toValue: 1, duration: 90, useNativeDriver: false }),
      Animated.timing(anim, { toValue: 0, duration: 180, useNativeDriver: false }),
    ]).start();
  };

  const openRealtimeFightSession = (data, encounterText) => {
    const now = Date.now();
    setFightSnapshot(data);
    setFightPlayerHp(Number(data.player?.max_hp || 1));
    setFightMonsterHp(Number(data.monster?.max_hp || 1));
    setFightLog([]);
    setFightEnded(false);
    setBasicReadyAt(now);
    setSkillReadyAts(Array(6).fill(now));
    setMonsterSkillReadyAts((data.monster?.skills || []).map(() => now));
    setPlayerActionLockedUntil(now);
    setMonsterComboBasicCount(0);
    setFloatingTexts([]);
    setFightUiVisible(true);
    appendFightLog(encounterText);
    if (data.monster?.mechanic) {
      appendFightLog(`Boss机制：${data.monster.mechanic.name} - ${data.monster.mechanic.desc}`);
    }

    if (monsterActionRef.current) clearInterval(monsterActionRef.current);
    monsterActionRef.current = setInterval(() => {
      let currentMonsterHp = fightMonsterHp;
      setFightMonsterHp((mh) => {
        currentMonsterHp = mh;
        if (fightEnded || mh <= 0) return mh;
        return mh;
      });
      setFightPlayerHp((hp) => {
        if (fightEnded || hp <= 0) return hp;
        const nowTs = Date.now();
        let fired = -1;
        let skill = null;
        setMonsterSkillReadyAts((prev) => {
          const next = [...prev];
          const mhRatio = currentMonsterHp / Math.max(1, Number(data.monster?.max_hp || 1));
          const ai = data.monster?.ai || {};
          const triggerPriority = ai.trigger_priority || {};
          const comboBonus = Number(ai.combo_followup_bonus || 0);
          const canUse = (s, i) => {
            if (nowTs < next[i]) return false;
            const tr = s?.trigger || "always";
            if (tr === "always") return true;
            if (tr === "after_basic_2") return monsterComboBasicCount >= 2;
            if (tr === "hp_below_70") return mhRatio <= 0.7;
            if (tr === "hp_below_35") return mhRatio <= 0.35;
            return true;
          };
          let bestScore = -1e9;
          for (let i = 0; i < next.length; i += 1) {
            const cur = data.monster.skills[i];
            if (canUse(cur, i)) {
              const tr = cur?.trigger || "always";
              let score = Number(triggerPriority[tr] || 0);
              if (cur?.id !== "m_basic" && monsterComboBasicCount >= 2) score += comboBonus;
              score += Math.random() * 0.1;
              if (score > bestScore) {
                bestScore = score;
                fired = i;
              }
            }
          }
          if (fired >= 0) {
            skill = data.monster.skills[fired];
            next[fired] = nowTs + (skill?.cd_ms || 1200);
          }
          return next;
        });
        if (fired < 0 || !skill) return hp;
        if (skill.id === "m_basic") setMonsterComboBasicCount((c) => c + 1);
        else setMonsterComboBasicCount(0);
        const mhRatio = currentMonsterHp / Math.max(1, Number(data.monster?.max_hp || 1));
        const enrageBoost =
          data.monster?.mechanic?.id === "enrage_phase" && mhRatio <= 0.35 ? 1.22 : 1;
        const summonBoost = data.monster?.mechanic?.id === "summon_phase" && Math.random() < 0.18 ? 1.12 : 1;
        const base = (Number(data.monster.attack || 1) * Number(skill.mult || 1) * enrageBoost * summonBoost) - Number(data.player.defense || 0) * 0.35;
        const dmg = Math.max(1, Math.round(base * Number(data.balance?.monster_out || 1)));
        if (skill.id !== "m_basic") appendFightLog(`${data.monster.name} 使用${skill.name}，造成 ${dmg} 伤害`);
        animateHit(playerHitFlash);
        addFloatingText("player", `-${dmg}`);
        setPlayerActionLockedUntil(Date.now() + 220);
        const nh = Math.max(0, hp - dmg);
        if (nh <= 0) setFightEnded(true);
        return nh;
      });
    }, 220);

    if (playerRegenRef.current) clearInterval(playerRegenRef.current);
    playerRegenRef.current = setInterval(() => {
      if (fightEnded) return;
      const regenRate = Number(data.balance?.regen || 0);
      if (regenRate <= 0) return;
      setFightPlayerHp((hp) => {
        const maxHp = Number(data.player?.max_hp || 1);
        if (hp >= maxHp) return hp;
        return Math.min(maxHp, hp + Math.max(1, Math.round(maxHp * regenRate)));
      });
    }, 800);
  };

  const startRealtimeFight = async () => {
    setGameLoading(true);
    try {
      const res = await callGameApi("/game/fight/engage", "POST", {
        map_id: selectedMap,
        monster_type: selectedMonsterType,
      });
      if (!res.ok) {
        pushGameLog(`战斗初始化失败: ${res.data.detail || "请求错误"}`);
        return;
      }
      const data = res.data;
      openRealtimeFightSession(
        data,
        `遭遇 ${getMonsterDisplayName(selectedMap, selectedMonsterType)}，预计胜率 ${Math.round((data.win_rate_estimate || 0) * 100)}%`,
      );
    } finally {
      setGameLoading(false);
    }
  };

  const startDungeonRealtimeFight = async () => {
    const eventChoices = {};
    selectedDungeonNodes.forEach((node, idx) => {
      if (!["treasure", "heal", "elite"].includes(node)) return;
      const k = `${selectedDungeon}-${idx}`;
      if (dungeonEventState[k]) eventChoices[String(idx)] = dungeonEventState[k];
    });
    setGameLoading(true);
    try {
      const res = await callGameApi("/game/dungeon/engage", "POST", {
        dungeon_id: selectedDungeon,
        current_room_index: dungeonRoomIndex,
        event_choices: eventChoices,
      });
      if (!res.ok || !res.data?.ok) {
        pushGameLog(`副本战斗初始化失败: ${res.data?.reason || res.data?.detail || "请求错误"}`);
        return;
      }
      const data = res.data;
      openRealtimeFightSession(
        data,
        `副本Boss战开始：${getDungeonBossName(selectedDungeon)}，预计胜率 ${Math.round((data.win_rate_estimate || 0) * 100)}%`,
      );
    } finally {
      setGameLoading(false);
    }
  };

  const castBasicAttack = () => {
    if (!fightSnapshot || fightEnded) return;
    const now = Date.now();
    if (now < basicReadyAt || now < playerActionLockedUntil) return;
    const windup = 160;
    const recovery = 220;
    setPlayerActionLockedUntil(now + windup + recovery);
    setBasicReadyAt(now + Number(fightSnapshot.player?.basic_cd_ms || 1000));
    setTimeout(() => {
      const base = Number(fightSnapshot.player?.attack || 1) - Number(fightSnapshot.monster?.defense || 0) * 0.28;
      const shieldReduce = fightSnapshot?.monster?.mechanic?.id === "shield_phase" ? 0.78 : 1;
      const dmg = Math.max(1, Math.round(base * Number(fightSnapshot.balance?.player_out || 1) * shieldReduce));
      animateHit(monsterHitFlash);
      addFloatingText("monster", `-${dmg}`);
      setFightMonsterHp((hp) => {
        const nh = Math.max(0, hp - dmg);
        if (nh <= 0) setFightEnded(true);
        return nh;
      });
    }, windup);
  };

  const castSkill = (slotIndex) => {
    if (!fightSnapshot || fightEnded) return;
    const bar = fightSnapshot.player?.skill_bar || [];
    const slot = bar[slotIndex];
    if (!slot?.unlocked || !slot?.skill_id) return;
    const now = Date.now();
    if (now < (skillReadyAts[slotIndex] || 0) || now < playerActionLockedUntil) return;
    const cd = Number(slot.cooldown_ms || 3000);
    setSkillReadyAts((prev) => {
      const next = [...prev];
      next[slotIndex] = now + cd;
      return next;
    });
    const windup = 260;
    const recovery = 300;
    setPlayerActionLockedUntil(now + windup + recovery);
    setTimeout(() => {
      const base = Number(fightSnapshot.player?.attack || 1) * Number(slot.damage_mult || 1.0) - Number(fightSnapshot.monster?.defense || 0) * 0.18;
      const shieldReduce = fightSnapshot?.monster?.mechanic?.id === "shield_phase" ? 0.8 : 1;
      const dmg = Math.max(2, Math.round(base * Number(fightSnapshot.balance?.player_out || 1) * shieldReduce));
      const heal = Math.round(Number(fightSnapshot.player?.max_hp || 1) * Number(slot.heal_pct_max || 0));
      appendFightLog(`你施放 ${slot.name}，造成 ${dmg} 伤害${heal > 0 ? `，回复 ${heal} 生命` : ""}`);
      animateHit(monsterHitFlash);
      addFloatingText("monster", `-${dmg}`);
      if (heal > 0) {
        addFloatingText("player", `+${heal}`, "heal");
        setFightPlayerHp((hp) => Math.min(Number(fightSnapshot.player?.max_hp || hp), hp + heal));
      }
      // 受击打断：技能命中后有概率让怪物硬直，延后其下次动作
      if (Math.random() < 0.22) {
        setMonsterSkillReadyAts((prev) => prev.map((t) => Math.max(t, Date.now() + 380)));
        appendFightLog("怪物被打断，出现短暂硬直");
      }
      setFightMonsterHp((hp) => {
        const nh = Math.max(0, hp - dmg);
        if (nh <= 0) setFightEnded(true);
        return nh;
      });
    }, windup);
  };

  useEffect(() => {
    if (!fightUiVisible) return;
    if (fightEnded || fightMonsterHp <= 0 || fightPlayerHp <= 0) {
      setFightEnded(true);
      if (monsterActionRef.current) clearInterval(monsterActionRef.current);
      if (playerRegenRef.current) clearInterval(playerRegenRef.current);
      monsterActionRef.current = null;
      playerRegenRef.current = null;
    }
  }, [fightUiVisible, fightEnded, fightMonsterHp, fightPlayerHp]);

  useEffect(() => {
    if (!fightUiVisible || fightEnded || !autoBasicEnabled) return;
    if (fightNow < basicReadyAt) return;
    castBasicAttack();
  }, [fightUiVisible, fightEnded, autoBasicEnabled, fightNow, basicReadyAt]);

  const buySkill = async (skillId) => {
    const res = await callGameApi("/game/skills/buy", "POST", { skill_id: skillId });
    if (res.ok) {
      pushGameLog(`购买技能成功: ${skillId}`);
      setGameProfile(res.data.profile);
      await loadSkillShop();
    } else {
      pushGameLog(`购买技能失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const refreshSkillShop = async () => {
    const res = await callGameApi("/game/skills/refresh", "POST", { force: true });
    if (res.ok) {
      setShopSkills(res.data.skills || []);
      setSkillRefreshCost(Number(res.data.refresh_cost || skillRefreshCost));
      setGameProfile(res.data.profile || gameProfile);
      pushGameLog(`刷新商店成功，花费 ${res.data.spent_gold || 0} 金币`);
      await refreshGameState();
    } else {
      pushGameLog(`刷新商店失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const scrapSkill = async (skillId) => {
    const res = await callGameApi("/game/skills/scrap", "POST", { skill_id: skillId });
    if (res.ok) {
      setGameProfile(res.data.profile);
      pushGameLog(`分解技能成功 +${res.data.gained_skill_shard} 技能碎片`);
      await loadSkillShop();
    } else {
      pushGameLog(`分解技能失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const exchangeDropSkill = async (skillId) => {
    const res = await callGameApi("/game/skills/exchange", "POST", { skill_id: skillId });
    if (res.ok) {
      setGameProfile(res.data.profile);
      pushGameLog(`兑换技能成功: ${skillId}`);
      await loadSkillShop();
    } else {
      pushGameLog(`兑换技能失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const saveSkillToSlot = async (slotIndex, skillId) => {
    const res = await callGameApi("/game/skills/loadout", "POST", {
      slots: [{ slot_index: slotIndex, skill_id: skillId }],
    });
    if (res.ok) {
      setGameProfile(res.data.profile);
      pushGameLog(`技能已配置到第${slotIndex + 1}栏`);
    } else {
      pushGameLog(`配置技能失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const openSkillPicker = (slot) => {
    setSkillPickerSlot(slot);
    setSkillPickerVisible(true);
  };

  const specializeSkill = async (skillId, branch) => {
    const res = await callGameApi("/game/skills/specialize", "POST", { skill_id: skillId, branch });
    if (res.ok) {
      setGameProfile(res.data.profile);
      pushGameLog(`技能专精已切换为 ${branch}`);
    } else {
      pushGameLog(`专精切换失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const challengeDungeon = async () => {
    const res = await callGameApi("/game/dungeon/challenge", "POST", { dungeon_id: selectedDungeon });
    if (res.ok) {
      const dungeonName = getDungeonName(selectedDungeon);
      pushGameLog(res.data.ok ? `${dungeonName} 等级满足，可进入副本` : `${dungeonName} 未达标: ${res.data.reason}`);
      if (res.data.ok) {
        setDungeonRoomIndex(0);
        setDungeonEventState({});
        setDungeonRunMods({ clearRateBonus: 0, rewardBonus: 0, bossScaleDelta: 0, curseValue: 0, greedValue: 0 });
        setDungeonUiVisible(true);
      }
      if (res.data.profile?.total_stats) {
        pushGameLog(
          `当前角色属性 HP${res.data.profile.total_stats.hp} / ATK${res.data.profile.total_stats.attack} / DEF${res.data.profile.total_stats.defense}`,
        );
      }
    }
    else pushGameLog(`副本检查失败: ${res.data.detail || "请求错误"}`);
    await refreshGameState();
  };

  const settleDungeon = async () => {
    setGameLoading(true);
    try {
      const eventChoices = {};
      selectedDungeonNodes.forEach((node, idx) => {
        if (!["treasure", "heal", "elite"].includes(node)) return;
        const k = `${selectedDungeon}-${idx}`;
        if (dungeonEventState[k]) eventChoices[String(idx)] = dungeonEventState[k];
      });
      const res = await callGameApi("/game/dungeon/settle", "POST", {
        dungeon_id: selectedDungeon,
        cleared: true,
        current_room_index: dungeonRoomIndex,
        event_choices: eventChoices,
      });
      if (res.ok) {
        if (res.data.ok) {
          const lootItems = res.data.rewards?.items || [];
          const dungeonName = getDungeonName(selectedDungeon);
          const bossName = getDungeonBossName(selectedDungeon);
          setLatestLootItems(lootItems);
          pushGameLog(
            `${dungeonName} ${res.data.cleared ? "通关" : "失败"}，预计通关率${Math.round((res.data.clear_rate_estimate || 0) * 100)}%，经验+${res.data.rewards.exp} 金币+${res.data.rewards.gold}`,
          );
          pushGameLog(
            `${bossName} 属性 HP${res.data.boss_stats?.hp || 0} / ATK${res.data.boss_stats?.attack || 0} / DEF${res.data.boss_stats?.defense || 0}`,
          );
          if ((res.data.rewards.items || []).length > 0) {
            pushGameLog(`副本掉落: ${(res.data.rewards.items || []).map((i) => i.name).join(" / ")}`);
          }
          openResultModal(
            `${bossName} 结算`,
            lootItems,
            [
              `${res.data.cleared ? "通关" : "失败"} | 经验+${res.data.rewards.exp} | 金币+${res.data.rewards.gold}`,
              `预计通关率 ${Math.round((res.data.clear_rate_estimate || 0) * 100)}%`,
              res.data.mechanic?.name ? `Boss机制: ${res.data.mechanic.name}` : null,
            ].filter(Boolean),
          );
          setDungeonUiVisible(false);
        } else {
          pushGameLog(`副本失败: ${res.data.reason || "结算失败"}`);
          setDungeonUiVisible(false);
        }
      }
      await refreshGameState();
    } finally {
      setGameLoading(false);
    }
  };

  const loadDungeonEventOptions = async (nodeType, roomIndex) => {
    if (!["treasure", "heal", "elite"].includes(nodeType)) return;
    const chosen = Object.values(dungeonEventState || {});
    const res = await callGameApi("/game/dungeon/event-roll", "POST", {
      dungeon_id: selectedDungeon,
      room_index: roomIndex,
      node_type: nodeType,
      chosen_event_ids: chosen,
    });
    if (!res.ok) {
      pushGameLog(`拉取房间事件失败: ${res.data.detail || "请求错误"}`);
      return;
    }
    const roomKey = `${selectedDungeon}-${roomIndex}`;
    setDungeonEventOptions((prev) => ({ ...prev, [roomKey]: res.data.options || [] }));
  };

  const applyDungeonChoice = (choice) => {
    const roomKey = `${selectedDungeon}-${dungeonRoomIndex}`;
    if (dungeonEventState[roomKey]) return;
    setDungeonEventState((prev) => ({ ...prev, [roomKey]: choice.id }));
    setDungeonRunMods((prev) => ({
      clearRateBonus: Math.max(-0.25, Math.min(0.25, prev.clearRateBonus + Number(choice.effect.clearRateBonus || 0))),
      rewardBonus: Math.max(-0.3, Math.min(0.5, prev.rewardBonus + Number(choice.effect.rewardBonus || 0))),
      bossScaleDelta: Math.max(-0.25, Math.min(0.25, prev.bossScaleDelta + Number(choice.effect.bossScaleDelta || 0))),
      curseValue: Math.max(0, Math.min(1.5, prev.curseValue + Number(choice.effect.curseValue || 0))),
      greedValue: Math.max(0, Math.min(1.5, prev.greedValue + Number(choice.effect.greedValue || 0))),
    }));
    pushGameLog(`房间事件选择：${choice.label}`);
  };

  useEffect(() => {
    if (!dungeonUiVisible) return;
    const nodeType = selectedDungeonNodes[dungeonRoomIndex];
    loadDungeonEventOptions(nodeType, dungeonRoomIndex);
  }, [dungeonUiVisible, selectedDungeon, dungeonRoomIndex]);

  const drawGacha = async () => {
    setGameLoading(true);
    try {
      const res = await callGameApi("/game/gacha/draw", "POST", { pool: selectedPool, count: 1 });
      if (res.ok) {
        const rewards = res.data.rewards || [];
        setLatestDrawRewards(rewards);
        const rewardText = (res.data.rewards || [])
          .map((r) => (r.type === "item" ? `装备:${r.item.name}` : `${r.type}:${r.amount}`))
          .join(" | ");
        pushGameLog(`抽奖(${selectedPool}) => ${rewardText || "无奖励"}`);
        openResultModal(
          `${selectedPool} 抽奖结果`,
          rewards.filter((r) => r.type === "item").map((r) => r.item),
          rewards.map((r) => (r.type === "item" ? `装备: ${r.item?.name}` : `${r.type} x${r.amount || 0}`)),
        );
      } else {
        pushGameLog(`抽奖失败: ${res.data.detail || "请求错误"}`);
      }
      await refreshGameState();
    } finally {
      setGameLoading(false);
    }
  };

  const equipItem = async (inventoryId) => {
    const res = await callGameApi("/game/equip", "POST", { inventory_id: inventoryId });
    if (res.ok) {
      pushGameLog("穿戴成功");
      setGameProfile(res.data.profile);
      setEquipModalVisible(false);
    } else {
      pushGameLog(`穿戴失败: ${res.data.detail || "请求错误"}`);
    }
    await refreshGameState();
  };

  const sellItem = async (inventoryId) => {
    const res = await callGameApi("/game/sell", "POST", { inventory_id: inventoryId, quantity: 1 });
    if (res.ok) {
      pushGameLog(`出售成功 +${res.data.sold.total_price} 金币 (${res.data.sold.name})`);
      setGameProfile(res.data.profile);
    } else {
      pushGameLog(`出售失败: ${res.data.detail || "请求错误"}`);
    }
    await refreshGameState();
  };

  const toggleBatchQuality = (q) => {
    setBatchSellQualities((prev) =>
      prev.includes(q) ? prev.filter((x) => x !== q) : [...prev, q],
    );
  };

  const sellBatch = async () => {
    const maxLv = Math.max(1, Math.min(50, Number(batchSellMaxLevel || 1)));
    const res = await callGameApi("/game/sell/batch", "POST", {
      min_level: 1,
      max_level: maxLv,
      qualities: batchSellQualities,
      category: "equipment",
      include_equipped: false,
    });
    if (res.ok) {
      pushGameLog(`一键出售完成：共${res.data.sold_count}件，金币+${res.data.total_gold}`);
      setGameProfile(res.data.profile);
      await refreshGameState();
    } else {
      pushGameLog(`一键出售失败: ${res.data.detail || "请求错误"}`);
    }
  };

  const qualityBorderColor = (quality) => {
    if (quality === "普通") return "#FFFFFF";
    if (quality === "优秀") return "#35D07F";
    if (quality === "精良") return "#4A8DFF";
    if (quality === "史诗") return "#B06CFF";
    if (quality === "传奇") return "#FFD24A";
    if (quality === "神话") return "#FF4A4A";
    return "#D0D7E2";
  };

  const filteredInventory = useMemo(() => {
    return (gameInventory || []).filter((it) => {
      const categoryPass =
        inventoryCategoryFilter === "all" ||
        (inventoryCategoryFilter === "equipment" && it.category === "equipment") ||
        (inventoryCategoryFilter === "consumable" && it.category === "consumable");
      const qualityPass = inventoryQualityFilter === "all" || it.quality === inventoryQualityFilter;
      return categoryPass && qualityPass;
    });
  }, [gameInventory, inventoryCategoryFilter, inventoryQualityFilter]);

  const equippedSlots = useMemo(() => {
    const slots = {
      weapon: null,
      helmet: null,
      chest: null,
      gloves: null,
      pants: null,
      boots: null,
    };
    (gameProfile?.equipped || []).forEach((item) => {
      if (item?.slot && slots[item.slot] === null) slots[item.slot] = item;
    });
    return slots;
  }, [gameProfile]);

  const equipCandidates = useMemo(() => {
    if (!equipModalSlot) return [];
    return (gameInventory || [])
      .filter((it) => it.category === "equipment" && it.slot === equipModalSlot)
      .sort((a, b) => {
        if (Number(b.equipped) !== Number(a.equipped)) return Number(b.equipped) - Number(a.equipped);
        if ((b.level_required || 0) !== (a.level_required || 0)) return (b.level_required || 0) - (a.level_required || 0);
        return (b.power || 0) - (a.power || 0);
      });
  }, [equipModalSlot, gameInventory]);

  const selectedDungeonMeta = useMemo(
    () => DUNGEONS.find((d) => d.id === selectedDungeon) || DUNGEONS[0],
    [selectedDungeon],
  );

  const selectedDungeonEncounter = useMemo(
    () => getDungeonEncounter(selectedDungeon),
    [selectedDungeon],
  );

  const selectedDungeonNodes = useMemo(
    () => DUNGEON_NODE_LAYOUTS[selectedDungeon] || DUNGEON_NODE_LAYOUTS.DUN30,
    [selectedDungeon],
  );
  const currentDungeonNodeType = selectedDungeonNodes[dungeonRoomIndex];
  const fightPlayerPortrait = useMemo(
    () => resolveEquipmentIcon(equippedSlots.weapon || equippedSlots.chest || equippedSlots.helmet),
    [equippedSlots],
  );
  const fightMonsterPortrait = useMemo(
    () =>
      fightSnapshot?.fight_mode === "dungeon"
        ? DUNGEON_BOSS_IMAGES[selectedDungeon] || DUNGEON_NODE_ICONS.boss
        : MONSTER_PORTRAITS[selectedMonsterType] || DUNGEON_NODE_ICONS.boss,
    [selectedMonsterType, fightSnapshot, selectedDungeon],
  );
  const availableSkillsForSlot = useMemo(() => {
    if (!skillPickerSlot) return [];
    const all = gameProfile?.owned_skills || [];
    return all.filter((s) => s.allowed_slot === "any" || s.allowed_slot === skillPickerSlot.slot);
  }, [gameProfile, skillPickerSlot]);

  const resultModalHasEpic = useMemo(
    () => resultModalItems.some((item) => item?.quality === "史诗"),
    [resultModalItems],
  );

  const resultModalIsBoss = useMemo(
    () =>
      resultModalTitle.includes("Boss") ||
      resultModalTitle.includes("DUN") ||
      resultModalTitle.includes("副本"),
    [resultModalTitle],
  );

  const resultModalIsGacha = useMemo(
    () => resultModalTitle.includes("抽奖"),
    [resultModalTitle],
  );

  useEffect(() => {
    if (!resultModalVisible) {
      epicPulseAnim.stopAnimation();
      epicPulseAnim.setValue(1);
      epicAppearAnim.setValue(0.88);
      gachaFlipAnim.setValue(0);
      setGachaRevealPhase("revealed");
      setResultEpicStage("detail");
      return;
    }

    Animated.spring(epicAppearAnim, {
      toValue: 1,
      friction: 6,
      tension: 70,
      useNativeDriver: true,
    }).start();

    if (resultModalHasEpic) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(epicPulseAnim, {
            toValue: 1.06,
            duration: 850,
            useNativeDriver: true,
          }),
          Animated.timing(epicPulseAnim, {
            toValue: 1,
            duration: 850,
            useNativeDriver: true,
          }),
        ]),
      ).start();
    } else {
      epicPulseAnim.setValue(1);
    }

    if (resultModalIsGacha) {
      gachaFlipAnim.setValue(0);
      Animated.sequence([
        Animated.timing(gachaFlipAnim, {
          toValue: 1,
          duration: 550,
          useNativeDriver: true,
        }),
        Animated.delay(180),
      ]).start(() => setGachaRevealPhase("revealed"));
    } else {
      gachaFlipAnim.setValue(1);
    }
  }, [resultModalVisible, resultModalHasEpic, resultModalIsGacha, epicAppearAnim, epicPulseAnim, gachaFlipAnim]);

  useEffect(() => {
    if (!resultModalVisible) return;
    if (!resultModalHasEpic) {
      setResultEpicStage("detail");
      return;
    }
    if (resultEpicStage !== "rarity") return;
    const t = setTimeout(() => setResultEpicStage("detail"), 900);
    return () => clearTimeout(t);
  }, [resultModalVisible, resultModalHasEpic, resultEpicStage]);

  const visibleMessages = useMemo(() => {
    const uid = currentUser?.user_id;
    return messages.filter((m) => {
      if (activeTab === "lobby") return m.scope === "lobby" || !m.scope;
      if (activeTab === "dm") {
        if (!dmPeer || m.scope !== "dm") return false;
        return (
          (m.sender_id === uid && m.peer_id === dmPeer.user_id) ||
          (m.sender_id === dmPeer.user_id && m.peer_id === uid)
        );
      }
      if (activeTab === "groups") return selectedGroup && m.scope === "group" && m.group_id === selectedGroup.group_id;
      return false;
    });
  }, [messages, activeTab, dmPeer, selectedGroup, currentUser]);

  if (!token) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="dark" />
        <View style={styles.loginCard}>
          <Text style={styles.title}>起源</Text>
          <Text style={styles.subtitle}>登录后可聊天并试玩 RPG 第一版</Text>
          <TextInput style={styles.input} value={username} onChangeText={setUsername} placeholder="用户名" autoCapitalize="none" />
          <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder="密码" secureTextEntry autoCapitalize="none" />
          {authError ? <Text style={styles.errorText}>{authError}</Text> : null}
          <TouchableOpacity style={styles.button} onPress={submitAuth}>
            <Text style={styles.buttonText}>{authLoading ? "处理中..." : authMode === "login" ? "登录" : "注册"}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.switchModeBtn} onPress={() => setAuthMode((p) => (p === "login" ? "register" : "login"))}>
            <Text style={styles.switchModeText}>{authMode === "login" ? "没有账号？去注册" : "已有账号？去登录"}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView style={styles.chatWrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>{currentUser?.username} (ID:{currentUser?.user_id})</Text>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.leaveText}>退出</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.modeRow}>
          {[
            { key: "chat", label: "聊天社交" },
            { key: "game", label: "RPG试玩" },
          ].map((m) => (
            <TouchableOpacity key={m.key} style={[styles.modeBtn, appMode === m.key && styles.modeBtnActive]} onPress={() => setAppMode(m.key)}>
              <Text style={[styles.modeText, appMode === m.key && styles.modeTextActive]}>{m.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {appMode === "chat" ? (
          <>
            <View style={styles.tabRow}>
              {[
                { key: "lobby", label: "大厅" },
                { key: "dm", label: "私聊" },
                { key: "groups", label: "群聊" },
                { key: "friends", label: "好友" },
              ].map((t) => (
                <TouchableOpacity key={t.key} style={[styles.tab, activeTab === t.key && styles.tabActive]} onPress={() => setActiveTab(t.key)}>
                  <Text style={[styles.tabText, activeTab === t.key && styles.tabTextActive]}>{t.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {activeTab === "friends" ? (
              <ScrollView style={styles.sideScroll}>
                <Text style={styles.sectionTitle}>待同意</Text>
                {pendingFriends.map((p) => (
                  <View key={p.user_id} style={styles.rowItem}>
                    <Text>{p.username} (ID:{p.user_id})</Text>
                    <TouchableOpacity style={styles.smallBtn} onPress={() => acceptFriend(p.user_id)}>
                      <Text style={styles.smallBtnText}>同意</Text>
                    </TouchableOpacity>
                  </View>
                ))}
                <Text style={styles.sectionTitle}>好友</Text>
                {friends.map((f) => (
                  <TouchableOpacity key={f.user_id} style={styles.rowItem} onPress={() => { setDmPeer(f); setActiveTab("dm"); }}>
                    <Text>{f.username} (ID:{f.user_id})</Text>
                  </TouchableOpacity>
                ))}
                <TextInput style={styles.input} value={friendUsernameInput} onChangeText={setFriendUsernameInput} placeholder="用户名加好友" />
                <TouchableOpacity style={styles.button} onPress={sendFriendRequest}>
                  <Text style={styles.buttonText}>发送请求</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.secondaryBtn} onPress={loadSocial}>
                  <Text style={styles.secondaryBtnText}>{socialLoading ? "刷新中..." : "刷新"}</Text>
                </TouchableOpacity>
              </ScrollView>
            ) : activeTab === "groups" && !selectedGroup ? (
              <ScrollView style={styles.sideScroll}>
                <Text style={styles.sectionTitle}>群组</Text>
                {groups.map((g) => (
                  <TouchableOpacity key={g.group_id} style={styles.rowItem} onPress={() => setSelectedGroup(g)}>
                    <Text>{g.name} (ID:{g.group_id})</Text>
                  </TouchableOpacity>
                ))}
                <TextInput style={styles.input} value={newGroupName} onChangeText={setNewGroupName} placeholder="新群名称" />
                <TouchableOpacity style={styles.button} onPress={createGroup}>
                  <Text style={styles.buttonText}>创建群</Text>
                </TouchableOpacity>
              </ScrollView>
            ) : (
              <>
                {activeTab === "groups" && selectedGroup ? (
                  <View style={styles.groupManage}>
                    <Text style={styles.sectionTitle}>群：{selectedGroup.name}</Text>
                    <View style={styles.inviteRow}>
                      <TextInput style={[styles.input, styles.inviteInput]} value={inviteUsername} onChangeText={setInviteUsername} placeholder="邀请用户名" />
                      <TouchableOpacity style={[styles.button, styles.inviteBtn]} onPress={inviteToGroup}>
                        <Text style={styles.buttonText}>邀请</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : null}
                {activeTab === "dm" && !dmPeer ? (
                  <Text style={styles.muted}>先到好友页选择私聊对象</Text>
                ) : null}
                <FlatList
                  style={styles.list}
                  data={visibleMessages}
                  keyExtractor={(item) => item.id}
                  renderItem={({ item }) => (
                    <View style={item.type === "chat" ? styles.chatBubble : styles.systemBubble}>
                      <Text style={styles.sender}>{item.sender}{item.sender_id ? ` (ID:${item.sender_id})` : ""}</Text>
                      <Text style={styles.messageText}>{item.content}</Text>
                    </View>
                  )}
                />
                <View style={styles.inputRow}>
                  <TextInput style={[styles.input, styles.chatInput]} value={inputText} onChangeText={setInputText} placeholder="输入聊天消息..." />
                  <TouchableOpacity style={[styles.button, styles.sendButton]} onPress={sendMessage}>
                    <Text style={styles.buttonText}>发送</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </>
        ) : (
          <ScrollView style={styles.sideScroll}>
            <Text style={styles.sectionTitle}>角色状态</Text>
            <Text style={styles.infoText}>等级: {gameProfile?.level ?? "-"}</Text>
            <Text style={styles.infoText}>总战力: {gameProfile?.total_power ?? "-"}</Text>
            <Text style={styles.infoText}>生命: {gameProfile?.total_stats?.hp ?? "-"}</Text>
            <Text style={styles.infoText}>攻击: {gameProfile?.total_stats?.attack ?? "-"}</Text>
            <Text style={styles.infoText}>防御: {gameProfile?.total_stats?.defense ?? "-"}</Text>
            <Text style={styles.infoText}>闪避: {formatPercent(gameProfile?.total_stats?.dodge)}</Text>
            <Text style={styles.infoText}>暴击: {formatPercent(gameProfile?.total_stats?.crit)}</Text>
            <Text style={styles.infoText}>暴伤加成: {formatPercent(gameProfile?.total_stats?.crit_damage)}</Text>
            <Text style={styles.infoText}>格挡: {formatPercent(gameProfile?.total_stats?.block)}</Text>
            <Text style={styles.infoText}>吸血: {formatPercent(gameProfile?.total_stats?.lifesteal)}</Text>
            <Text style={styles.infoText}>冰冻几率: {formatPercent(gameProfile?.total_stats?.freeze)}</Text>
            <Text style={styles.infoText}>金币: {gameProfile?.wallet?.gold ?? 0}</Text>
            <Text style={styles.infoText}>普通券: {gameProfile?.wallet?.normal_ticket ?? 0}</Text>
            <Text style={styles.infoText}>高级券: {gameProfile?.wallet?.advanced_ticket ?? 0}</Text>
            <Text style={styles.infoText}>强化石: {gameProfile?.wallet?.enhance_stone ?? 0}</Text>
            <Text style={styles.infoText}>重铸石: {gameProfile?.wallet?.reroll_stone ?? 0}</Text>
            <Text style={styles.infoText}>史诗碎片: {gameProfile?.wallet?.epic_shard ?? 0}</Text>

            <Text style={styles.sectionTitle}>已穿戴</Text>
            <View style={styles.equippedGrid}>
              {Object.keys(SLOT_LABELS).map((slot) => {
                const item = equippedSlots[slot];
                const icon = resolveEquipmentIcon(item || { category: "equipment", slot });
                return (
                  <TouchableOpacity
                    key={slot}
                    style={styles.equippedCell}
                    onPress={() => {
                      setEquipModalSlot(slot);
                      setEquipModalVisible(true);
                    }}
                  >
                    <View
                      style={[
                        styles.equippedIconWrap,
                        item ? { borderColor: qualityBorderColor(item.quality) } : styles.equippedEmpty,
                      ]}
                    >
                      {icon ? <Image source={icon} style={styles.equippedIcon} resizeMode="contain" /> : null}
                    </View>
                    <Text style={styles.equippedSlotText}>{SLOT_LABELS[slot]}</Text>
                    <Text style={styles.equippedNameText} numberOfLines={2}>
                      {item ? item.name : "未装备"}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={styles.sectionTitle}>刷怪</Text>
            <View style={styles.choiceRow}>
              {GAME_MAPS.map((m) => (
                <TouchableOpacity key={m.map_id} style={[styles.choiceBtn, selectedMap === m.map_id && styles.choiceBtnActive]} onPress={() => setSelectedMap(m.map_id)}>
                  <Text style={[styles.choiceText, selectedMap === m.map_id && styles.choiceTextActive]}>{m.map_id}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.choiceRow}>
              {MONSTER_TYPES.map((mt) => (
                <TouchableOpacity key={mt.type} style={[styles.choiceBtn, selectedMonsterType === mt.type && styles.choiceBtnActive]} onPress={() => setSelectedMonsterType(mt.type)}>
                  <Text style={[styles.choiceText, selectedMonsterType === mt.type && styles.choiceTextActive]}>{mt.shortLabel}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={styles.button} onPress={startRealtimeFight}>
              <Text style={styles.buttonText}>{gameLoading ? "处理中..." : "开始战斗"}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.secondaryBtn, { marginTop: 6 }]} onPress={runMonsterFight}>
              <Text style={styles.secondaryBtnText}>快速结算（旧模式）</Text>
            </TouchableOpacity>

            <Text style={styles.sectionTitle}>技能商店</Text>
            <View style={styles.choiceRow}>
              <TouchableOpacity style={styles.smallBtn} onPress={refreshSkillShop}>
                <Text style={styles.smallBtnText}>刷新商店({skillRefreshCost}金)</Text>
              </TouchableOpacity>
            </View>
            {(shopSkills || []).map((sk) => (
              <View key={sk.skill_id} style={styles.rowItem}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "700" }}>{sk.name}</Text>
                  <Text style={styles.mutedSmall}>
                    {sk.allowed_slot}位 | 倍率x{Number(sk.damage_mult || 1).toFixed(2)} | CD {Math.round((sk.cooldown_ms || 0) / 1000)}s
                  </Text>
                  <Text style={styles.mutedSmall}>{sk.description}</Text>
                </View>
                {sk.owned ? (
                  <Text style={styles.linkText}>已拥有</Text>
                ) : (
                  <TouchableOpacity style={styles.smallBtn} onPress={() => buySkill(sk.skill_id)}>
                    <Text style={styles.smallBtnText}>{sk.gold_price} 金币</Text>
                  </TouchableOpacity>
                )}
              </View>
            ))}
            <View style={styles.choiceRow}>
              <TouchableOpacity style={styles.choiceBtn} onPress={() => exchangeDropSkill("SK_DROP_KING")}>
                <Text style={styles.choiceText}>碎片兑换 王权烙印(30)</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.choiceBtn} onPress={() => exchangeDropSkill("SK_DROP_ABYSS")}>
                <Text style={styles.choiceText}>碎片兑换 渊噬(30)</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.mutedSmall}>
              技能碎片: {gameProfile?.wallet?.skill_shard ?? 0}
            </Text>

            <Text style={styles.sectionTitle}>六技能栏（史诗+装备解锁）</Text>
            {(gameProfile?.skill_loadout || []).map((slot) => {
              return (
                <View key={`${slot.slot}-${slot.slot_index}`} style={styles.rowItem}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontWeight: "700" }}>
                      {slot.slot_label}栏 {slot.unlocked ? "" : "(未解锁)"}
                    </Text>
                    <Text style={styles.mutedSmall}>
                      当前: {slot.name || "未配置"} {slot.cooldown_ms ? `| CD ${Math.round(slot.cooldown_ms / 1000)}s` : ""}
                    </Text>
                  </View>
                  {slot.unlocked ? (
                    <View style={{ minWidth: 120, alignItems: "flex-end" }}>
                      <TouchableOpacity onPress={() => openSkillPicker(slot)}>
                        <Text style={styles.linkText}>选择技能</Text>
                      </TouchableOpacity>
                      {slot.skill_id ? (
                        <>
                          <TouchableOpacity onPress={() => specializeSkill(slot.skill_id, "burst")}>
                            <Text style={styles.mutedSmall}>专精:爆发</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => specializeSkill(slot.skill_id, "sustain")}>
                            <Text style={styles.mutedSmall}>专精:续航</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => specializeSkill(slot.skill_id, "control")}>
                            <Text style={styles.mutedSmall}>专精:控制</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => scrapSkill(slot.skill_id)}>
                            <Text style={styles.sellText}>分解技能</Text>
                          </TouchableOpacity>
                        </>
                      ) : null}
                      <TouchableOpacity onPress={() => saveSkillToSlot(slot.slot_index, null)}>
                        <Text style={styles.sellText}>清空</Text>
                      </TouchableOpacity>
                    </View>
                  ) : null}
                </View>
              );
            })}

            <Text style={styles.sectionTitle}>副本</Text>
            <View style={styles.dungeonCardList}>
              {DUNGEONS.map((d) => {
                const encounter = getDungeonEncounter(d.id);
                return (
                  <TouchableOpacity
                    key={d.id}
                    style={[styles.dungeonCard, selectedDungeon === d.id ? styles.dungeonCardActive : null]}
                    onPress={() => {
                      setSelectedDungeon(d.id);
                      setDungeonRoomIndex(0);
                    }}
                  >
                    {DUNGEON_BACKGROUNDS[d.id] ? (
                      <Image source={DUNGEON_BACKGROUNDS[d.id]} style={styles.dungeonCardBgImage} resizeMode="cover" />
                    ) : (
                      <View style={styles.dungeonBgPlaceholder}>
                        <Text style={styles.dungeonBgPlaceholderText}>{d.name} 背景</Text>
                      </View>
                    )}
                    <View style={styles.dungeonCardBody}>
                      <Text style={styles.dungeonCardTitle}>{d.name}</Text>
                      <Text style={styles.dungeonCardMeta}>最终Boss：{encounter.boss}</Text>
                      <Text style={styles.dungeonCardMeta}>节点：{(DUNGEON_NODE_LAYOUTS[d.id] || []).map((n) => NODE_TYPE_LABELS[n]).join(" / ")}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
            <View style={styles.duoBtnRow}>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={challengeDungeon}>
                <Text style={styles.buttonText}>检查等级</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, styles.duoBtn]}
                onPress={() => {
                  setDungeonRoomIndex(0);
                  setDungeonEventState({});
                  setDungeonEventOptions({});
                  setDungeonRunMods({ clearRateBonus: 0, rewardBonus: 0, bossScaleDelta: 0, curseValue: 0, greedValue: 0 });
                  setDungeonUiVisible(true);
                }}
              >
                <Text style={styles.buttonText}>进入副本界面</Text>
              </TouchableOpacity>
            </View>
            <View style={[styles.duoBtnRow, { marginTop: 8 }]}>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={settleDungeon}>
                <Text style={styles.buttonText}>策略结算（旧）</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.sectionTitle}>抽奖</Text>
            <View style={styles.choiceRow}>
              {["normal", "advanced"].map((p) => (
                <TouchableOpacity key={p} style={[styles.choiceBtn, selectedPool === p && styles.choiceBtnActive]} onPress={() => setSelectedPool(p)}>
                  <Text style={[styles.choiceText, selectedPool === p && styles.choiceTextActive]}>{p}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={styles.button} onPress={drawGacha}>
              <Text style={styles.buttonText}>抽1次</Text>
            </TouchableOpacity>

            <Text style={styles.sectionTitle}>背包（点击穿戴）</Text>
            <View style={styles.rowItem}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "700" }}>一键出售（不含已穿戴）</Text>
                <Text style={styles.mutedSmall}>出售等级 {"<="} {batchSellMaxLevel || 1} 且匹配品质</Text>
              </View>
              <TextInput
                style={[styles.input, { width: 64, marginBottom: 0, textAlign: "center" }]}
                value={batchSellMaxLevel}
                onChangeText={setBatchSellMaxLevel}
                keyboardType="number-pad"
              />
            </View>
            <View style={styles.choiceRow}>
              {["普通", "优秀", "精良", "史诗"].map((q) => (
                <TouchableOpacity
                  key={`bs-${q}`}
                  style={[styles.choiceBtn, batchSellQualities.includes(q) ? styles.choiceBtnActive : null]}
                  onPress={() => toggleBatchQuality(q)}
                >
                  <Text style={[styles.choiceText, batchSellQualities.includes(q) ? styles.choiceTextActive : null]}>
                    {q}
                  </Text>
                </TouchableOpacity>
              ))}
              <TouchableOpacity style={styles.smallBtn} onPress={sellBatch}>
                <Text style={styles.smallBtnText}>一键出售</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.choiceRow}>
              {[
                { id: "all", label: "全部" },
                { id: "equipment", label: "装备" },
                { id: "consumable", label: "道具" },
              ].map((f) => (
                <TouchableOpacity
                  key={f.id}
                  style={[styles.choiceBtn, inventoryCategoryFilter === f.id && styles.choiceBtnActive]}
                  onPress={() => setInventoryCategoryFilter(f.id)}
                >
                  <Text style={[styles.choiceText, inventoryCategoryFilter === f.id && styles.choiceTextActive]}>
                    {f.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.choiceRow}>
              {["all", "普通", "优秀", "精良", "史诗"].map((q) => (
                <TouchableOpacity
                  key={q}
                  style={[styles.choiceBtn, inventoryQualityFilter === q && styles.choiceBtnActive]}
                  onPress={() => setInventoryQualityFilter(q)}
                >
                  <Text style={[styles.choiceText, inventoryQualityFilter === q && styles.choiceTextActive]}>
                    {q}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            {filteredInventory.slice(0, 80).map((it) => (
              <View
                key={it.inventory_id}
                style={[
                  styles.rowItem,
                  styles.inventoryItemRow,
                  { borderColor: qualityBorderColor(it.quality), borderWidth: 2 },
                  it.equipped ? styles.rowSelected : null,
                ]}
              >
                {resolveEquipmentIcon(it) ? (
                  <View style={styles.inventoryIconWrap}>
                    <Image source={resolveEquipmentIcon(it)} style={styles.inventoryIcon} resizeMode="contain" />
                  </View>
                ) : null}
                <View style={{ flex: 1 }}>
                  <Text>{it.name}</Text>
                  <Text style={styles.mutedSmall}>
                    {it.category === "consumable" ? "道具" : "装备"} | {it.quality} | {it.slot} | 战力+{it.power}{" "}
                    {it.set_key ? `| 套装:${it.set_key}` : ""}
                  </Text>
                  {it.category === "equipment" ? (
                    <Text style={styles.mutedSmall}>
                      HP+{it.hp} ATK+{it.attack} DEF+{it.defense} | 闪避 {formatPercent(it.dodge)} | 暴击 {formatPercent(it.crit)} | 格挡 {formatPercent(it.block)} | 吸血 {formatPercent(it.lifesteal)}
                    </Text>
                  ) : null}
                  {it.affixes?.length ? (
                    <Text style={styles.mutedSmall}>
                      词条: {it.affixes.map((a) => a.text).join(" / ")}
                    </Text>
                  ) : null}
                </View>
                <View style={styles.inventoryActionCol}>
                  {it.category === "equipment" ? (
                    <TouchableOpacity onPress={() => equipItem(it.inventory_id)}>
                      <Text style={styles.linkText}>{it.equipped ? "已穿戴" : "穿戴"}</Text>
                    </TouchableOpacity>
                  ) : null}
                  <TouchableOpacity onPress={() => sellItem(it.inventory_id)}>
                    <Text style={styles.sellText}>出售</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}

            <Text style={styles.sectionTitle}>操作日志</Text>
            {(gameActionLog || []).map((log, idx) => (
              <Text key={`${log}-${idx}`} style={styles.logText}>{log}</Text>
            ))}
            <TouchableOpacity style={styles.secondaryBtn} onPress={refreshGameState}>
              <Text style={styles.secondaryBtnText}>刷新游戏状态</Text>
            </TouchableOpacity>
          </ScrollView>
        )}
      </KeyboardAvoidingView>

      <Modal
        visible={fightUiVisible}
        transparent
        animationType="fade"
        onRequestClose={closeFightUi}
      >
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: "90%" }]}>
            <Text style={styles.modalTitle}>实时战斗</Text>
            <Text style={styles.infoText}>
              {fightSnapshot?.fight_mode === "dungeon"
                ? `${getDungeonName(selectedDungeon)} - ${getDungeonBossName(selectedDungeon)}`
                : `${getMapName(selectedMap)} - ${getMonsterDisplayName(selectedMap, selectedMonsterType)}`}
            </Text>
            <Text style={styles.infoText}>
              预计胜率: {Math.round((fightSnapshot?.win_rate_estimate || 0) * 100)}%
            </Text>
            <View style={styles.fightPortraitRow}>
              <Animated.View
                style={[
                  styles.fightPortraitWrap,
                  {
                    borderColor: "#30c670",
                    backgroundColor: playerHitFlash.interpolate({
                      inputRange: [0, 1],
                      outputRange: ["#1e2a2f", "#4d1f1f"],
                    }),
                  },
                ]}
              >
                {fightPlayerPortrait ? (
                  <Image source={fightPlayerPortrait} style={styles.fightPortraitImage} resizeMode="contain" />
                ) : (
                  <Text style={styles.fightPortraitFallback}>你</Text>
                )}
              </Animated.View>
              <Animated.View
                style={[
                  styles.fightPortraitWrap,
                  {
                    borderColor: "#e24b4b",
                    backgroundColor: monsterHitFlash.interpolate({
                      inputRange: [0, 1],
                      outputRange: ["#2a2020", "#5f2a2a"],
                    }),
                  },
                ]}
              >
                {fightMonsterPortrait ? (
                  <Image source={fightMonsterPortrait} style={styles.fightPortraitImage} resizeMode="contain" />
                ) : (
                  <Text style={styles.fightPortraitFallback}>敌</Text>
                )}
              </Animated.View>
            </View>
            <View style={styles.floatingLayer}>
              {floatingTexts.map((f) => (
                <Text
                  key={f.id}
                  style={[
                    styles.floatingText,
                    f.target === "monster" ? styles.floatingTextMonster : styles.floatingTextPlayer,
                    { color: f.color },
                  ]}
                >
                  {f.text}
                </Text>
              ))}
            </View>
            <View style={styles.choiceRow}>
              <TouchableOpacity
                style={[styles.choiceBtn, autoBasicEnabled ? styles.choiceBtnActive : null]}
                onPress={() => setAutoBasicEnabled((v) => !v)}
              >
                <Text style={[styles.choiceText, autoBasicEnabled ? styles.choiceTextActive : null]}>
                  自动普攻: {autoBasicEnabled ? "开" : "关"}
                </Text>
              </TouchableOpacity>
            </View>
            <View style={styles.hpBarWrap}>
              <Text style={styles.mutedSmall}>玩家 HP {fightPlayerHp}/{fightSnapshot?.player?.max_hp || 0}</Text>
              <View style={styles.hpBarBg}>
                <View
                  style={[
                    styles.hpBarFillPlayer,
                    { width: `${Math.max(0, Math.min(100, (fightPlayerHp / Math.max(1, fightSnapshot?.player?.max_hp || 1)) * 100))}%` },
                  ]}
                />
              </View>
            </View>
            <View style={styles.hpBarWrap}>
              <Text style={styles.mutedSmall}>怪物 HP {fightMonsterHp}/{fightSnapshot?.monster?.max_hp || 0}</Text>
              <View style={styles.hpBarBg}>
                <View
                  style={[
                    styles.hpBarFillMonster,
                    { width: `${Math.max(0, Math.min(100, (fightMonsterHp / Math.max(1, fightSnapshot?.monster?.max_hp || 1)) * 100))}%` },
                  ]}
                />
              </View>
            </View>

            <View style={styles.choiceRow}>
              <TouchableOpacity
                style={[styles.button, { flex: 1, opacity: fightNow < basicReadyAt || fightNow < playerActionLockedUntil || fightEnded ? 0.5 : 1 }]}
                onPress={castBasicAttack}
                disabled={fightNow < basicReadyAt || fightNow < playerActionLockedUntil || fightEnded}
              >
                <Text style={styles.buttonText}>
                  普攻 {fightNow < basicReadyAt ? `${((basicReadyAt - fightNow) / 1000).toFixed(1)}s` : fightNow < playerActionLockedUntil ? "硬直中" : ""}
                </Text>
              </TouchableOpacity>
            </View>

            <View style={styles.skillGrid}>
              {(fightSnapshot?.player?.skill_bar || []).map((slot) => {
                const readyAt = skillReadyAts[slot.slot_index] || 0;
                const locked = !slot.unlocked || !slot.skill_id;
                const cooling = fightNow < readyAt || fightNow < playerActionLockedUntil;
                return (
                  <TouchableOpacity
                    key={`${slot.slot_index}-${slot.skill_id || "none"}`}
                    style={[styles.skillCell, locked ? styles.skillCellLocked : null, cooling ? styles.skillCellCooling : null]}
                    onPress={() => castSkill(slot.slot_index)}
                    disabled={locked || cooling || fightEnded}
                  >
                    <Text style={styles.skillCellTitle}>{slot.name || `${slot.slot_label}栏`}</Text>
                    <Text style={styles.mutedSmall}>
                      {locked ? "需史诗+并配置技能" : fightNow < playerActionLockedUntil ? "硬直中" : cooling ? `CD ${((readyAt - fightNow) / 1000).toFixed(1)}s` : "可释放"}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <ScrollView style={{ maxHeight: 170, marginTop: 8 }}>
              {fightLog.map((line, idx) => (
                <Text key={`${line}-${idx}`} style={styles.logText}>{line}</Text>
              ))}
            </ScrollView>

            <View style={styles.duoBtnRow}>
              <TouchableOpacity
                style={[styles.button, styles.duoBtn, { opacity: fightEnded ? 1 : 0.5 }]}
                onPress={finishRealtimeFight}
                disabled={!fightEnded || fightCommitting}
              >
                <Text style={styles.buttonText}>{fightCommitting ? "结算中..." : "结算战斗"}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.secondaryBtn, styles.duoBtn]} onPress={closeFightUi}>
                <Text style={styles.secondaryBtnText}>关闭</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <Modal
        visible={skillPickerVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setSkillPickerVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: "78%" }]}>
            <Text style={styles.modalTitle}>
              选择技能 - {skillPickerSlot?.slot_label || ""}
            </Text>
            <ScrollView style={styles.modalScroll}>
              {availableSkillsForSlot.length ? (
                availableSkillsForSlot.map((s) => (
                  <TouchableOpacity
                    key={s.skill_id}
                    style={styles.skillPickerRow}
                    onPress={async () => {
                      if (!skillPickerSlot) return;
                      await saveSkillToSlot(skillPickerSlot.slot_index, s.skill_id);
                      setSkillPickerVisible(false);
                    }}
                  >
                    <Text style={styles.skillPickerTitle}>{s.name}</Text>
                    <Text style={styles.mutedSmall}>
                      倍率x{Number(s.damage_mult || 1).toFixed(2)} | 回复{Math.round((s.heal_pct_max || 0) * 100)}% | CD {Math.round((s.cooldown_ms || 0) / 1000)}s
                    </Text>
                    <Text style={styles.mutedSmall}>
                      {s.description} {s.drop_only ? "| Boss掉落技能" : ""} | 专精:{s.branch || "burst"} Lv{s.mastery_level || 0}
                    </Text>
                  </TouchableOpacity>
                ))
              ) : (
                <Text style={styles.muted}>当前栏位没有可选技能（先购买或掉落）</Text>
              )}
            </ScrollView>
            <TouchableOpacity style={styles.secondaryBtn} onPress={() => setSkillPickerVisible(false)}>
              <Text style={styles.secondaryBtnText}>关闭</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal
        visible={dungeonUiVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setDungeonUiVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, styles.dungeonUiCard]}>
            <ScrollView style={styles.modalScroll} contentContainerStyle={{ paddingBottom: 12 }}>
            <Text style={styles.modalTitle}>{selectedDungeonMeta?.name || "副本"}</Text>
            {DUNGEON_BACKGROUNDS[selectedDungeon] ? (
              <Image source={DUNGEON_BACKGROUNDS[selectedDungeon]} style={styles.dungeonScreenBgImage} resizeMode="cover" />
            ) : (
              <View style={styles.dungeonScreenBg}>
                <Text style={styles.dungeonScreenBgText}>
                  预留背景图：`mobile/assets/dungeons/backgrounds/{selectedDungeon}.png`
                </Text>
              </View>
            )}
            <View style={styles.dungeonHeroRow}>
              {DUNGEON_BOSS_IMAGES[selectedDungeon] ? (
                <Image source={DUNGEON_BOSS_IMAGES[selectedDungeon]} style={styles.dungeonBossPortraitImage} resizeMode="cover" />
              ) : (
                <View style={styles.dungeonBossPortrait}>
                  <Text style={styles.dungeonBossPortraitText}>
                    预留Boss图：`mobile/assets/dungeons/bosses/{selectedDungeon}.png`
                  </Text>
                </View>
              )}
              <View style={styles.dungeonBossInfo}>
                <Text style={styles.dungeonBossName}>{selectedDungeonEncounter.boss}</Text>
                <Text style={styles.dungeonBossMeta}>小怪：{selectedDungeonEncounter.trash}</Text>
                <Text style={styles.dungeonBossMeta}>精英：{selectedDungeonEncounter.elite}</Text>
                <Text style={styles.dungeonBossMeta}>当前房间：{dungeonRoomIndex + 1}/{selectedDungeonNodes.length}</Text>
              </View>
            </View>
            <Text style={styles.sectionTitle}>路线节点</Text>
            <View style={styles.nodeRow}>
              {selectedDungeonNodes.map((node, idx) => (
                <View key={`${node}-${idx}`} style={styles.nodeItem}>
                  {DUNGEON_NODE_ICONS[node] ? (
                    <View
                      style={[
                        styles.nodeImageWrap,
                        idx === dungeonRoomIndex ? styles.nodeIconActive : null,
                        node === "boss" ? styles.nodeIconBoss : null,
                      ]}
                    >
                      <Image source={DUNGEON_NODE_ICONS[node]} style={styles.nodeImage} resizeMode="contain" />
                    </View>
                  ) : (
                    <View
                      style={[
                        styles.nodeIconPlaceholder,
                        idx === dungeonRoomIndex ? styles.nodeIconActive : null,
                        node === "boss" ? styles.nodeIconBoss : null,
                      ]}
                    >
                      <Text style={styles.nodeIconPlaceholderText}>{NODE_TYPE_LABELS[node]}</Text>
                    </View>
                  )}
                  <Text style={styles.nodeIndexText}>{idx + 1}</Text>
                </View>
              ))}
            </View>
            <View style={styles.dungeonActionPanel}>
              <Text style={styles.dungeonActionTitle}>当前房间事件</Text>
              <Text style={styles.dungeonActionText}>
                {NODE_TYPE_LABELS[currentDungeonNodeType] || "未知房间"}：
                {currentDungeonNodeType === "boss"
                  ? ` 面对 ${selectedDungeonEncounter.boss}`
                  : currentDungeonNodeType === "elite"
                    ? ` 面对 ${selectedDungeonEncounter.elite}`
                    : currentDungeonNodeType === "normal"
                      ? ` 面对 ${selectedDungeonEncounter.trash}`
                      : currentDungeonNodeType === "treasure"
                        ? " 可配置宝箱奖励"
                        : " 可配置恢复效果"}
              </Text>
              {["treasure", "heal", "elite"].includes(currentDungeonNodeType) ? (
                <View style={{ marginTop: 8 }}>
                  {(() => {
                    const roomKey = `${selectedDungeon}-${dungeonRoomIndex}`;
                    const options = dungeonEventOptions[roomKey] || [];
                    if (!options.length) return <Text style={styles.mutedSmall}>暂无事件选项，尝试切换房间重试</Text>;
                    return options.map((c) => {
                      const selected = dungeonEventState[roomKey] === c.id;
                      return (
                        <TouchableOpacity
                          key={c.id}
                          style={[styles.choiceBtn, selected ? styles.choiceBtnActive : null, { marginBottom: 6 }]}
                          disabled={Boolean(dungeonEventState[roomKey])}
                          onPress={() => applyDungeonChoice(c)}
                        >
                          <Text style={[styles.choiceText, selected ? styles.choiceTextActive : null]}>{c.label}</Text>
                        </TouchableOpacity>
                      );
                    });
                  })()}
                </View>
              ) : null}
              <Text style={styles.mutedSmall}>
                事件加成：通关率 {Math.round((dungeonRunMods.clearRateBonus || 0) * 100)}% | 奖励 {Math.round((dungeonRunMods.rewardBonus || 0) * 100)}% | Boss强度 {Math.round((dungeonRunMods.bossScaleDelta || 0) * 100)}%
              </Text>
              <Text style={styles.mutedSmall}>
                风险轨道：诅咒 {Math.round((dungeonRunMods.curseValue || 0) * 100)} | 贪婪 {Math.round((dungeonRunMods.greedValue || 0) * 100)}
              </Text>
            </View>
            <View style={styles.duoBtnRow}>
              <TouchableOpacity
                style={[styles.secondaryBtn, styles.duoBtn]}
                onPress={() => setDungeonRoomIndex((prev) => Math.max(0, prev - 1))}
              >
                <Text style={styles.secondaryBtnText}>上一房间</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.secondaryBtn, styles.duoBtn]}
                onPress={() =>
                  setDungeonRoomIndex((prev) => Math.min(selectedDungeonNodes.length - 1, prev + 1))
                }
              >
                <Text style={styles.secondaryBtnText}>下一房间</Text>
              </TouchableOpacity>
            </View>
            <View style={[styles.duoBtnRow, { marginTop: 8 }]}>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={startDungeonRealtimeFight}>
                <Text style={styles.buttonText}>发起实时Boss战</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={() => setDungeonUiVisible(false)}>
                <Text style={styles.buttonText}>退出副本界面</Text>
              </TouchableOpacity>
            </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      <Modal
        visible={equipModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setEquipModalVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>更换{SLOT_LABELS[equipModalSlot] || "装备"}</Text>
            <ScrollView style={styles.modalScroll}>
              {equipCandidates.length ? (
                equipCandidates.map((item) => (
                  <TouchableOpacity
                    key={item.inventory_id}
                    style={[
                      styles.modalEquipRow,
                      { borderColor: qualityBorderColor(item.quality), borderWidth: 2 },
                      item.equipped ? styles.rowSelected : null,
                    ]}
                    onPress={() => equipItem(item.inventory_id)}
                  >
                    {resolveEquipmentIcon(item) ? (
                      <Image source={resolveEquipmentIcon(item)} style={styles.modalEquipIcon} resizeMode="contain" />
                    ) : null}
                    <View style={{ flex: 1 }}>
                      <Text style={styles.modalEquipName}>{item.name}</Text>
                      <Text style={styles.mutedSmall}>
                        {item.quality} | Lv{item.level_required} | 战力+{item.power}
                      </Text>
                      <Text style={styles.mutedSmall}>
                        HP+{item.hp} ATK+{item.attack} DEF+{item.defense}
                      </Text>
                      {item.affixes?.length ? (
                        <Text style={styles.mutedSmall} numberOfLines={2}>
                          词条: {item.affixes.map((a) => a.text).join(" / ")}
                        </Text>
                      ) : null}
                    </View>
                  </TouchableOpacity>
                ))
              ) : (
                <Text style={styles.muted}>该部位暂无可替换装备</Text>
              )}
            </ScrollView>
            <TouchableOpacity style={styles.secondaryBtn} onPress={() => setEquipModalVisible(false)}>
              <Text style={styles.secondaryBtnText}>关闭</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal
        visible={resultModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => {
          setResultModalVisible(false);
          setGachaRevealPhase("revealed");
        }}
      >
        <View style={styles.modalBackdrop}>
          <Animated.View
            style={[
              styles.modalCard,
              resultModalHasEpic ? styles.modalCardEpic : null,
              resultModalIsGacha ? styles.modalCardGacha : null,
              { transform: [{ scale: epicAppearAnim }] },
            ]}
          >
            <View
              style={[
                styles.resultBanner,
                resultModalHasEpic ? styles.resultBannerEpic : null,
                resultModalIsBoss ? styles.resultBannerBoss : null,
                resultModalIsGacha ? styles.resultBannerGacha : null,
              ]}
            >
              <Text
                style={[
                  styles.resultBannerEyebrow,
                  resultModalHasEpic ? styles.resultBannerEyebrowEpic : null,
                ]}
              >
                {resultModalIsBoss ? "BOSS 掉落" : resultModalIsGacha ? "命运显现" : "战斗结果"}
              </Text>
              <Text
                style={[
                  styles.modalTitle,
                  styles.resultModalTitle,
                  resultModalHasEpic ? styles.resultModalTitleEpic : null,
                ]}
              >
                {resultModalTitle || "结果"}
              </Text>
              {resultModalHasEpic ? (
                <Text style={styles.resultRareText}>紫光闪耀，你获得了高价值战利品</Text>
              ) : null}
            </View>
            <ScrollView style={styles.modalScroll}>
              {resultModalSummary.map((line, idx) => (
                <Text key={`${line}-${idx}`} style={styles.modalSummaryText}>{line}</Text>
              ))}
              {resultModalHasEpic && resultEpicStage === "rarity" ? (
                <View style={styles.rareRevealBox}>
                  <Text style={styles.rareRevealTitle}>稀有度揭示</Text>
                  <Text style={styles.rareRevealBody}>史诗以上战利品出现，词条正在鉴定...</Text>
                </View>
              ) : null}
              {resultModalItems.length && resultEpicStage === "detail" ? (
                <View style={styles.rewardGrid}>
                  {resultModalItems.map((item, idx) => (
                    <Animated.View
                      key={`${item.inventory_id || item.item_id || item.name}-${idx}`}
                      style={[
                        styles.rewardCard,
                        { borderColor: qualityBorderColor(item.quality || "普通") },
                        item.quality === "史诗" ? styles.rewardCardEpic : null,
                        item.quality === "史诗"
                          ? {
                              transform: [{ scale: epicPulseAnim }],
                            }
                          : null,
                      ]}
                    >
                      {resultModalIsGacha && gachaRevealPhase === "flipping" ? (
                        <Animated.View
                          style={[
                            styles.gachaCardBack,
                            {
                              transform: [
                                {
                                  rotateY: gachaFlipAnim.interpolate({
                                    inputRange: [0, 1],
                                    outputRange: ["0deg", "88deg"],
                                  }),
                                },
                              ],
                            },
                          ]}
                        >
                          <Text style={styles.gachaCardBackText}>命运之牌</Text>
                          <Text style={styles.gachaCardBackSub}>正在揭晓...</Text>
                        </Animated.View>
                      ) : (
                        <>
                          <View
                            style={[
                              styles.rewardBadge,
                              item.quality === "史诗" ? styles.rewardBadgeEpic : styles.rewardBadgeNormal,
                            ]}
                          >
                            <Text
                              style={[
                                styles.rewardBadgeText,
                                item.quality === "史诗" ? styles.rewardBadgeTextEpic : null,
                              ]}
                            >
                              {rewardTitleByQuality(item.quality)}
                            </Text>
                          </View>
                          {resolveEquipmentIcon(item) ? (
                            <Image source={resolveEquipmentIcon(item)} style={styles.rewardIcon} resizeMode="contain" />
                          ) : null}
                          <Text style={styles.rewardName} numberOfLines={2}>{item.name}</Text>
                          <Text style={styles.rewardMeta}>{item.quality || "-"} | {SLOT_LABELS[item.slot] || item.slot || "-"}</Text>
                          {item.affixes?.length ? (
                            <Text style={styles.rewardMeta} numberOfLines={3}>词条: {item.affixes.map((a) => a.text).join(" / ")}</Text>
                          ) : null}
                        </>
                      )}
                    </Animated.View>
                  ))}
                </View>
              ) : null}
            </ScrollView>
            <TouchableOpacity
              style={styles.button}
              onPress={() => {
                setResultModalVisible(false);
                setGachaRevealPhase("revealed");
              }}
            >
              <Text style={styles.buttonText}>确定</Text>
            </TouchableOpacity>
          </Animated.View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f2f4f8", justifyContent: "center" },
  loginCard: { margin: 20, padding: 20, borderRadius: 14, backgroundColor: "#fff", shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 8, elevation: 3 },
  title: { fontSize: 28, fontWeight: "700", marginBottom: 8 },
  subtitle: { fontSize: 14, color: "#666", marginBottom: 12 },
  errorText: { marginBottom: 10, color: "#d63737", fontWeight: "600" },
  switchModeBtn: { marginTop: 10, alignItems: "center" },
  switchModeText: { color: "#246bff", fontWeight: "600" },
  input: { borderColor: "#d0d7e2", borderWidth: 1, borderRadius: 10, backgroundColor: "#fff", paddingHorizontal: 12, paddingVertical: 10, fontSize: 16, marginBottom: 12 },
  button: { backgroundColor: "#246bff", borderRadius: 10, paddingVertical: 12, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  chatWrap: { flex: 1, padding: 12 },
  header: { paddingVertical: 8, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  headerTitle: { fontSize: 14, fontWeight: "600", flex: 1, marginRight: 8 },
  leaveText: { color: "#d63737", fontWeight: "600" },
  modeRow: { flexDirection: "row", gap: 8, marginBottom: 8 },
  modeBtn: { flex: 1, backgroundColor: "#dfe5f1", borderRadius: 8, paddingVertical: 8, alignItems: "center" },
  modeBtnActive: { backgroundColor: "#246bff" },
  modeText: { color: "#203050", fontWeight: "700", fontSize: 12 },
  modeTextActive: { color: "#fff" },
  tabRow: { flexDirection: "row", marginBottom: 8, gap: 6 },
  tab: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: "#e4e9f2", alignItems: "center" },
  tabActive: { backgroundColor: "#246bff" },
  tabText: { fontSize: 12, color: "#333", fontWeight: "600" },
  tabTextActive: { color: "#fff" },
  list: { flex: 1 },
  chatBubble: { backgroundColor: "#fff", borderRadius: 10, padding: 10, marginBottom: 8 },
  systemBubble: { backgroundColor: "#eaf0ff", borderRadius: 10, padding: 10, marginBottom: 8 },
  sender: { fontWeight: "700", marginBottom: 4 },
  messageText: { fontSize: 15 },
  inputRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingTop: 8 },
  chatInput: { flex: 1, marginBottom: 0 },
  sendButton: { paddingHorizontal: 16 },
  sideScroll: { flex: 1, marginBottom: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "700", marginTop: 12, marginBottom: 8, color: "#1a2744" },
  muted: { color: "#888", marginBottom: 8 },
  mutedSmall: { color: "#888", fontSize: 12, marginTop: 4 },
  rowItem: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 12, backgroundColor: "#fff", borderRadius: 10, marginBottom: 8 },
  rowSelected: { borderWidth: 2, borderColor: "#246bff" },
  inventoryItemRow: { alignItems: "center" },
  inventoryIconWrap: { width: 58, height: 58, borderRadius: 10, backgroundColor: "#eef2fa", alignItems: "center", justifyContent: "center", marginRight: 10, overflow: "hidden" },
  inventoryIcon: { width: 48, height: 48 },
  inventoryActionCol: { alignItems: "flex-end", gap: 8, marginLeft: 10 },
  sellText: { color: "#d63737", fontWeight: "700" },
  smallBtn: { backgroundColor: "#246bff", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  smallBtnText: { color: "#fff", fontWeight: "600" },
  secondaryBtn: { marginTop: 8, alignItems: "center", padding: 8 },
  secondaryBtnText: { color: "#246bff", fontWeight: "600" },
  groupManage: { marginBottom: 8 },
  inviteRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  inviteInput: { flex: 1, marginBottom: 0 },
  inviteBtn: { paddingHorizontal: 14, paddingVertical: 10 },
  infoText: { fontSize: 13, marginBottom: 4, color: "#203050" },
  equippedGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 8 },
  equippedCell: { width: "30%", minWidth: 92, alignItems: "center", marginBottom: 8 },
  equippedIconWrap: { width: 66, height: 66, borderRadius: 12, borderWidth: 2, backgroundColor: "#eef2fa", alignItems: "center", justifyContent: "center", overflow: "hidden" },
  equippedEmpty: { borderColor: "#cfd7e6" },
  equippedIcon: { width: 54, height: 54 },
  equippedSlotText: { marginTop: 6, fontSize: 12, fontWeight: "700", color: "#233" },
  equippedNameText: { marginTop: 2, fontSize: 11, color: "#667", textAlign: "center" },
  choiceRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  dungeonCardList: { gap: 10, marginBottom: 8 },
  dungeonCard: { backgroundColor: "#fff", borderRadius: 14, overflow: "hidden", borderWidth: 2, borderColor: "#dbe2ee" },
  dungeonCardActive: { borderColor: "#246bff" },
  dungeonBgPlaceholder: { height: 90, backgroundColor: "#243046", alignItems: "center", justifyContent: "center" },
  dungeonCardBgImage: { width: "100%", height: 90 },
  dungeonBgPlaceholderText: { color: "#d9e3f7", fontSize: 12, fontWeight: "700" },
  dungeonCardBody: { padding: 12 },
  dungeonCardTitle: { fontSize: 15, fontWeight: "700", color: "#1a2744", marginBottom: 4 },
  dungeonCardMeta: { fontSize: 12, color: "#6b7485", marginBottom: 2 },
  choiceBtn: { backgroundColor: "#e4e9f2", borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10 },
  choiceBtnActive: { backgroundColor: "#246bff" },
  choiceText: { color: "#233", fontWeight: "600", fontSize: 12 },
  choiceTextActive: { color: "#fff" },
  duoBtnRow: { flexDirection: "row", gap: 8 },
  duoBtn: { flex: 1 },
  rewardGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginBottom: 8 },
  rewardCard: { width: "47%", minWidth: 145, backgroundColor: "#fff", borderRadius: 12, borderWidth: 2, padding: 10, alignItems: "center" },
  rewardCardPlain: { borderColor: "#d8dfec" },
  rewardIcon: { width: 56, height: 56, marginBottom: 6 },
  rewardName: { fontSize: 12, fontWeight: "700", color: "#203050", textAlign: "center" },
  rewardMeta: { marginTop: 4, fontSize: 11, color: "#6b7485", textAlign: "center" },
  rewardTextOnlyBox: { width: 56, height: 56, borderRadius: 10, backgroundColor: "#eef2fa", alignItems: "center", justifyContent: "center", marginBottom: 6 },
  rewardTextOnly: { fontSize: 11, fontWeight: "700", color: "#51617d", textAlign: "center" },
  hpBarWrap: { marginTop: 8, marginBottom: 4 },
  hpBarBg: { height: 12, borderRadius: 999, backgroundColor: "#dbe2ee", overflow: "hidden" },
  hpBarFillPlayer: { height: "100%", backgroundColor: "#30c670" },
  hpBarFillMonster: { height: "100%", backgroundColor: "#e24b4b" },
  skillGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  skillCell: { width: "31%", minWidth: 98, borderRadius: 10, backgroundColor: "#eaf0ff", padding: 8 },
  skillCellLocked: { backgroundColor: "#ececec" },
  skillCellCooling: { backgroundColor: "#d8e0f3" },
  skillCellTitle: { fontWeight: "700", fontSize: 12, color: "#1a2744" },
  floatingLayer: { minHeight: 18, marginBottom: 6 },
  floatingText: { position: "absolute", fontWeight: "800", fontSize: 16 },
  floatingTextPlayer: { left: 22, top: 0 },
  floatingTextMonster: { right: 22, top: 0 },
  fightPortraitRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 8, marginBottom: 8, gap: 10 },
  fightPortraitWrap: { flex: 1, height: 120, borderRadius: 12, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  fightPortraitImage: { width: 90, height: 90 },
  fightPortraitFallback: { color: "#fff", fontWeight: "800", fontSize: 20 },
  skillPickerRow: { backgroundColor: "#f3f6fd", borderRadius: 10, padding: 10, marginBottom: 8 },
  skillPickerTitle: { fontWeight: "700", color: "#1a2744" },
  modalBackdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)", justifyContent: "center", padding: 18 },
  modalCard: { maxHeight: "78%", backgroundColor: "#fff", borderRadius: 16, padding: 16 },
  dungeonUiCard: { maxHeight: "88%" },
  modalCardEpic: { backgroundColor: "#161120", borderColor: "#b06cff", borderWidth: 2, shadowColor: "#b06cff", shadowOpacity: 0.35, shadowRadius: 16, elevation: 10 },
  modalCardGacha: { shadowColor: "#ffd24a", shadowOpacity: 0.22, shadowRadius: 14, elevation: 8 },
  modalTitle: { fontSize: 18, fontWeight: "700", color: "#1a2744", marginBottom: 12 },
  dungeonScreenBg: { height: 132, borderRadius: 14, backgroundColor: "#202b3d", alignItems: "center", justifyContent: "center", marginBottom: 12, padding: 12 },
  dungeonScreenBgImage: { width: "100%", height: 132, borderRadius: 14, marginBottom: 12 },
  dungeonScreenBgText: { color: "#d6def1", fontSize: 12, fontWeight: "700", textAlign: "center" },
  dungeonHeroRow: { flexDirection: "row", gap: 10, marginBottom: 12 },
  dungeonBossPortrait: { width: 120, height: 120, borderRadius: 14, backgroundColor: "#2f2436", alignItems: "center", justifyContent: "center", padding: 10 },
  dungeonBossPortraitImage: { width: 120, height: 120, borderRadius: 14 },
  dungeonBossPortraitText: { color: "#ead7ff", fontSize: 12, textAlign: "center", fontWeight: "700" },
  dungeonBossInfo: { flex: 1, backgroundColor: "#f5f7fb", borderRadius: 14, padding: 12 },
  dungeonBossName: { fontSize: 15, fontWeight: "800", color: "#1a2744", marginBottom: 8 },
  dungeonBossMeta: { fontSize: 12, color: "#53627b", marginBottom: 4 },
  nodeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  nodeItem: { alignItems: "center" },
  nodeImageWrap: { width: 62, height: 54, borderRadius: 12, backgroundColor: "#eef2fa", alignItems: "center", justifyContent: "center", overflow: "hidden" },
  nodeImage: { width: 42, height: 42 },
  nodeIconPlaceholder: { minWidth: 62, minHeight: 54, paddingHorizontal: 8, paddingVertical: 8, borderRadius: 12, backgroundColor: "#eef2fa", alignItems: "center", justifyContent: "center" },
  nodeIconActive: { backgroundColor: "#dbe8ff", borderWidth: 2, borderColor: "#246bff" },
  nodeIconBoss: { backgroundColor: "#ffe2e2" },
  nodeIconPlaceholderText: { fontSize: 11, fontWeight: "700", color: "#384964", textAlign: "center" },
  nodeIndexText: { marginTop: 4, fontSize: 11, color: "#667" },
  dungeonActionPanel: { backgroundColor: "#f5f7fb", borderRadius: 14, padding: 12, marginBottom: 8 },
  dungeonActionTitle: { fontSize: 13, fontWeight: "800", color: "#1a2744", marginBottom: 6 },
  dungeonActionText: { fontSize: 12, color: "#53627b", lineHeight: 18 },
  resultModalTitle: { marginBottom: 2 },
  resultModalTitleEpic: { color: "#f4e8ff" },
  rareRevealBox: {
    borderWidth: 1,
    borderColor: "#c693ff",
    backgroundColor: "#261736",
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 12,
    marginBottom: 10,
  },
  rareRevealTitle: { color: "#f2ddff", fontWeight: "700", marginBottom: 4 },
  rareRevealBody: { color: "#d8b9ff", fontSize: 12 },
  resultBanner: { borderRadius: 14, paddingVertical: 12, paddingHorizontal: 12, marginBottom: 12, backgroundColor: "#eef3ff" },
  resultBannerEpic: { backgroundColor: "#2a193f" },
  resultBannerBoss: { backgroundColor: "#3a1b1b" },
  resultBannerGacha: { backgroundColor: "#3b3212" },
  resultBannerEyebrow: { fontSize: 11, fontWeight: "700", color: "#52607a", marginBottom: 4, letterSpacing: 0.5 },
  resultBannerEyebrowEpic: { color: "#d7b4ff" },
  resultRareText: { fontSize: 12, color: "#d9c0ff", marginTop: 4, fontWeight: "600" },
  modalScroll: { marginBottom: 10 },
  modalEquipRow: { flexDirection: "row", alignItems: "center", backgroundColor: "#fff", borderRadius: 12, padding: 10, marginBottom: 8 },
  modalEquipIcon: { width: 56, height: 56, marginRight: 10 },
  modalEquipName: { fontSize: 13, fontWeight: "700", color: "#203050" },
  modalSummaryText: { fontSize: 13, color: "#31415f", marginBottom: 6 },
  rewardCardEpic: { backgroundColor: "#20142d", shadowColor: "#b06cff", shadowOpacity: 0.3, shadowRadius: 14, elevation: 8 },
  rewardBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999, marginBottom: 6 },
  rewardBadgeNormal: { backgroundColor: "#eef2fa" },
  rewardBadgeEpic: { backgroundColor: "#4f2a73" },
  rewardBadgeText: { fontSize: 10, fontWeight: "700", color: "#51617d" },
  rewardBadgeTextEpic: { color: "#f5e8ff" },
  gachaCardBack: { width: "100%", minHeight: 150, borderRadius: 12, backgroundColor: "#2e2611", borderWidth: 2, borderColor: "#d9b648", alignItems: "center", justifyContent: "center", padding: 12 },
  gachaCardBackText: { fontSize: 18, fontWeight: "800", color: "#ffe395", marginBottom: 8 },
  gachaCardBackSub: { fontSize: 12, color: "#f3ddb4" },
  linkText: { color: "#246bff", fontWeight: "600" },
  logText: { fontSize: 12, color: "#2d3b66", marginBottom: 4, backgroundColor: "#f0f4ff", padding: 6, borderRadius: 6 },
});
