# Issue #3: Sophdotnet 设计拷贝 + 页面骨架

## 类型
AFK

## 阻塞
无 — 纯前端，与 #1 #2 并行

## 目标

从 Sophdotnet 拷贝 CSS 设计系统，创建 MOMOKA 文件助手的 Web UI 页面骨架。

## 验收标准

- [ ] 从 `s:/20_项目/Sophdotnet/` 拷贝 CSS 到 `static/css/`:
  - `syrretro.css` — 核心 retro 主题
  - `ggmetro.css` — 水晶玻璃主题
  - `mobile-framework.css` + `mobile/` + `themes/` 目录
- [ ] 拷贝必要的图片资源到 `static/images/`
- [ ] `static/index.html` — 采用 retro-shell + retro-card 三栏布局:
  - 左侧: Agent 状态信息
  - 中间: 对话区
  - 右侧: 工具日志区 (占位)
  - 底部: 输入区 (toolbar 风格)
- [ ] `static/css/app.css` — Agent 专属样式
- [ ] 浏览器打开 `index.html` 可看到完整的 Sophdotnet retro 风格页面

## 阻塞
无
