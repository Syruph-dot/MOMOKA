# Issue #10: 结构化 Reflect 模块

## 类型
AFK

## 阻塞
- #8 批注数据链路 + 输出台账

## 目标

将评分解释从一句字符串升级为结构化反思结果，为后续偏好记忆晋升和自我进化提供可审计信号。

## 验收标准

- [x] 新增 `momoka.feedback.analyze_judgment`
- [x] 反思结果包含 `stance`
- [x] 反思结果包含 `next_guess_strategy`
- [x] 反思结果包含 `intent_hypothesis`
- [x] 反思结果包含 `next_guess_instruction`
- [x] score 1-2、4、6-7 走不同策略
- [x] `/api/judge` 响应返回 `reflection`
- [x] 日记忆写入评分、分析、策略和批注上下文

## 验证

- `python -m unittest discover -s tests -p test_feedback_loop.py -v`
- `python -m unittest discover -s tests -p test_server_feedback_api.py -v`

## 阻塞
- #8
