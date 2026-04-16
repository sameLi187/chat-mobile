import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
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
  { map_id: "M01", label: "迷雾森林(1-12)" },
  { map_id: "M02", label: "断碑荒原(13-22)" },
  { map_id: "M03", label: "黑岩峡谷(23-32)" },
  { map_id: "M04", label: "霜骨墓地(33-42)" },
  { map_id: "M05", label: "深渊边境(43-50)" },
];

const MONSTER_TYPES = ["普通怪", "精英怪", "地图Boss"];
const DUNGEONS = ["DUN30", "DUN40", "DUN50"];

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
  const [selectedMap, setSelectedMap] = useState("M01");
  const [selectedMonsterType, setSelectedMonsterType] = useState("普通怪");
  const [selectedDungeon, setSelectedDungeon] = useState("DUN30");
  const [selectedPool, setSelectedPool] = useState("normal");

  const socketRef = useRef(null);
  const wsUrl = useMemo(() => `${WS_BASE}?token=${encodeURIComponent(token)}`, [token]);
  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  const pushGameLog = (text) => {
    setGameActionLog((prev) => [`${new Date().toLocaleTimeString()} ${text}`, ...prev].slice(0, 30));
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
        pushGameLog(
          `${selectedMap}-${selectedMonsterType}: ${res.data.won ? "胜利" : "失败"}，经验+${res.data.rewards.exp} 金币+${res.data.rewards.gold}`,
        );
        if (res.data.rewards.item?.name) pushGameLog(`掉落装备: ${res.data.rewards.item.name}`);
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
    if (res.ok) pushGameLog(res.data.ok ? `${selectedDungeon} 门槛已达标` : `${selectedDungeon} 未达标: ${res.data.reason}`);
    else pushGameLog(`副本检查失败: ${res.data.detail || "请求错误"}`);
    await refreshGameState();
  };

  const settleDungeon = async () => {
    setGameLoading(true);
    try {
      const res = await callGameApi("/game/dungeon/settle", "POST", { dungeon_id: selectedDungeon, cleared: true });
      if (res.ok) {
        if (res.data.ok) {
          pushGameLog(`${selectedDungeon} 结算完成: 经验+${res.data.rewards.exp} 金币+${res.data.rewards.gold}`);
          if ((res.data.rewards.items || []).length > 0) {
            pushGameLog(`副本掉落: ${(res.data.rewards.items || []).map((i) => i.name).join(" / ")}`);
          }
        } else {
          pushGameLog(`副本失败: ${res.data.reason || "未通过门槛"}`);
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
        const rewardText = (res.data.rewards || [])
          .map((r) => (r.type === "item" ? `装备:${r.item.name}` : `${r.type}:${r.amount}`))
          .join(" | ");
        pushGameLog(`抽奖(${selectedPool}) => ${rewardText || "无奖励"}`);
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
    } else {
      pushGameLog(`穿戴失败: ${res.data.detail || "请求错误"}`);
    }
    await refreshGameState();
  };

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
            <Text style={styles.infoText}>金币: {gameProfile?.wallet?.gold ?? 0}</Text>
            <Text style={styles.infoText}>普通券: {gameProfile?.wallet?.normal_ticket ?? 0}</Text>
            <Text style={styles.infoText}>高级券: {gameProfile?.wallet?.advanced_ticket ?? 0}</Text>
            <Text style={styles.infoText}>强化石: {gameProfile?.wallet?.enhance_stone ?? 0}</Text>
            <Text style={styles.infoText}>重铸石: {gameProfile?.wallet?.reroll_stone ?? 0}</Text>
            <Text style={styles.infoText}>史诗碎片: {gameProfile?.wallet?.epic_shard ?? 0}</Text>

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
                <TouchableOpacity key={mt} style={[styles.choiceBtn, selectedMonsterType === mt && styles.choiceBtnActive]} onPress={() => setSelectedMonsterType(mt)}>
                  <Text style={[styles.choiceText, selectedMonsterType === mt && styles.choiceTextActive]}>{mt}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={styles.button} onPress={runMonsterFight}>
              <Text style={styles.buttonText}>{gameLoading ? "处理中..." : "开始战斗"}</Text>
            </TouchableOpacity>

            <Text style={styles.sectionTitle}>副本</Text>
            <View style={styles.choiceRow}>
              {DUNGEONS.map((d) => (
                <TouchableOpacity key={d} style={[styles.choiceBtn, selectedDungeon === d && styles.choiceBtnActive]} onPress={() => setSelectedDungeon(d)}>
                  <Text style={[styles.choiceText, selectedDungeon === d && styles.choiceTextActive]}>{d}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.duoBtnRow}>
              <TouchableOpacity style={[styles.button, styles.duoBtn]} onPress={challengeDungeon}>
                <Text style={styles.buttonText}>检查门槛</Text>
              </TouchableOpacity>
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
            {(gameInventory || []).slice(0, 40).map((it) => (
              <TouchableOpacity key={it.inventory_id} style={[styles.rowItem, it.equipped ? styles.rowSelected : null]} onPress={() => equipItem(it.inventory_id)}>
                <View style={{ flex: 1 }}>
                  <Text>{it.name}</Text>
                  <Text style={styles.mutedSmall}>
                    {it.quality} | {it.slot} | 战力+{it.power} {it.set_key ? `| 套装:${it.set_key}` : ""}
                  </Text>
                </View>
                <Text style={styles.linkText}>{it.equipped ? "已穿戴" : "穿戴"}</Text>
              </TouchableOpacity>
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
  smallBtn: { backgroundColor: "#246bff", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  smallBtnText: { color: "#fff", fontWeight: "600" },
  secondaryBtn: { marginTop: 8, alignItems: "center", padding: 8 },
  secondaryBtnText: { color: "#246bff", fontWeight: "600" },
  groupManage: { marginBottom: 8 },
  inviteRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  inviteInput: { flex: 1, marginBottom: 0 },
  inviteBtn: { paddingHorizontal: 14, paddingVertical: 10 },
  infoText: { fontSize: 13, marginBottom: 4, color: "#203050" },
  choiceRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  choiceBtn: { backgroundColor: "#e4e9f2", borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10 },
  choiceBtnActive: { backgroundColor: "#246bff" },
  choiceText: { color: "#233", fontWeight: "600", fontSize: 12 },
  choiceTextActive: { color: "#fff" },
  duoBtnRow: { flexDirection: "row", gap: 8 },
  duoBtn: { flex: 1 },
  linkText: { color: "#246bff", fontWeight: "600" },
  logText: { fontSize: 12, color: "#2d3b66", marginBottom: 4, backgroundColor: "#f0f4ff", padding: 6, borderRadius: 6 },
});
