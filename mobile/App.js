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
  const [selectedMap, setSelectedMap] = useState("M01");
  const [selectedMonsterType, setSelectedMonsterType] = useState("普通怪");
  const [selectedDungeon, setSelectedDungeon] = useState("DUN30");
  const [selectedPool, setSelectedPool] = useState("normal");
  const [dungeonUiVisible, setDungeonUiVisible] = useState(false);
  const [dungeonRoomIndex, setDungeonRoomIndex] = useState(0);
  const [, setLatestLootItems] = useState([]);
  const [, setLatestDrawRewards] = useState([]);
  const [equipModalSlot, setEquipModalSlot] = useState("");
  const [equipModalVisible, setEquipModalVisible] = useState(false);
  const [resultModalVisible, setResultModalVisible] = useState(false);
  const [resultModalTitle, setResultModalTitle] = useState("");
  const [resultModalItems, setResultModalItems] = useState([]);
  const [resultModalSummary, setResultModalSummary] = useState([]);
  const [gachaRevealPhase, setGachaRevealPhase] = useState("revealed");

  const socketRef = useRef(null);
  const epicPulseAnim = useRef(new Animated.Value(1)).current;
  const epicAppearAnim = useRef(new Animated.Value(0.88)).current;
  const gachaFlipAnim = useRef(new Animated.Value(0)).current;
  const wsUrl = useMemo(() => `${WS_BASE}?token=${encodeURIComponent(token)}`, [token]);
  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  const pushGameLog = (text) => {
    setGameActionLog((prev) => [`${new Date().toLocaleTimeString()} ${text}`, ...prev].slice(0, 30));
  };

  const formatPercent = (value) => `${Math.round((value || 0) * 1000) / 10}%`;

  const openResultModal = (title, items = [], summary = []) => {
    setResultModalTitle(title);
    setResultModalItems(items);
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
  }, [token, refreshGameState]);

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

  const challengeDungeon = async () => {
    const res = await callGameApi("/game/dungeon/challenge", "POST", { dungeon_id: selectedDungeon });
    if (res.ok) {
      const dungeonName = getDungeonName(selectedDungeon);
      pushGameLog(res.data.ok ? `${dungeonName} 门槛已达标` : `${dungeonName} 未达标: ${res.data.reason}`);
      if (res.data.ok) {
        setDungeonRoomIndex(0);
        setDungeonUiVisible(true);
      }
      if (res.data.required_stats) {
        pushGameLog(
          `副本属性要求 HP${res.data.required_stats.hp || 0} / ATK${res.data.required_stats.attack || 0} / DEF${res.data.required_stats.defense || 0}`,
        );
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
      const res = await callGameApi("/game/dungeon/settle", "POST", { dungeon_id: selectedDungeon, cleared: true });
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
            ],
          );
          setDungeonUiVisible(false);
        } else {
          pushGameLog(`副本失败: ${res.data.reason || "未通过门槛"}`);
          setDungeonUiVisible(false);
        }
      }
      await refreshGameState();
    } finally {
      setGameLoading(false);
    }
  };

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
            <TouchableOpacity style={styles.button} onPress={runMonsterFight}>
              <Text style={styles.buttonText}>{gameLoading ? "处理中..." : "开始战斗"}</Text>
            </TouchableOpacity>

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
                <Text style={styles.buttonText}>检查门槛</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, styles.duoBtn]}
                onPress={() => {
                  setDungeonRoomIndex(0);
                  setDungeonUiVisible(true);
                }}
              >
                <Text style={styles.buttonText}>进入副本界面</Text>
              </TouchableOpacity>
            </View>
            <View style={[styles.duoBtnRow, { marginTop: 8 }]}>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={settleDungeon}>
                <Text style={styles.buttonText}>副本结算</Text>
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
        visible={dungeonUiVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setDungeonUiVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, styles.dungeonUiCard]}>
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
                {NODE_TYPE_LABELS[selectedDungeonNodes[dungeonRoomIndex]] || "未知房间"}：
                {selectedDungeonNodes[dungeonRoomIndex] === "boss"
                  ? ` 面对 ${selectedDungeonEncounter.boss}`
                  : selectedDungeonNodes[dungeonRoomIndex] === "elite"
                    ? ` 面对 ${selectedDungeonEncounter.elite}`
                    : selectedDungeonNodes[dungeonRoomIndex] === "normal"
                      ? ` 面对 ${selectedDungeonEncounter.trash}`
                      : selectedDungeonNodes[dungeonRoomIndex] === "treasure"
                        ? " 可配置宝箱奖励"
                        : " 可配置恢复效果"}
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
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={settleDungeon}>
                <Text style={styles.buttonText}>挑战当前副本</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={() => setDungeonUiVisible(false)}>
                <Text style={styles.buttonText}>退出副本界面</Text>
              </TouchableOpacity>
            </View>
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
              {resultModalItems.length ? (
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
