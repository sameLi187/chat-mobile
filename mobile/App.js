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

const FIXED_WS_BASE = "wss://chat-mobile-backend-production.up.railway.app/ws";

export default function App() {
  const [username, setUsername] = useState("");
  const [enteredName, setEnteredName] = useState("");
  const [connected, setConnected] = useState(false);
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState([]);
  const socketRef = useRef(null);

  const wsUrl = useMemo(() => {
    const encodedName = encodeURIComponent(enteredName || "匿名用户");
    return `${FIXED_WS_BASE}?username=${encodedName}`;
  }, [enteredName]);

  useEffect(() => {
    if (!connected) {
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
          content: "网络错误，请检查服务端或局域网连接",
        },
      ]);
    };

    socket.onclose = () => {
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
  }, [connected, wsUrl]);

  const joinChat = () => {
    const cleanName = username.trim();
    if (!cleanName) {
      return;
    }
    setEnteredName(cleanName);
    setConnected(true);
  };

  const sendMessage = () => {
    const text = inputText.trim();
    if (!text || !socketRef.current || socketRef.current.readyState !== 1) {
      return;
    }
    socketRef.current.send(text);
    setInputText("");
  };

  const leaveChat = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }
    setConnected(false);
    setMessages([]);
  };

  if (!connected) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar style="dark" />
        <View style={styles.loginCard}>
          <Text style={styles.title}>多人聊天</Text>
          <Text style={styles.subtitle}>输入昵称后加入群聊</Text>
          <TextInput
            style={styles.input}
            value={username}
            onChangeText={setUsername}
            placeholder="你的昵称"
            autoCapitalize="none"
          />
          <TouchableOpacity style={styles.button} onPress={joinChat}>
            <Text style={styles.buttonText}>进入聊天室</Text>
          </TouchableOpacity>
          <Text style={styles.tip}>已固定连接到公网聊天服务器</Text>
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
          <Text style={styles.headerTitle}>当前用户：{enteredName}</Text>
          <TouchableOpacity onPress={leaveChat}>
            <Text style={styles.leaveText}>退出</Text>
          </TouchableOpacity>
        </View>

        <FlatList
          style={styles.list}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={item.type === "chat" ? styles.chatBubble : styles.systemBubble}>
              <Text style={styles.sender}>{item.sender}</Text>
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
