"""Evolution proposal helpers for MOMOKA (no auto-apply)."""

from __future__ import annotations

from datetime import datetime


def _find_skill_path(skill_loader, skill_name: str) -> str:
    for skill in skill_loader.list_skills():
        if skill.get("name") == skill_name:
            return str(skill_loader.skills_dir / skill.get("path", ""))
    return ""


def _build_proposal(
    proposal_type: str,
    skill_name: str,
    evidence: list[dict],
    target_files: list[str],
    summary: str,
    expected_diff: str,
) -> dict:
    created_at = datetime.now().isoformat()
    return {
        "id": f"evo_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "key": f"{proposal_type}:{skill_name}",
        "type": proposal_type,
        "skill": skill_name,
        "status": "pending",
        "created_at": created_at,
        "summary": summary,
        "target_files": target_files,
        "expected_diff": expected_diff,
        "apply_guardrails": "require_clean_git=true; backup_branch=true",
        "evidence": evidence,
    }


def generate_evolution_proposals(skill_loader, memory_store, judgment: dict) -> list[dict]:
    """Generate skill rewrite/solidify proposals based on repeated feedback."""
    proposals: list[dict] = []
    skills = judgment.get("matched_skills", [])
    if not skills:
        return []

    for skill_name in skills:
        evidence_all = memory_store.get_recent_skill_judgments(skill_name, limit=8)
        negatives = [e for e in evidence_all if int(e.get("score", 0)) <= 2]
        positives = [e for e in evidence_all if int(e.get("score", 0)) >= 6]

        if len(negatives) >= 3:
            skill_path = _find_skill_path(skill_loader, skill_name)
            targets = [p for p in [skill_path] if p]
            summary = f"{skill_name} 多次低分反馈，建议重写技能说明或例子。"
            expected = "更新技能触发条件、补充反例或新增约束，避免触发偏差。"
            proposals.append(
                _build_proposal(
                    "skill_rewrite",
                    skill_name,
                    negatives[:3],
                    targets,
                    summary,
                    expected,
                )
            )

        if len(positives) >= 3:
            skill_path = _find_skill_path(skill_loader, skill_name)
            targets = [p for p in [skill_path, "prompts/AGENTS.md"] if p]
            summary = f"{skill_name} 多次高分反馈，建议固化到技能或主提示词。"
            expected = "沉淀高分模式为技能段落或主提示词规范，减少重复探索。"
            proposals.append(
                _build_proposal(
                    "skill_promote",
                    skill_name,
                    positives[:3],
                    targets,
                    summary,
                    expected,
                )
            )

    recorded = []
    for proposal in proposals:
        recorded.append(memory_store.record_evolution_proposal(proposal))
    return recorded
