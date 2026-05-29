# Issue #5: 工具调用日志实时展示

## 类型
AFK

## 阻塞
- #4 HTTP API + 前后端联通

## 目标

后端返回结构化的工具调用日志，前端在右侧 retro-aside 栏实时展示每次 tool call 的工具名、参数和返回值。

## 验收标准

- [ ] 后端 `/api/chat` 响应中包含 `tool_calls` 数组:
  ```json
  [{ "tool": "read_file", "args": {"path": "test.txt"}, "result": "文件内容..." }]
  ```
- [ ] 前端 retro-aside 栏展示工具调用卡片:
  - 工具名 + 图标
  - 调用参数
  - 返回结果（可折叠）
  - 时间戳
- [ ] 每次对话的工具调用链完整可见

## 阻塞
- #4
