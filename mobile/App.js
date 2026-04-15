import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
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
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState([]);
  const [onlineUsers, setOnlineUsers] = useState([]);
  const socketRef = useRef(null);

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
          sender: "系统",
          content: "连接成功",
        },
      ]);
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "online") {
          setOnlineUsers(payload.users || []);
          return;
        }

        setMessages((prev) => [...prev, { id: `${Date.now()}-${Math.random()}`, ...payload }]);
      } catch (error) {
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
  }, [connected, token, wsUrl]);

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
    } catch (error) {
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
    setAuthError("");
  };

  const sendMessage = () => {
    const text = inputText.trim();
    if (!text || !socketRef.current || socketRef.current.readyState !== 1) {
      return;
    }
    socketRef.current.send(text);
    setInputText("");
  };

  if (!token) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="dark" />
        <View style={styles.loginCard}>
          <Text style={styles.title}>起源聊天室</Text>
          <Text style={styles.subtitle}>账号密码登录后进入多人聊天</Text>
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
          <Text style={styles.tip}>用户信息将保存到服务器（SQLite）</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        style={styles.chatWrap}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.header}>
          <Text style={styles.headerTitle}>
            当前用户：{currentUser?.username} (ID:{currentUser?.user_id})
          </Text>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.leaveText}>退出登录</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.onlineText}>
          在线人数：{onlineUsers.length} | 在线用户ID：
          {onlineUsers.length > 0 ? onlineUsers.map((u) => u.user_id).join(", ") : "无"}
        </Text>

        <FlatList
          style={styles.list}
          data={messages}
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
            placeholder="输入消息..."
          />
          <TouchableOpacity style={[styles.button, styles.sendButton]} onPress={sendMessage}>
            <Text style={styles.buttonText}>发送</Text>
          </TouchableOpacity>
        </View>
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
  tip: {
    marginTop: 12,
    color: "#555",
  },
  chatWrap: {
    flex: 1,
    padding: 12,
  },
  header: {
    paddingVertical: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: "600",
  },
  onlineText: {
    color: "#2d3b66",
    marginBottom: 8,
    fontSize: 13,
    fontWeight: "600",
  },
  leaveText: {
    color: "#d63737",
    fontWeight: "600",
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
});
