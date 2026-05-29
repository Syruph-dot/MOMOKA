# MOMOKA — Minimalist-Opinion-Model-Optimized Knowledge Agent

批注式判断交互协议 · 极简意见模型 · 文件助手 Agent
https://github.com/Syruph-dot/MOMOKA

MOMOKA 是一个基于 [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) 的智能文件助手，运行在 SophDotNet 平台上。它通过 **批注式判断交互协议**（Likert 7 点量表）实现人机之间的高效对齐——用户对 Agent 输出的一系列（逐句）评分，自动驱动 Agent 调整后续行为。

## 特性

- **会话级管理** — 每个会话绑定一个核心目标和一个工作文件夹，Agent 的文件操作被限制在该文件夹内
- **技能自动匹配** — 根据用户输入自动匹配并加载对应技能（summarizer、file_organizer 等），按需扩展
- **记忆系统** — 日记忆 + 长期记忆 + 偏好学习，Agent 在交互中持续进化
- **批注式判断** — 7 点 Likert 量表评分，每次评分触发闭环（反思 → 更新偏好 → 进化提案 → 可选续猜）
- **复古 UI** — 多主题（Aero、Metro 等），三栏布局（Agent 状态 · 对话区 · 工具调用日志）

## 快速启动

### 环境要求

- Python ≥ 3.10
- 一个兼容 OpenAI API 的 API Key（推荐阿里云 DashScope / 通义千问）

### 1. 克隆项目

```bash
git clone <repo-url>
cd MOMOKA
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单：`openai-agents`, `python-dotenv`, `uvicorn`, `starlette`

### 3. 配置环境变量

将 `.env.example` 复制为 `.env`，或直接设置环境变量：

```bash
# .env
MOMOKA_MODEL=qwen3.6-flash
```

> **API Key** 通过环境变量设置（优先顺序）：
> - `ALIYUN_API_KEY` — 阿里云 DashScope 密钥
> - `OPENAI_API_KEY` — 通用 OpenAI 兼容密钥
>
> 默认 Base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1`（阿里云 DashScope 兼容模式）。
> 可通过 `OPENAI_BASE_URL` 环境变量覆盖为任何 OpenAI 兼容服务。

```bash
# 示例：使用阿里云 DashScope
export ALIYUN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 示例：使用 OpenAI
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export OPENAI_BASE_URL=https://api.openai.com/v1
```

### 4. 启动 Web 服务器

```bash
python server.py
```

启动后访问 **http://localhost:8888**

终端会显示：
```
MOMOKA HTTP Server 启动中...
  [OK] Provider: DashScope
  [OK] Key: sk-xxxx...
  [OK] Skills: 2 loaded
  访问: http://localhost:8888
```

### 5. （可选）CLI 模式启动

```bash
python file_agent.py
```

以当前目录为工作文件夹，直接在终端中与 Agent 对话。输入 `/quit` 或 `/exit` 退出。

## 交互指南

### Web 界面：会话管理

访问 `http://localhost:8888` 进入**会话列表页**：

1. 点击 **「+ 新建会话」**
2. 填写 **核心目标**（如"整理项目文档结构"）
3. 指定 **工作文件夹**（可点击"浏览"用目录选择器选取）
4. 创建成功后，自动进入对话页面

### Web 界面：对话

在对话页中：

- **左侧面板**显示 Agent 身份和能力说明
- **中间区域**是对话区，底部输入框输入任务
- **右侧面板**实时显示工具调用日志和匹配的技能

示例对话：
```
> 列出当前目录的所有文件
> 读取 README.md 的内容
> 帮我写一个文件归档脚本
> 总结 src/ 目录下的所有 Python 文件
```

### 批注式判断交互（核心）

对话中，Agent 每次回复会带有一个 `output_id`。你可以对其回复进行评分：

| 分数 | 标签 | 含义 |
|------|------|------|
| 1 | 强烈反对 | 方向完全偏离 |
| 2 | 反对 | 方向偏离 |
| 3 | 不太赞同 | 接近但不足 |
| 4 | 中立 | 有其他不冲突但不同的想法 |
| 5 | 有点赞同 | 方向正确，有改进空间 |
| 6 | 赞同 | 方向正确，可深化 |
| 7 | 强烈赞同 | 超出预期，完美匹配 |

