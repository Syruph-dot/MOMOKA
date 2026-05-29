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

    def match_skills(self, user_message: str) -> list[dict]:
        """根据用户消息匹配相关技能（关键词匹配）。"""
        matched = []
        msg_lower = user_message.lower()
        for skill in self.list_skills():
            keywords = skill.get("trigger_keywords", [])
            for kw in keywords:
                if kw.lower() in msg_lower:
                    skill_def = self.load_skill(skill["name"])
                    if skill_def:
                        matched.append({
                            "meta": skill,
                            "content": skill_def,
                        })
                    break
        return matched

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

        lines.append(f"### 技能 {i}: {name} (效用: {score:.0%})")
        lines.append(f"{desc}\n")
        lines.append(content)
        lines.append("---")

    return "\n".join(lines)
