"""Runtime annotation-ledger controller for MOMOKA."""

from __future__ import annotations

from collections import defaultdict


class AnnotationRuntimeController:
    """Build runtime control context from the annotation ledger."""

    def __init__(self, memory_store):
        self.memory_store = memory_store

    def build_runtime_bundle(self, user_message: str, topic: str = "", limit: int = 12) -> dict:
        records = self.memory_store.list_annotation_records()
        relevant = self._select_relevant_records(records, user_message=user_message, topic=topic, limit=limit)
        promoted = self.memory_store.get_promoted_preferences()
        return {
            "topic": topic,
            "ledger_size": len(records),
            "relevant_annotations": relevant,
            "promoted_preferences": [p for p in promoted if not topic or p.get("topic", "") == topic][:8],
            "rules": self._synthesize_rules(relevant),
        }

    def _select_relevant_records(self, records: list[dict], user_message: str, topic: str, limit: int) -> list[dict]:
        msg = (user_message or "").lower()
        filtered: list[tuple[int, int, dict]] = []
        for idx, record in enumerate(records):
            score = 0
            record_topic = (record.get("topic", "") or "").lower()
            if topic and record.get("topic", "") == topic:
                score += 4
            if record_topic and record_topic in msg:
                score += 2
            comment = (record.get("comment", "") or "").lower()
            context = (record.get("context", "") or "").lower()
            if msg and any(token and token in comment for token in msg.split()):
                score += 1
            if msg and any(token and token in context for token in msg.split()):
                score += 1
            if score > 0 or (topic and record.get("topic", "") == topic):
                filtered.append((score, idx, record))

        if filtered:
            filtered.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return [record for _, _, record in filtered[:limit]]
        return records[-limit:]

    def _synthesize_rules(self, records: list[dict]) -> list[str]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for record in records:
            score = int(record.get("score", 0))
            label = "prefer" if score >= 6 else "avoid" if score <= 2 else "adjust"
            comment = (record.get("comment") or "").strip()
            context = (record.get("context") or "").strip()
            if comment:
                grouped[label].append(f"{context} => {comment}" if context else comment)
            elif context:
                grouped[label].append(context)

        lines: list[str] = []
        for label in ("prefer", "avoid", "adjust"):
            values = grouped.get(label, [])
            if not values:
                continue
            seen: list[str] = []
            for value in values:
                if value not in seen:
                    seen.append(value)
            lines.extend([f"[{label}] {value}" for value in seen[:6]])
        return lines

    def render_runtime_context(self, bundle: dict) -> str:
        lines = ["## 批注账本规则"]
        lines.append(f"- ledger_size: {bundle.get('ledger_size', 0)}")

        promoted = bundle.get("promoted_preferences", [])
        if promoted:
            lines.append("- promoted_preferences:")
            for pref in promoted[:6]:
                lines.append(
                    f"  - [{pref.get('polarity', '')}] {pref.get('signal', '')} (topic: {pref.get('topic', '')})"
                )

        rules = bundle.get("rules", [])
        if rules:
            lines.append("- synthesized_rules:")
            for rule in rules:
                lines.append(f"  - {rule}")

        annotations = bundle.get("relevant_annotations", [])
        if annotations:
            lines.append("- relevant_annotations:")
            for ann in annotations[:8]:
                score = ann.get("score", "")
                context = (ann.get("context", "") or "").strip()
                comment = (ann.get("comment", "") or "").strip()
                if comment:
                    lines.append(f"  - score:{score} | {context} | comment:{comment}")
                else:
                    lines.append(f"  - score:{score} | {context}")

        return "\n".join(lines)

    def build_runtime_input(
        self,
        runtime_context: str,
        user_message: str,
        request_heading: str = "当前用户请求",
    ) -> str:
        return f"{runtime_context}\n\n## {request_heading}\n{user_message}" if runtime_context else user_message

    def build_runtime_envelope(
        self,
        user_message: str,
        topic: str = "",
        request_heading: str = "当前用户请求",
        limit: int = 12,
    ) -> dict:
        bundle = self.build_runtime_bundle(user_message=user_message, topic=topic, limit=limit)
        runtime_context = self.render_runtime_context(bundle)
        runtime_input = self.build_runtime_input(
            runtime_context=runtime_context,
            user_message=user_message,
            request_heading=request_heading,
        )
        return {
            "bundle": bundle,
            "runtime_context": runtime_context,
            "runtime_input": runtime_input,
        }

    def assess_output(self, bundle: dict, output_text: str) -> dict:
        text = (output_text or "").strip()
        reasons: list[str] = []
        revision_rules: list[str] = []

        for ann in bundle.get("relevant_annotations", []):
            score = int(ann.get("score", 0))
            context = (ann.get("context", "") or "").strip()
            comment = (ann.get("comment", "") or "").strip()
            if score <= 2 and context and context in text:
                reasons.append(f"命中低分批注禁区: {context}")
                if comment:
                    revision_rules.append(f"避免 `{context}`，改成：{comment}")
                else:
                    revision_rules.append(f"避免重用 `{context}`")

        if not reasons:
            return {
                "action": "accept",
                "reasons": [],
                "revision_prompt": "",
            }

        instruction_lines = [
            "## 输出修订指令",
            "当前输出命中了批注账本中的低分禁区，请直接重写这一轮输出。",
            "要求：",
        ]
        for rule in revision_rules:
            instruction_lines.append(f"- {rule}")
        instruction_lines.extend([
            "",
            "## 待修订输出",
            text or "(空输出)",
        ])

        return {
            "action": "revise",
            "reasons": reasons,
            "revision_prompt": "\n".join(instruction_lines),
        }

    def build_revision_input(
        self,
        *,
        runtime_context: str,
        request_heading: str,
        request_text: str,
        assessment: dict,
    ) -> str:
        revision_parts: list[str] = []
        if runtime_context:
            revision_parts.append(runtime_context)
        revision_parts.append(f"## {request_heading}\n{request_text}")
        revision_prompt = assessment.get("revision_prompt", "")
        if revision_prompt:
            revision_parts.append(revision_prompt)
        return "\n\n".join(revision_parts)
