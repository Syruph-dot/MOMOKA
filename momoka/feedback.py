"""Feedback reflection helpers for MOMOKA's annotation loop."""

from __future__ import annotations


def analyze_judgment(
    score: int,
    label: str,
    annotated_text: str,
    topic: str = "",
    user_comment: str = "",
) -> dict:
    """Convert a Likert score into a structured reflection for the next guess."""
    evidence = annotated_text.strip()
    comment = user_comment.strip()
    evidence_label = evidence or "整段输出"
    comment_note = f" 用户文字批注：{comment}" if comment else ""
    topic_text = topic.strip() or "当前会话主题"
    comment_hypothesis = f"用户明确补充的判断标准是：{comment}" if comment else ""

    if score <= 2:
        return {
            "stance": "reject",
            "next_guess_strategy": "pivot",
            "summary": f"用户明确不认可被批注内容：{evidence_label}。{comment_note}",
            "intent_hypothesis": comment_hypothesis or f"用户可能认为当前回答偏离了「{topic_text}」的真实重点。",
            "next_guess_instruction": "不要沿用上一轮角度，换一个解释框架重新猜用户意图。",
        }
    if score == 3:
        return {
            "stance": "weak_reject",
            "next_guess_strategy": "adjust",
            "summary": f"用户认为被批注内容接近但不足：{evidence_label}。{comment_note}",
            "intent_hypothesis": comment_hypothesis or f"用户可能认可「{topic_text}」的大方向，但觉得表达或重点不够准。",
            "next_guess_instruction": "保留上一轮少量有效部分，收窄问题并重新组织重点。",
        }
    if score == 4:
        return {
            "stance": "ambivalent",
            "next_guess_strategy": "diverge",
            "summary": f"用户对被批注内容保持中立：{evidence_label}。{comment_note}",
            "intent_hypothesis": comment_hypothesis or f"用户可能有一个不冲突但尚未显式说出的「{topic_text}」并行想法。可能在回答的文本里面，但用户也可能并没有回答。",
            "next_guess_instruction": "如果用户没有发文字消息，或文字消息中并没有隐含相关内容，提出并行假设，探索另一条可能的用户意图，不要要求用户解释。",
        }
    if score == 5:
        return {
            "stance": "weak_endorse",
            "next_guess_strategy": "refine",
            "summary": f"用户轻度认可被批注内容：{evidence_label}。{comment_note}",
            "intent_hypothesis": comment_hypothesis or f"用户认为「{topic_text}」方向基本正确，但还需要更贴近他的判断标准。",
            "next_guess_instruction": "沿着当前方向继续，但要更具体、更可执行。",
        }
    return {
        "stance": "endorse",
        "next_guess_strategy": "deepen",
        "summary": f"用户高度认可被批注内容：{evidence_label}。{comment_note}",
        "intent_hypothesis": comment_hypothesis or f"用户希望继续深化「{topic_text}」里被认可的判断路径。",
        "next_guess_instruction": "深化被认可方向，把它发展成下一步更强的判断或行动建议。",
    }


def build_followup_prompt(
    topic: str,
    output_text: str,
    judgment: dict,
    reflection: dict,
) -> str:
    """Build the score-only continuation prompt after a user judgment."""
    comment = (judgment.get("comment") or "").strip()
    lead = "用户这次通过划选/回复块评分给出反馈。"
    if comment:
        lead += "用户还填写了文字批注，文字批注比单独评分携带更明确的意图信号。"
    else:
        lead += "用户没有填写文字批注，不要要求用户补充文字或解释评分原因。"

    return "\n".join([
        lead,
        "请根据批注信号继续主动揣摩用户意图并输出下一轮猜测。",
        "",
        f"会话主题: {topic or '未命名主题'}",
        "",
        "上一轮输出:",
        output_text.strip() or "(空)",
        "",
        "用户批注:",
        f"- 评分: {judgment.get('score')}/7 ({judgment.get('label', '')})",
        f"- 被评文本: {judgment.get('context', '') or '整条输出'}",
        f"- 文字批注: {comment or '无'}",
        "",
        "结构化反思:",
        f"- 立场: {reflection.get('stance', '')}",
        f"- 策略: {reflection.get('next_guess_strategy', '')}",
        f"- 意图假设: {reflection.get('intent_hypothesis', '')}",
        f"- 下一轮指令: {reflection.get('next_guess_instruction', '')}",
    ])
