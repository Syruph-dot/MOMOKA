"""
MOMOKA 记忆系统 — 日记忆 + 长期记忆的外部化 Markdown 存储。
参考: OpenClaw (memory/YYYY-MM-DD.md + MEMORY.md)
"""

import json
import re
from pathlib import Path
from datetime import datetime


class MemoryStore:
    """文件系统记忆存储。"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        dreams_dir = self.memory_dir / ".dreams" / "long-term"
        dreams_dir.mkdir(parents=True, exist_ok=True)

        output_dir = self.memory_dir / ".outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        evolog_dir = self.memory_dir / ".evolog"
        evolog_dir.mkdir(parents=True, exist_ok=True)

    # -- 日记忆 ---
    def daily_path(self, date: datetime | None = None) -> Path:
        dt = date or datetime.now()
        return self.memory_dir / f"{dt.strftime('%Y-%m-%d')}.md"

    def write_daily(self, content: str, date: datetime | None = None):
        """追加写入日记忆。"""
        path = self.daily_path(date)
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"\n## {ts}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        return path

    def read_daily(self, days_back: int = 2) -> str:
        """加载近 N 天的日记忆。"""
        lines = []
        for i in range(days_back):
            import datetime as _dt
            dt = datetime.now() - _dt.timedelta(days=i)
            path = self.daily_path(dt)
            if path.exists():
                lines.append(f"\n### 记忆: {dt.strftime('%Y-%m-%d')}")
                lines.append(path.read_text(encoding="utf-8")[:2000])
        return "\n".join(lines)

    # -- 长期记忆 ---
    def long_term_path(self) -> Path:
        return self.memory_dir / "MEMORY.md"

    def write_long_term(self, content: str):
        """写入长期记忆。"""
        path = self.long_term_path()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {ts}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    def read_long_term(self) -> str:
        path = self.long_term_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # -- 输出台账 ---
    def outputs_path(self) -> Path:
        return self.memory_dir / ".outputs" / "outputs.json"

    def _read_json_list(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _read_json_obj(self, path: Path, default: dict | None = None) -> dict:
        if default is None:
            default = {}
        if not path.exists():
            return dict(default)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default)
        return data if isinstance(data, dict) else dict(default)

    def _write_json_list(self, path: Path, records: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_json_obj(self, path: Path, payload: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_output(
        self,
        output_id: str,
        prompt: str,
        response: str,
        topic: str = "",
        matched_skills: list[str] | None = None,
        tool_calls: list[dict] | None = None,
    ) -> dict:
        """Record a full Agent output so later judgments can cite it."""
        record = {
            "output_id": output_id,
            "topic": topic,
            "prompt": prompt,
            "response": response,
            "matched_skills": matched_skills or [],
            "tool_calls": tool_calls or [],
            "timestamp": datetime.now().isoformat(),
        }
        path = self.outputs_path()
        records = [r for r in self._read_json_list(path) if r.get("output_id") != output_id]
        records.append(record)
        self._write_json_list(path, records[-200:])
        return record

    def get_output(self, output_id: str) -> dict | None:
        """Look up a recorded Agent output by id."""
        for record in reversed(self._read_json_list(self.outputs_path())):
            if record.get("output_id") == output_id:
                return record
        return None

    # -- 判断记录 ---
    def record_judgment(self, output_id: str, score: int, context: str = ""):
        """记录用户的一次批注判断。"""
        output = self.get_output(output_id) or {}
        selected = context.strip()
        full_output = str(output.get("response", "")).strip()
        resolved_context = selected or full_output
        record = {
            "output_id": output_id,
            "score": score,
            "context": resolved_context[:2000],
            "context_source": "selected_text" if selected else "full_output",
            "topic": output.get("topic", ""),
            "matched_skills": output.get("matched_skills", []),
            "timestamp": datetime.now().isoformat(),
        }
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        records = self._read_json_list(path)
        records.append(record)
        # 只保留最近 100 条
        records = records[-100:]
        self._write_json_list(path, records)
        return record

    # -- 获取最近评分记录 ---
    def get_recent_judgments(self, count: int = 3) -> list[dict]:
        """读取最近 N 条评分记录。"""
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        if not path.exists():
            return []
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return records[-count:]

    # -- 偏好晋升 ---
    def preferences_path(self) -> Path:
        return self.memory_dir / ".preferences.json"

    def _normalize_signal(self, text: str) -> str:
        compact = re.sub(r"\s+", "", text.strip().lower())
        return compact[:120]

    def update_preferences(self, judgment: dict, reflection: dict) -> dict:
        """基于重复评分晋升稳定偏好，返回本次更新结果。"""
        score = int(judgment.get("score", 0))
        if score not in (1, 2, 6, 7):
            return {"updated": False, "promoted": []}

        polarity = "prefer" if score >= 6 else "avoid"
        signal = (reflection.get("intent_hypothesis") or judgment.get("context") or "").strip()
        if not signal:
            return {"updated": False, "promoted": []}

        topic = judgment.get("topic", "")
        key = f"{polarity}:{topic}:{self._normalize_signal(signal)}"
        pref_path = self.preferences_path()
        payload = self._read_json_obj(pref_path, {"candidates": [], "promoted": []})

        promoted = next((p for p in payload["promoted"] if p.get("key") == key), None)
        if promoted:
            return {"updated": False, "promoted": []}

        candidate = next((c for c in payload["candidates"] if c.get("key") == key), None)
        if candidate is None:
            candidate = {
                "id": f"pref_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "key": key,
                "polarity": polarity,
                "signal": signal[:200],
                "topic": topic,
                "count": 0,
                "confidence": 0.0,
                "evidence": [],
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            }
            payload["candidates"].append(candidate)

        evidence = {
            "output_id": judgment.get("output_id", ""),
            "score": score,
            "context": judgment.get("context", "")[:200],
            "timestamp": datetime.now().isoformat(),
        }
        if any(ev.get("output_id") == evidence["output_id"] for ev in candidate.get("evidence", [])):
            self._write_json_obj(pref_path, payload)
            return {"updated": False, "promoted": []}

        candidate["evidence"].append(evidence)
        candidate["evidence"] = candidate["evidence"][-8:]
        candidate["count"] += 1
        candidate["last_seen"] = datetime.now().isoformat()
        candidate["confidence"] = min(0.95, 0.25 + 0.2 * candidate["count"])

        promoted_entries: list[dict] = []
        if candidate["count"] >= 3:
            promoted_entry = {
                **candidate,
                "promoted_at": datetime.now().isoformat(),
                "status": "promoted",
            }
            payload["promoted"].append(promoted_entry)
            payload["candidates"] = [c for c in payload["candidates"] if c.get("key") != key]
            promoted_entries.append(promoted_entry)
            self._write_preference_to_long_term(promoted_entry)

        self._write_json_obj(pref_path, payload)
        return {"updated": True, "promoted": promoted_entries}

    def _write_preference_to_long_term(self, pref: dict):
        evidence_lines = []
        for ev in pref.get("evidence", []):
            evidence_lines.append(
                f"- {ev.get('timestamp', '')} | {ev.get('output_id', '')} | score:{ev.get('score', '')} | {ev.get('context', '')}"
            )

        content = "\n".join([
            f"**偏好**: [{pref.get('polarity', '')}] {pref.get('signal', '')}",
            f"**主题**: {pref.get('topic', '')}",
            f"**置信度**: {pref.get('confidence', 0):.2f}",
            "**证据**:",
            *evidence_lines,
        ])
        self.write_long_term(content)

    def get_preference_context(self, limit: int = 5) -> str:
        """返回已晋升偏好的精简摘要。"""
        payload = self._read_json_obj(self.preferences_path(), {"candidates": [], "promoted": []})
        promoted = payload.get("promoted", [])
        if not promoted:
            return ""
        lines = ["\n## 稳定偏好"]
        for pref in promoted[-limit:]:
            lines.append(
                f"- [{pref.get('polarity', '')}] {pref.get('signal', '')} (主题: {pref.get('topic', '')}, 置信度: {pref.get('confidence', 0):.2f})"
            )
        return "\n".join(lines)

    # -- 技能反馈权重 ---
    def get_skill_feedback_boosts(self, max_items: int = 12) -> dict[str, float]:
        """根据近期评分对技能权重进行调整。"""
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        records = self._read_json_list(path)
        boosts: dict[str, float] = {}

        for i, record in enumerate(reversed(records[-max_items:])):
            score = int(record.get("score", 0))
            skills = record.get("matched_skills", [])
            if not skills:
                continue
            weight = max(0.2, 1.0 - i * 0.08)
            if score >= 6:
                delta = 0.12 * weight
            elif score <= 2:
                delta = -0.18 * weight
            else:
                delta = 0.0
            if delta == 0.0:
                continue
            for name in skills:
                boosts[name] = boosts.get(name, 0.0) + delta

        for name, value in list(boosts.items()):
            boosts[name] = max(-0.3, min(0.3, value))
        return boosts

    def get_recent_skill_judgments(self, skill_name: str, limit: int = 8) -> list[dict]:
        """获取关联到指定技能的最近评分记录。"""
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        records = self._read_json_list(path)
        matched = [r for r in reversed(records) if skill_name in r.get("matched_skills", [])]
        return matched[:limit]

    # -- 进化提案 ---
    def proposals_path(self) -> Path:
        return self.memory_dir / ".evolog" / "proposals.json"

    def evolog_daily_path(self, date: datetime | None = None) -> Path:
        dt = date or datetime.now()
        return self.memory_dir / ".evolog" / f"{dt.strftime('%Y-%m-%d')}.md"

    def record_evolution_proposal(self, proposal: dict) -> dict:
        """记录一条进化提案 (仅记录，不自动应用)。"""
        proposals = self._read_json_list(self.proposals_path())
        key = proposal.get("key", "")
        if key:
            existing = next((p for p in proposals if p.get("key") == key), None)
            if existing:
                return existing

        proposals.append(proposal)
        self._write_json_list(self.proposals_path(), proposals)

        md_lines = [
            f"## {proposal.get('created_at', '')}",
            f"**类型**: {proposal.get('type', '')}",
            f"**目标文件**: {', '.join(proposal.get('target_files', []))}",
            f"**说明**: {proposal.get('summary', '')}",
            "**证据**:",
        ]
        for ev in proposal.get("evidence", []):
            md_lines.append(
                f"- {ev.get('timestamp', '')} | {ev.get('output_id', '')} | score:{ev.get('score', '')} | {ev.get('context', '')}"
            )
        md_lines.append(f"**预期变更**: {proposal.get('expected_diff', '')}")
        md_lines.append(f"**应用约束**: {proposal.get('apply_guardrails', '')}")

        path = self.evolog_daily_path()
        entry = "\n".join(md_lines) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

        return proposal

    # -- 上下文注入用 ---
    def get_injectable_context(self) -> str:
        """获取可注入 Agent 上下文的最相关记忆。"""
        parts = []
        recent = self.read_daily(2)
        if recent.strip():
            parts.append(recent)
        return "\n".join(parts)
