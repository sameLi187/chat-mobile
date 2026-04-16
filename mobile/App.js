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

export default function App() {
  const [authMode, setAuthMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  const [connected, setConnected] = useState(false);
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

  const socketRef = useRef(null);

  const authHeaders = useMemo(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  const loadSocial = useCallback(async () => {
    if (!token) return;
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
    } catch {
      /* ignore */
    }
  }, [token, authHeaders]);

  const wsUrl = useMemo(() => {
    const encodedToken = encodeURIComponent(token);
    return `${WS_BASE}?token=${encodedToken}`;
  }, [token]);

  useEffect(() => {
    if (!connected || !token) {
      return undefined;
    }

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setMessages((prev) => [
        ...prev,
        {
          id: `local-${Date.now()}`,
          type: "system",
          scope: "lobby",
          sender: "系统",
          content: "已连接世界大厅",
        },
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
              content: `${payload.from_username} (ID:${payload.from_user_id}) 请求加你为好友，到「好友」里同意`,
            },
          ]);
          loadSocial();
          return;
        }
        if (payload.type === "friend_accepted") {
          setMessages((prev) => [
            ...prev,
            {
              id: `fa-${Date.now()}`,
              type: "system",
              scope: "lobby",
              sender: "系统",
              content: `${payload.username} (ID:${payload.user_id}) 已同意你的好友请求`,
            },
          ]);
          loadSocial();
          return;
        }

        setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, ...payload }]);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            type: "system",
            sender: "系统",
            content: "收到无法解析的消息",
          },
        ]);
      }
    };

    socket.onerror = () => {
      setMessages((prev) => [
        ...prev,
        {
          id: `ws-error-${Date.now()}`,
          type: "system",
          sender: "系统",
          content: "网络错误，请检查服务端状态",
        },
      ]);
    };

    socket.onclose = () => {
      setConnected(false);
      setMessages((prev) => [
        ...prev,
        {
          id: `close-${Date.now()}`,
          type: "system",
          sender: "系统",
          content: "连接已关闭",
        },
      ]);
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [connected, token, wsUrl, loadSocial]);

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
      setAuthError("请求失败，请检查后端服务状态");
    } finally {
      setAuthLoading(false);
    }
  };

  const logout = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }
    setToken("");
    setCurrentUser(null);
    setConnected(false);
    setUsername("");
    setPassword("");
    setMessages([]);
    setOnlineUsers([]);
    setFriends([]);
    setPendingFriends([]);
    setGroups([]);
    setActiveTab("lobby");
    setDmPeer(null);
    setSelectedGroup(null);
    setAuthError("");
  };

  const visibleMessages = useMemo(() => {
    const uid = currentUser?.user_id;
    return messages.filter((m) => {
      if (m.type === "online") return false;
      if (activeTab === "lobby") {
        if (m.type === "system") return m.scope === "lobby" || !m.scope;
        return m.scope === "lobby" || (!m.scope && m.type === "chat");
      }
      if (activeTab === "dm") {
        if (!dmPeer) return false;
        if (m.type === "system" && m.scope === "dm") return true;
        if (m.type !== "chat" || m.scope !== "dm") return false;
        return (
          (m.sender_id === uid && m.peer_id === dmPeer.user_id) ||
          (m.sender_id === dmPeer.user_id && m.peer_id === uid)
        );
      }
      if (activeTab === "groups") {
        if (!selectedGroup) return false;
        if (m.type === "system" && m.scope === "group" && m.group_id === selectedGroup.group_id)
          return true;
        if (m.type !== "chat" || m.scope !== "group") return false;
        return m.group_id === selectedGroup.group_id;
      }
      return false;
    });
  }, [messages, activeTab, dmPeer, selectedGroup, currentUser]);

  const sendMessage = () => {
    const text = inputText.trim();
    if (!text || !socketRef.current || socketRef.current.readyState !== 1) {
      return;
    }

    if (activeTab === "lobby") {
      socketRef.current.send(JSON.stringify({ action: "lobby", text }));
    } else if (activeTab === "dm") {
      if (!dmPeer) return;
      socketRef.current.send(
        JSON.stringify({ action: "dm", to_user_id: dmPeer.user_id, text }),
      );
    } else if (activeTab === "groups") {
      if (!selectedGroup) return;
      socketRef.current.send(
        JSON.stringify({ action: "group", group_id: selectedGroup.group_id, text }),
      );
    }
    setInputText("");
  };

  const sendFriendRequest = async () => {
    const u = friendUsernameInput.trim();
    if (!u) return;
    try {
      const res = await fetch(`${API_BASE}/friends/request`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ to_username: u }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            type: "system",
            scope: "lobby",
            sender: "系统",
            content: data.detail || "加好友失败",
          },
        ]);
        return;
      }
      setFriendUsernameInput("");
      loadSocial();
    } catch {
      /* ignore */
    }
  };

  const acceptFriend = async (fromUserId) => {
    try {
      const res = await fetch(`${API_BASE}/friends/accept`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ from_user_id: fromUserId }),
      });
      if (res.ok) loadSocial();
    } catch {
      /* ignore */
    }
  };

  const createGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    try {
      const res = await fetch(`${API_BASE}/groups`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (res.ok) {
        setNewGroupName("");
        setSelectedGroup({ group_id: data.group_id, name: data.name });
        loadSocial();
      }
    } catch {
      /* ignore */
    }
  };

  const inviteToGroup = async () => {
    const u = inviteUsername.trim();
    if (!u || !selectedGroup) return;
    try {
      const res = await fetch(`${API_BASE}/groups/${selectedGroup.group_id}/members`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ username: u }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            id: `ig-${Date.now()}`,
            type: "system",
            scope: "lobby",
            sender: "系统",
            content: data.detail || "邀请失败",
          },
        ]);
        return;
      }
      setInviteUsername("");
    } catch {
      /* ignore */
    }
  };

  if (!token) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="dark" />
        <View style={styles.loginCard}>
          <Text style={styles.title}>起源</Text>
          <Text style={styles.subtitle}>登录后进入世界大厅与好友私聊、群聊</Text>
          <TextInput
            style={styles.input}
            value={username}
            onChangeText={setUsername}
            placeholder="用户名（至少3位）"
            autoCapitalize="none"
          />
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            placeholder="密码（至少6位）"
            secureTextEntry
            autoCapitalize="none"
          />
          {authError ? <Text style={styles.errorText}>{authError}</Text> : null}
          <TouchableOpacity style={styles.button} onPress={submitAuth}>
            <Text style={styles.buttonText}>
              {authLoading ? "处理中..." : authMode === "login" ? "登录" : "注册"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.switchModeBtn}
            onPress={() => setAuthMode((prev) => (prev === "login" ? "register" : "login"))}
          >
            <Text style={styles.switchModeText}>
              {authMode === "login" ? "没有账号？去注册" : "已有账号？去登录"}
            </Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const tabBar = (
    <View style={styles.tabRow}>
      {[
        { key: "lobby", label: "世界大厅" },
        { key: "dm", label: "私聊" },
        { key: "groups", label: "群聊" },
        { key: "friends", label: "好友" },
      ].map((t) => (
        <TouchableOpacity
          key={t.key}
          style={[styles.tab, activeTab === t.key && styles.tabActive]}
          onPress={() => {
            setActiveTab(t.key);
            if (t.key === "friends") loadSocial();
            if (t.key === "groups") loadSocial();
          }}
        >
          <Text style={[styles.tabText, activeTab === t.key && styles.tabTextActive]}>{t.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        style={styles.chatWrap}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.header}>
          <Text style={styles.headerTitle} numberOfLines={2}>
            {currentUser?.username} (ID:{currentUser?.user_id})
          </Text>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.leaveText}>退出</Text>
          </TouchableOpacity>
        </View>
        {tabBar}
        {activeTab === "lobby" ? (
          <Text style={styles.onlineText}>
            在线：{onlineUsers.length} 人
            {onlineUsers.length > 0
              ? ` | ID: ${onlineUsers.map((u) => u.user_id).join(", ")}`
              : ""}
          </Text>
        ) : null}

        {activeTab === "friends" ? (
          <ScrollView style={styles.sideScroll} keyboardShouldPersistTaps="handled">
            <Text style={styles.sectionTitle}>待同意</Text>
            {pendingFriends.length === 0 ? (
              <Text style={styles.muted}>暂无</Text>
            ) : (
              pendingFriends.map((p) => (
                <View key={p.user_id} style={styles.rowItem}>
                  <Text>
                    {p.username} (ID:{p.user_id})
                  </Text>
                  <TouchableOpacity style={styles.smallBtn} onPress={() => acceptFriend(p.user_id)}>
                    <Text style={styles.smallBtnText}>同意</Text>
                  </TouchableOpacity>
                </View>
              ))
            )}
            <Text style={styles.sectionTitle}>我的好友</Text>
            {friends.length === 0 ? (
              <Text style={styles.muted}>暂无好友，下方添加</Text>
            ) : (
              friends.map((f) => (
                <TouchableOpacity
                  key={f.user_id}
                  style={styles.rowItem}
                  onPress={() => {
                    setDmPeer(f);
                    setActiveTab("dm");
                  }}
                >
                  <Text>
                    {f.username} (ID:{f.user_id}) — 点进私聊
                  </Text>
                </TouchableOpacity>
              ))
            )}
            <Text style={styles.sectionTitle}>添加好友（用户名）</Text>
            <TextInput
              style={styles.input}
              value={friendUsernameInput}
              onChangeText={setFriendUsernameInput}
              placeholder="对方用户名"
              autoCapitalize="none"
            />
            <TouchableOpacity style={styles.button} onPress={sendFriendRequest}>
              <Text style={styles.buttonText}>发送好友请求</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryBtn} onPress={loadSocial}>
              <Text style={styles.secondaryBtnText}>刷新列表</Text>
            </TouchableOpacity>
          </ScrollView>
        ) : activeTab === "groups" && !selectedGroup ? (
          <ScrollView style={styles.sideScroll} keyboardShouldPersistTaps="handled">
            <Text style={styles.sectionTitle}>我的群组</Text>
            {groups.length === 0 ? (
              <Text style={styles.muted}>暂无，下方创建</Text>
            ) : (
              groups.map((g) => (
                <TouchableOpacity
                  key={g.group_id}
                  style={[styles.rowItem, selectedGroup?.group_id === g.group_id && styles.rowSelected]}
                  onPress={() => setSelectedGroup(g)}
                >
                  <Text>
                    {g.name} (ID:{g.group_id})
                  </Text>
                </TouchableOpacity>
              ))
            )}
            <Text style={styles.sectionTitle}>新建群组</Text>
            <TextInput
              style={styles.input}
              value={newGroupName}
              onChangeText={setNewGroupName}
              placeholder="群名称"
            />
            <TouchableOpacity style={styles.button} onPress={createGroup}>
              <Text style={styles.buttonText}>创建</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryBtn} onPress={loadSocial}>
              <Text style={styles.secondaryBtnText}>刷新群组</Text>
            </TouchableOpacity>
          </ScrollView>
        ) : activeTab === "dm" && !dmPeer ? (
          <ScrollView style={styles.sideScroll}>
            <Text style={styles.sectionTitle}>选择好友私聊</Text>
            {friends.length === 0 ? (
              <Text style={styles.muted}>请先在「好友」里添加好友</Text>
            ) : (
              friends.map((f) => (
                <TouchableOpacity key={f.user_id} style={styles.rowItem} onPress={() => setDmPeer(f)}>
                  <Text>
                    {f.username} (ID:{f.user_id})
                  </Text>
                </TouchableOpacity>
              ))
            )}
          </ScrollView>
        ) : (
          <>
            {activeTab === "groups" && selectedGroup ? (
              <View style={styles.groupManage}>
                <View style={styles.subHeader}>
                  <Text style={styles.subHeaderText} numberOfLines={2}>
                    群：{selectedGroup.name} (ID:{selectedGroup.group_id})
                  </Text>
                  <TouchableOpacity onPress={() => setSelectedGroup(null)}>
                    <Text style={styles.linkText}>返回选群</Text>
                  </TouchableOpacity>
                </View>
                <Text style={styles.inviteLabel}>邀请入群（仅群主，填用户名）</Text>
                <View style={styles.inviteRow}>
                  <TextInput
                    style={[styles.input, styles.inviteInput]}
                    value={inviteUsername}
                    onChangeText={setInviteUsername}
                    placeholder="用户名"
                    autoCapitalize="none"
                  />
                  <TouchableOpacity style={[styles.button, styles.inviteBtn]} onPress={inviteToGroup}>
                    <Text style={styles.buttonText}>邀请</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : null}
            {activeTab === "dm" && dmPeer ? (
              <View style={styles.subHeader}>
                <Text style={styles.subHeaderText}>
                  私聊：{dmPeer.username} (ID:{dmPeer.user_id})
                </Text>
                <TouchableOpacity onPress={() => setDmPeer(null)}>
                  <Text style={styles.linkText}>换一个人</Text>
                </TouchableOpacity>
              </View>
            ) : null}
            <FlatList
              style={styles.list}
              data={visibleMessages}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <View style={item.type === "chat" ? styles.chatBubble : styles.systemBubble}>
                  <Text style={styles.sender}>
                    {item.sender}
                    {item.sender_id ? ` (ID:${item.sender_id})` : ""}
                  </Text>
                  <Text style={styles.messageText}>{item.content}</Text>
                </View>
              )}
            />
            <View style={styles.inputRow}>
              <TextInput
                style={[styles.input, styles.chatInput]}
                value={inputText}
                onChangeText={setInputText}
                placeholder={
                  activeTab === "lobby"
                    ? "世界大厅消息..."
                    : activeTab === "dm"
                      ? "私聊消息..."
                      : "群聊消息..."
                }
              />
              <TouchableOpacity style={[styles.button, styles.sendButton]} onPress={sendMessage}>
                <Text style={styles.buttonText}>发送</Text>
              </TouchableOpacity>
            </View>
          </>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f2f4f8",
    justifyContent: "center",
  },
  loginCard: {
    margin: 20,
    padding: 20,
    borderRadius: 14,
    backgroundColor: "#fff",
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  title: {
    fontSize: 28,
    fontWeight: "700",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: "#666",
    marginBottom: 12,
  },
  errorText: {
    marginBottom: 10,
    color: "#d63737",
    fontWeight: "600",
  },
  switchModeBtn: {
    marginTop: 10,
    alignItems: "center",
  },
  switchModeText: {
    color: "#246bff",
    fontWeight: "600",
  },
  input: {
    borderColor: "#d0d7e2",
    borderWidth: 1,
    borderRadius: 10,
    backgroundColor: "#fff",
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    marginBottom: 12,
  },
  button: {
    backgroundColor: "#246bff",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  buttonText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 16,
  },
  chatWrap: {
    flex: 1,
    padding: 12,
  },
  header: {
    paddingVertical: 8,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  onlineText: {
    color: "#2d3b66",
    marginBottom: 8,
    fontSize: 12,
    fontWeight: "600",
  },
  leaveText: {
    color: "#d63737",
    fontWeight: "600",
  },
  tabRow: {
    flexDirection: "row",
    marginBottom: 8,
    gap: 6,
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: "#e4e9f2",
    alignItems: "center",
  },
  tabActive: {
    backgroundColor: "#246bff",
  },
  tabText: {
    fontSize: 12,
    color: "#333",
    fontWeight: "600",
  },
  tabTextActive: {
    color: "#fff",
  },
  list: {
    flex: 1,
  },
  chatBubble: {
    backgroundColor: "#ffffff",
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  systemBubble: {
    backgroundColor: "#eaf0ff",
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  sender: {
    fontWeight: "700",
    marginBottom: 4,
  },
  messageText: {
    fontSize: 15,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingTop: 8,
  },
  chatInput: {
    flex: 1,
    marginBottom: 0,
  },
  sendButton: {
    paddingHorizontal: 16,
  },
  sideScroll: {
    flex: 1,
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    marginTop: 12,
    marginBottom: 8,
    color: "#1a2744",
  },
  muted: {
    color: "#888",
    marginBottom: 8,
  },
  rowItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 12,
    backgroundColor: "#fff",
    borderRadius: 10,
    marginBottom: 8,
  },
  rowSelected: {
    borderWidth: 2,
    borderColor: "#246bff",
  },
  smallBtn: {
    backgroundColor: "#246bff",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  smallBtnText: {
    color: "#fff",
    fontWeight: "600",
  },
  secondaryBtn: {
    marginTop: 8,
    alignItems: "center",
    padding: 8,
  },
  secondaryBtnText: {
    color: "#246bff",
    fontWeight: "600",
  },
  subHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  subHeaderText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#1a2744",
    flex: 1,
  },
  linkText: {
    color: "#246bff",
    fontWeight: "600",
  },
  groupManage: {
    marginBottom: 8,
  },
  inviteLabel: {
    fontSize: 12,
    color: "#555",
    marginBottom: 6,
  },
  inviteRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  inviteInput: {
    flex: 1,
    marginBottom: 0,
  },
  inviteBtn: {
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
});
