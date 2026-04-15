# Chat Mobile (公网多人聊天 App)

这个版本支持“**不在同一网络，只要能上网就能聊天**”。

- `backend`：Python + FastAPI + WebSocket（部署到公网）
- `mobile`：React Native (Expo)（连接 `wss://.../ws`）

## 1) 部署后端到公网

`backend` 目录已经提供 `Dockerfile`，可直接部署到 Render / Railway / Fly.io 等平台。

本地先验证后端可运行：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

然后把 `backend` 部署到云平台，拿到公网地址，例如：

- `https://your-chat-api.onrender.com`

你的 WebSocket 地址就是：

- `wss://your-chat-api.onrender.com/ws`

## 2) 启动手机端

在 `mobile` 目录运行：

```bash
npm install
npx expo start
```

手机用 Expo Go 扫码打开。

## 3) 在 App 里填写服务器地址

进入 App 后，在登录页把服务器地址填成公网 WebSocket 地址：

- `wss://your-chat-api.onrender.com/ws`

然后输入昵称，进入聊天室。

## 4) 验证跨网络聊天

- 手机 A 用移动网络（4G/5G）
- 手机 B 用另一网络（例如家里 Wi-Fi）
- 两台设备都连接同一个 `wss://.../ws`
- 任意一端发送消息，另一端实时收到

## 5) 常见问题

- 连接失败：确认填的是 `wss://`（不是 `ws://`）
- 连上后立即断开：看云平台日志，检查服务是否休眠或崩溃
- 消息收不到：确认两端连接的是同一个后端域名
