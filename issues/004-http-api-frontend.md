# Issue #4: HTTP API + 前后端联通

## 类型
AFK

## 阻塞
- #1 项目骨架
- #2 文件工具
- #3 页面骨架

## 目标

为 Agent 添加 HTTP API 服务，实现前端与后端的完整联通。浏览器中可发送消息给 Agent 并获取回复。

## 验收标准

- [ ] `server.py` — HTTP 服务器（或集成到 `file_agent.py`）:
  - `POST /api/chat` — 接收 `{message}`, 返回 `{response, tool_calls}`
  - 静态文件服务 `GET /static/*`
- [ ] `static/js/app.js` — 前端交互:
  - 发送消息到 `/api/chat`
  - 渲染 Agent 回复到对话区
  - 错误处理
- [ ] 浏览器中可完成一次完整对话
- [ ] `python server.py` 启动后访问 `http://localhost:8888` 可用

## 阻塞
- #1, #2, #3
