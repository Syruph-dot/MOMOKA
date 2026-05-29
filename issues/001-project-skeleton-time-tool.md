# Issue #1: 项目骨架 + 时间工具

## 类型
AFK

## 阻塞
无 — 可立即开始

## 目标

建立 MOMOKA 项目骨架，使用 OpenAI Agents SDK 创建最小可运行的 Agent，配备时间查询工具。

## 验收标准

- [ ] 创建目录结构: `tools/`, `agents/`, `static/`, `logs/`
- [ ] `tools/__init__.py` 工具注册中心
- [ ] `tools/time_tool.py` — `get_current_time()` 返回当前日期时间
- [ ] `agents/AGENTS.md` — 外置 system prompt，Agent 从文件加载
- [ ] `file_agent.py` — 主入口，创建 Agent + 注册工具 + CLI 交互
- [ ] 工具调用日志在终端输出
- [ ] `python file_agent.py "现在几点"` 可正常运行并返回时间

## 阻塞
无
