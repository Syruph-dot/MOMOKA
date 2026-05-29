# Issue #6: Skill 系统

## 类型
AFK

## 阻塞
- #1 项目骨架

## 目标

实现 MOMOKA PRD 中定义的 Skill 系统：用 Markdown 文件描述任务处理流程，Agent 按需加载。

## 验收标准

- [ ] `skills/` 目录结构
- [ ] `skills/summarizer/SKILL.md` — 文件总结 skill (采用 PRD 定义的模板)
- [ ] `skills/index.json` — 技能索引
- [ ] Agent 接到总结任务时，自动从 `skills/` 加载对应 SKILL.md
- [ ] 工具日志中展示 Skill 加载过程

## 阻塞
- #1
