# Issue #9: 主题会话 + 零文本续猜循环

## 类型
AFK

## 阻塞
- #8 批注数据链路 + 输出台账

## 目标

用户先指定会话主题后，可以不再输入文字，只通过划选和 1-7 分评分让 MOMOKA 自动生成下一轮猜测。

## 验收标准

- [x] 前端保存第一条用户消息作为当前主题
- [x] `/api/chat` 接收并保存 `topic`
- [x] `/api/judge` 支持 `continue: true`
- [x] 评分后后端构造“不要求用户补充文字”的续猜 prompt
- [x] 评分后返回 `next_response` 和 `next_output_id`
- [x] 前端收到 `next_response` 后自动追加下一条 MOMOKA 回复

## 验证

- `python -m unittest discover -s tests -p test_feedback_loop.py -v`
- `python -m unittest discover -s tests -p test_server_feedback_api.py -v`

## 阻塞
- #8
