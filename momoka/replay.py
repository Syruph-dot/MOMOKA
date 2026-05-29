"""Replay record helpers for MOMOKA feedback loops."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from momoka.config import LOGS_DIR


def write_replay_record(topic: str, steps: list[dict], path: Path | None = None) -> Path:
    """Write a readable replay record for the feedback loop."""
    if path is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = LOGS_DIR / f"replay-{ts}.md"

    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# MOMOKA 回放记录",
        f"主题: {topic}",
        "",
    ]

    for idx, step in enumerate(steps, 1):
        reflection = step.get("reflection", {})
        lines.extend([
            f"## Step {idx}",
            f"- output_id: {step.get('output_id', '')}",
            f"- score: {step.get('score', '')}",
            f"- annotated_text: {step.get('annotated_text', '')}",
            "",
            "### output",
            step.get("output_text", ""),
            "",
            "### reflection",
            f"- stance: {reflection.get('stance', '')}",
            f"- strategy: {reflection.get('next_guess_strategy', '')}",
            f"- intent: {reflection.get('intent_hypothesis', '')}",
            f"- instruction: {reflection.get('next_guess_instruction', '')}",
            "",
            "### next_output",
            step.get("next_output", ""),
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
