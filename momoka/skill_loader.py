"""
MOMOKA Skill 系统 — 从外部 Markdown 文件加载技能定义。
参考: Memento-Skills (Read-Write-Reflect), AceForge (Skill Lifecycle)
"""

import json
import re
from pathlib import Path
from datetime import datetime


class SkillLoader:
    """技能加载与路由器。"""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        self.index_path = self.skills_dir / "index.json"
        self._index = None

    @property
    def index(self) -> dict:
        if self._index is None:
            self._index = self._load_index()
        return self._index

    def _load_index(self) -> dict:
        if not self.index_path.exists():
            return {"skills": []}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {"skills": []}

    def list_skills(self) -> list[dict]:
        return self.index.get("skills", [])

    def match_skills(
        self,
        user_message: str,
        topic: str = "",
        feedback_boosts: dict[str, float] | None = None,
        min_score: float = 0.55,
        top_k: int = 4,
    ) -> list[dict]:
        """根据用户消息匹配相关技能（关键词 + 反馈权重）。"""
        matched = []
        msg_lower = (user_message or "").lower()
        topic_lower = (topic or "").lower()
        feedback_boosts = feedback_boosts or {}

        for skill in self.list_skills():
            score, reasons = self._score_skill(skill, msg_lower, topic_lower, feedback_boosts)
            if score < min_score:
                continue
            skill_def = self.load_skill(skill["name"])
            if not skill_def:
                continue
            matched.append({
                "meta": skill,
                "content": skill_def,
                "score": score,
                "reasons": reasons,
            })

        matched.sort(key=lambda x: x.get("score", 0), reverse=True)
        return matched[:top_k]

    def _score_skill(
        self,
        skill: dict,
        msg_lower: str,
        topic_lower: str,
        feedback_boosts: dict[str, float],
    ) -> tuple[float, list[str]]:
        utility = float(skill.get("utility_score", 0.5))
        score = 0.0
        reasons: list[str] = [f"utility:{utility:.2f}"]

        keywords = skill.get("trigger_keywords", [])
        keyword_hits = [kw for kw in keywords if kw.lower() in msg_lower or kw.lower() in topic_lower]
        if keyword_hits:
            score += 0.45 + (0.2 * utility) + 0.03 * len(keyword_hits)
            reasons.append("keywords:" + ",".join(keyword_hits[:3]))

        desc = (skill.get("description") or "").strip()
        if desc:
            tokens = [t for t in re.split(r"[\s/·、，,。]+", desc) if len(t) >= 2]
            if any(t.lower() in msg_lower or t.lower() in topic_lower for t in tokens):
                score += 0.28 + (0.12 * utility)
                reasons.append("desc-match")

        fb = float(feedback_boosts.get(skill.get("name", ""), 0.0))
        if fb:
            if fb > 0:
                score += 0.25 + fb + (0.1 * utility)
            else:
                score += fb
            reasons.append(f"feedback:{fb:+.2f}")

        return score, reasons

    def load_skill(self, name: str) -> str | None:
        """加载指定技能的 SKILL.md 内容。"""
        for skill in self.list_skills():
            if skill["name"] == name:
                skill_path = self.skills_dir / skill["path"]
                if skill_path.exists():
                    return skill_path.read_text(encoding="utf-8")
        return None

    def register_skill(self, name: str, path: str, keywords: list[str], description: str = ""):
        """注册新技能到索引。"""
        skills = self.list_skills()
        for s in skills:
            if s["name"] == name:
                s["trigger_keywords"] = list(set(s.get("trigger_keywords", []) + keywords))
                s["utility_score"] = min(1.0, s.get("utility_score", 0.5) + 0.05)
                self._save_index()
                return s

        skills.append({
            "name": name,
            "description": description,
            "trigger_keywords": keywords,
            "utility_score": 0.5,
            "version": "1.0.0",
            "path": path,
        })
        self._save_index()
        return skills[-1]

    def _save_index(self):
        self.index_path.write_text(
            json.dumps({"skills": self._index["skills"]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def format_skill_prompt(matched_skills: list[dict]) -> str:
    """将匹配到的技能格式化为可注入 system prompt 的文本。"""
    if not matched_skills:
        return ""

    lines = ["\n## 已加载技能 (Skills)\n"]
    for i, skill in enumerate(matched_skills, 1):
        meta = skill["meta"]
        content = skill["content"]

        # 提取 YAML frontmatter 和正文
        name = meta.get("name", f"skill_{i}")
        desc = meta.get("description", "")
        score = meta.get("utility_score", 0)

        reasons = skill.get("reasons", [])
        lines.append(f"### 技能 {i}: {name} (效用: {score:.0%})")
        if reasons:
            lines.append(f"理由: {', '.join(reasons)}")
        lines.append(f"{desc}\n")
        lines.append(content)
        lines.append("---")

    return "\n".join(lines)
