# Issue #8: 批注数据链路 + 输出台账

## 类型
AFK

## 阻塞
- #4 HTTP API + 前后端联通

## 目标

让每条 Agent 输出都有稳定 `output_id`，并在后端保存完整输出台账。用户评分时即使没有划选文本，也能回退到整条 Agent 输出作为批注上下文。

## 验收标准

- [x] `/api/chat` 在客户端未提供 `output_id` 时自动生成稳定 id
- [x] 每条 Agent 输出写入 `memory/.outputs/outputs.json`
- [x] 输出台账包含主题、prompt、完整 response、匹配技能、工具调用
- [x] `/api/judge` 可以用 `output_id` 找回完整输出
- [x] 无划选文本时，评分上下文回退到整条输出
- [x] 动态评分栏包含 `data-output-id`，前端评分按钮能找到对应批注栏

## 验证

- `python -m unittest discover -s tests -p test_feedback_loop.py -v`
- `python -m unittest discover -s tests -p test_server_feedback_api.py -v`

## 阻塞
- #4
