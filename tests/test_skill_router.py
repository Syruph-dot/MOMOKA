import json
import tempfile
import unittest
from pathlib import Path

from momoka.skill_loader import SkillLoader


class SkillRouterTests(unittest.TestCase):
    def test_high_utility_skill_does_not_match_without_relevance_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            (skills_dir / "summarizer").mkdir()
            (skills_dir / "summarizer" / "SKILL.md").write_text("# Summarizer", encoding="utf-8")
            (skills_dir / "index.json").write_text(
                json.dumps({
                    "skills": [
                        {
                            "name": "summarizer",
                            "description": "读取文件并生成结构化摘要",
                            "trigger_keywords": ["总结"],
                            "utility_score": 0.95,
                            "version": "1.0.0",
                            "path": "summarizer/SKILL.md",
                        }
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            loader = SkillLoader(skills_dir)
            matched = loader.match_skills("今天只聊 MOMOKA 主循环")

            self.assertEqual(matched, [])

    def test_feedback_boost_can_raise_skill_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            (skills_dir / "summarizer").mkdir()
            (skills_dir / "summarizer" / "SKILL.md").write_text("# Summarizer", encoding="utf-8")
            (skills_dir / "index.json").write_text(
                json.dumps({
                    "skills": [
                        {
                            "name": "summarizer",
                            "description": "读取文件并生成结构化摘要",
                            "trigger_keywords": ["总结"],
                            "utility_score": 0.5,
                            "version": "1.0.0",
                            "path": "summarizer/SKILL.md",
                        }
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            loader = SkillLoader(skills_dir)
            matched = loader.match_skills(
                "随便聊聊",
                feedback_boosts={"summarizer": 0.3},
            )

            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["meta"]["name"], "summarizer")
            self.assertTrue(any("feedback" in r for r in matched[0].get("reasons", [])))


if __name__ == "__main__":
    unittest.main()