每次评分触发四个阶段：

1. **Reflect** — 分析评分含义，生成反思摘要
2. **Update Preferences** — 更新 Agent 的偏好模型
3. **Evolve** — 生成技能进化提案（如新增关键词、调整权重）
4. **Continue**（可选）— 基于反思生成续猜输出，形成完整闭环

> 评分 API：`POST /api/judge`，请求体包含 `output_id`、`score`（1-7）、`context`（被评原文）、`comment`（可选文字批注）、`continue`（是否续猜）。

### 文件工具

Agent 支持以下文件操作（受限于会话绑定的工作文件夹）：

- **读取文件** — `read_file(path)`
- **写入文件** — `write_file(path, content)`
- **列出目录** — `list_files(path)`
- **追加内容** — `append_file(path, content)`
- **查询时间** — `get_current_time()`

所有操作被限制在会话绑定的工作文件夹内，无法路径遍历。

## 项目结构

```
MOMOKA/
├── server.py              # HTTP API 服务器（Starlette + Uvicorn）
├── file_agent.py          # Agent 核心：system prompt 构建、Agent 工厂、CLI 模式
├── momoka/
│   ├── config.py          # 全局配置：路径常量、Likert 量表、环境变量加载
│   ├── memory.py          # 记忆系统：日记忆、长期记忆、偏好存储、反馈记录
│   ├── feedback.py        # 评分分析：判断含义推断、续猜 prompt 构建
│   ├── evolution.py       # 进化系统：根据评分生成技能进化提案
│   ├── skill_loader.py    # 技能加载器：匹配、评分、prompt 格式化
│   ├── session_manager.py # 会话管理：CRUD、消息持久化
│   └── replay.py          # 回放系统：重放历史评分与输出
├── tools/
│   ├── time_tool.py       # 时间工具
│   ├── file_reader.py     # 文件读取工具
│   ├── file_writer.py     # 文件写入工具
│   ├── file_lister.py     # 目录列表工具
│   └── file_appender.py   # 文件追加工具
├── skills/
│   ├── index.json         # 技能注册表
│   ├── summarizer/        # 摘要技能
│   └── file_organizer/    # 整理技能
├── prompts/
│   └── AGENTS.md          # Agent system prompt（身份、行为规则、安全边界）
├── static/
│   ├── index.html         # 会话管理页面
│   ├── chat.html          # 对话页面
│   ├── css/               # 多主题样式（aero、metro、mobile-framework）
│   └── js/                # 前端脚本（app.js、session.js、chat.js）
├── memory/                # 记忆存储目录（自动生成）
├── docs/                  # 文档
└── tests/                 # 测试
```

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/config` | GET | 查看配置状态 |
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions` | POST | 创建新会话 |
| `/api/sessions/{id}` | GET | 获取会话详情 |
| `/api/sessions/{id}` | DELETE | 删除会话 |
| `/api/sessions/{id}/messages` | GET | 获取会话消息历史 |
| `/api/chat` | POST | 发送聊天消息 |
| `/api/judge` | POST | 提交批注评分 |
| `/api/skills` | GET | 列出已加载技能 |
| `/api/memory` | GET | 查看最近记忆 |
| `/api/directories` | GET | 浏览文件系统目录 |

## 扩展：添加新技能

1. 在 `skills/` 下创建子目录，放入 `SKILL.md`（技能 prompt）
2. 在 `skills/index.json` 中注册：

```json
{
  "name": "my_skill",
  "description": "技能描述",
  "trigger_keywords": ["关键词1", "关键词2"],
  "utility_score": 0.8,
  "version": "1.0.0",
  "path": "my_skill/SKILL.md"
}
```

当用户输入包含触发关键词时，Skill Loader 自动匹配并注入该技能的 prompt 到 Agent 上下文中。

## 注意

- 默认使用 **阿里云 DashScope 兼容模式**，一个阿里云 API Key 即可使用通义千问系列模型
- 也支持任意 OpenAI 兼容 API（通过 `OPENAI_BASE_URL` 切换）
- 模型名称通过 `MOMOKA_MODEL` 环境变量指定
- 首次使用时，确保 memory 目录（`memory/`）已创建

## 协议

MOMOKA &copy; 2026 SophDotNet · 批注式判断交互协议 · Likert 7-Point Scale
