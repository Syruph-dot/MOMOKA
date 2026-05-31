"""
MOMOKA memory store.

Separates:
- output ledger: every agent output
- annotation ledger: every user annotation / grading event
- promoted preferences
- evolution proposals
- system-injectable daily memory
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path


class MemoryStore:
    """Filesystem-backed memory storage."""

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        (self.memory_dir / ".annotations").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / ".dreams" / "long-term").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / ".outputs").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / ".evolog").mkdir(parents=True, exist_ok=True)

    # -- daily memory -------------------------------------------------
    def daily_path(self, date: datetime | None = None) -> Path:
        dt = date or datetime.now()
        return self.memory_dir / f"{dt.strftime('%Y-%m-%d')}.md"

    def write_daily(self, content: str, date: datetime | None = None):
        path = self.daily_path(date)
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"\n## {ts}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        return path

    def read_daily(self, days_back: int = 2) -> str:
        lines = []
        for i in range(days_back):
            dt = datetime.now() - timedelta(days=i)
            path = self.daily_path(dt)
            if path.exists():
                lines.append(f"\n### 记忆: {dt.strftime('%Y-%m-%d')}")
                lines.append(path.read_text(encoding="utf-8")[:2000])
        return "\n".join(lines)

    def _filter_daily_entries_for_system(self, content: str) -> str:
        sections = re.split(r"(?m)(?=^## )", content)
        blocked_markers = ("**评分**", "**分析**", "**策略**", "**上下文**", "**文字批注**")
        kept: list[str] = []
        for section in sections:
            stripped = section.strip()
            if not stripped:
                continue
            if any(marker in stripped for marker in blocked_markers):
                continue
            kept.append(section.rstrip())
        return "\n".join(kept).strip()

    def get_injectable_context(self) -> str:
        parts: list[str] = []
        for i in range(2):
            dt = datetime.now() - timedelta(days=i)
            path = self.daily_path(dt)
            if not path.exists():
                continue
            filtered = self._filter_daily_entries_for_system(path.read_text(encoding="utf-8")[:2000])
            if filtered:
                parts.append(f"\n### 记忆: {dt.strftime('%Y-%m-%d')}")
                parts.append(filtered)
        return "\n".join(parts)

    # -- long-term memory --------------------------------------------
    def long_term_path(self) -> Path:
        return self.memory_dir / "MEMORY.md"

    def write_long_term(self, content: str):
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

    # -- generic json helpers ----------------------------------------
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

    # -- output ledger ------------------------------------------------
    def outputs_path(self) -> Path:
        return self.memory_dir / ".outputs" / "outputs.json"

    def record_output(
        self,
        output_id: str,
        prompt: str,
        response: str,
        topic: str = "",
        matched_skills: list[str] | None = None,
        tool_calls: list[dict] | None = None,
        session_id: str | None = None,
    ) -> dict:
        record = {
            "output_id": output_id,
            "topic": topic,
            "prompt": prompt,
            "response": response,
            "matched_skills": matched_skills or [],
            "tool_calls": tool_calls or [],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }
        path = self.outputs_path()
        records = [r for r in self._read_json_list(path) if r.get("output_id") != output_id]
        records.append(record)
        self._write_json_list(path, records[-200:])
        return record

    def get_output(self, output_id: str) -> dict | None:
        for record in reversed(self._read_json_list(self.outputs_path())):
            if record.get("output_id") == output_id:
                return record
        return None

    # -- annotation ledger -------------------------------------------
    def annotation_ledger_path(self) -> Path:
        return self.memory_dir / ".annotations" / "ledger.json"

    def legacy_judgments_path(self) -> Path:
        return self.memory_dir / ".dreams" / "short-term-recall.json"

    def _read_annotation_records(self) -> list[dict]:
        records = self._read_json_list(self.annotation_ledger_path())
        if records:
            return records
        return self._read_json_list(self.legacy_judgments_path())

    def _write_annotation_records(self, records: list[dict]):
        self._write_json_list(self.annotation_ledger_path(), records)
        self._write_json_list(self.legacy_judgments_path(), records)

    def record_judgment(self, output_id: str, score: int, context: str = "", comment: str = ""):
        output = self.get_output(output_id) or {}
        selected = context.strip()
        note = comment.strip()
        full_output = str(output.get("response", "")).strip()
        resolved_context = selected or full_output
        record = {
            "output_id": output_id,
            "score": score,
            "context": resolved_context[:2000],
            "context_source": "selected_text" if selected else "full_output",
            "comment": note[:1000],
            "comment_source": "user_comment" if note else "none",
            "topic": output.get("topic", ""),
            "matched_skills": output.get("matched_skills", []),
            "timestamp": datetime.now().isoformat(),
        }
        records = self._read_annotation_records()
        records.append(record)
        self._write_annotation_records(records)
        return record

    def get_recent_judgments(self, count: int = 3) -> list[dict]:
        records = self._read_annotation_records()
        return records[-count:]

    def list_annotation_records(self) -> list[dict]:
        return list(self._read_annotation_records())

    # -- preferences --------------------------------------------------
    def preferences_path(self) -> Path:
        return self.memory_dir / ".preferences.json"

    def _normalize_signal(self, text: str) -> str:
        compact = re.sub(r"\s+", "", text.strip().lower())
        return compact[:120]

    def _derive_preference_signal(self, judgment: dict, reflection: dict) -> str:
        comment = (judgment.get("comment") or "").strip()
        context = (judgment.get("context") or "").strip()
        polarity = "prefer" if int(judgment.get("score", 0)) >= 6 else "avoid"
        if comment:
            if context:
                return f"{polarity}:{context} => {comment}"[:240]
            return f"{polarity}:{comment}"[:240]
        if context:
            return f"{polarity}:{context}"[:240]
        return (reflection.get("intent_hypothesis") or "").strip()[:240]

    def update_preferences(self, judgment: dict, reflection: dict) -> dict:
        score = int(judgment.get("score", 0))
        if score not in (1, 2, 6, 7):
            return {"updated": False, "promoted": []}

        polarity = "prefer" if score >= 6 else "avoid"
        signal = self._derive_preference_signal(judgment, reflection)
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
            "comment": judgment.get("comment", "")[:200],
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
            comment = ev.get("comment", "")
            comment_suffix = f" | comment:{comment}" if comment else ""
            evidence_lines.append(
                f"- {ev.get('timestamp', '')} | {ev.get('output_id', '')} | score:{ev.get('score', '')} | {ev.get('context', '')}{comment_suffix}"
            )

        content = "\n".join([
            f"**偏好**: [{pref.get('polarity', '')}] {pref.get('signal', '')}",
            f"**主题**: {pref.get('topic', '')}",
            f"**置信度**: {pref.get('confidence', 0):.2f}",
            "**证据**:",
            *evidence_lines,
        ])
        self.write_long_term(content)

    def get_promoted_preferences(self) -> list[dict]:
        payload = self._read_json_obj(self.preferences_path(), {"candidates": [], "promoted": []})
        return list(payload.get("promoted", []))

    def get_preference_context(self, limit: int = 5) -> str:
        payload = self._read_json_obj(self.preferences_path(), {"candidates": [], "promoted": []})
        promoted = payload.get("promoted", [])
        if not promoted:
            return ""
        lines = ["\n## 稳定偏好"]
        for pref in promoted[-limit:]:
            lines.append(
                f"- [{pref.get('polarity', '')}] {pref.get('signal', '')} (主题: {pref.get('topic', '')}, 置信度 {pref.get('confidence', 0):.2f})"
            )
        return "\n".join(lines)

    # -- skill feedback weighting ------------------------------------
    def get_skill_feedback_boosts(self, max_items: int = 12) -> dict[str, float]:
        records = self._read_annotation_records()
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
        records = self._read_annotation_records()
        matched = [r for r in reversed(records) if skill_name in r.get("matched_skills", [])]
        return matched[:limit]

    # -- evolution proposals -----------------------------------------
    def proposals_path(self) -> Path:
        return self.memory_dir / ".evolog" / "proposals.json"

    def evolog_daily_path(self, date: datetime | None = None) -> Path:
        dt = date or datetime.now()
        return self.memory_dir / ".evolog" / f"{dt.strftime('%Y-%m-%d')}.md"

    def record_evolution_proposal(self, proposal: dict) -> dict:
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
            comment = ev.get("comment", "")
            comment_suffix = f" | comment:{comment}" if comment else ""
            md_lines.append(
                f"- {ev.get('timestamp', '')} | {ev.get('output_id', '')} | score:{ev.get('score', '')} | {ev.get('context', '')}{comment_suffix}"
            )
        md_lines.append(f"**预期变更**: {proposal.get('expected_diff', '')}")
        md_lines.append(f"**应用约束**: {proposal.get('apply_guardrails', '')}")

        with open(self.evolog_daily_path(), "a", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        return proposal
