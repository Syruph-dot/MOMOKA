import json
import tempfile
import unittest
from pathlib import Path

from momoka.config import LIKERT_LABELS
from momoka.feedback import analyze_judgment
from momoka.memory import MemoryStore
from momoka.skill_loader import SkillLoader
from momoka.evolution import generate_evolution_proposals


class PreferencePromotionTests(unittest.TestCase):
    def test_same_output_id_does_not_count_multiple_times_for_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_dup",
                prompt="继续猜",
                response="用户偏好可追踪主循环",
                topic="MOMOKA 主循环",
            )
            judgment = store.record_judgment("out_dup", 6, "主循环")
            reflection = analyze_judgment(6, LIKERT_LABELS[6], "主循环", "MOMOKA 主循环")

            promoted = []
            for _ in range(3):
                result = store.update_preferences(judgment, reflection)
                promoted.extend(result.get("promoted", []))

            pref_data = json.loads(store.preferences_path().read_text(encoding="utf-8"))
            self.assertEqual(pref_data["candidates"][0]["count"], 1)
            self.assertEqual(pref_data["promoted"], [])
            self.assertEqual(promoted, [])

    def test_preference_promotes_after_three_high_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))

            promoted = []
            for i in range(3):
                output_id = f"out_pref_{i}"
                store.record_output(
                    output_id=output_id,
                    prompt="继续猜",
                    response="用户偏好可追踪的主循环",
                    topic="MOMOKA 主循环",
                )
                judgment = store.record_judgment(output_id, 6, "主循环")
                reflection = analyze_judgment(6, LIKERT_LABELS[6], "主循环", "MOMOKA 主循环")
                result = store.update_preferences(judgment, reflection)
                promoted.extend(result.get("promoted", []))

            pref_data = json.loads(store.preferences_path().read_text(encoding="utf-8"))
            self.assertEqual(len(pref_data["promoted"]), 1)
            self.assertTrue(any("主循环" in p.get("signal", "") for p in pref_data["promoted"]))
            self.assertIn("主循环", store.read_long_term())
            self.assertTrue(len(promoted) >= 1)


class EvolutionProposalTests(unittest.TestCase):
    def test_record_evolution_proposal_returns_existing_proposal_for_same_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            first = {
                "id": "evo_first",
                "key": "skill_rewrite:summarizer",
                "type": "skill_rewrite",
                "created_at": "2026-05-29T00:00:00",
                "target_files": ["skills/summarizer/SKILL.md"],
                "summary": "first",
                "expected_diff": "first diff",
                "apply_guardrails": "manual",
                "evidence": [],
            }
            second = {**first, "id": "evo_second", "summary": "second"}

            stored_first = store.record_evolution_proposal(first)
            stored_second = store.record_evolution_proposal(second)
            proposals_data = json.loads(store.proposals_path().read_text(encoding="utf-8"))

            self.assertEqual(stored_first["id"], "evo_first")
            self.assertEqual(stored_second["id"], "evo_first")
            self.assertEqual(len(proposals_data), 1)

    def test_skill_rewrite_proposal_after_repeated_low_scores(self):
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
                            "utility_score": 0.6,
                            "version": "1.0.0",
                            "path": "summarizer/SKILL.md",
                        }
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            loader = SkillLoader(skills_dir)
            store = MemoryStore(tmp_path / "memory")

            for i in range(3):
                output_id = f"out_low_{i}"
                store.record_output(
                    output_id=output_id,
                    prompt="总结",
                    response="输出偏离",
                    topic="测试",
                    matched_skills=["summarizer"],
                )
                store.record_judgment(output_id, 1, "偏离")

            judgment = store.get_recent_judgments(1)[0]
            proposals = generate_evolution_proposals(loader, store, judgment)

            self.assertTrue(any(p.get("type") == "skill_rewrite" for p in proposals))
            self.assertTrue(store.proposals_path().exists())

    def test_repeated_evolution_generation_returns_existing_proposal_once(self):
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
                            "utility_score": 0.6,
                            "version": "1.0.0",
                            "path": "summarizer/SKILL.md",
                        }
                    ]
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            loader = SkillLoader(skills_dir)
            store = MemoryStore(tmp_path / "memory")

            for i in range(3):
                output_id = f"out_low_repeat_{i}"
                store.record_output(
                    output_id=output_id,
                    prompt="总结",
                    response="输出偏离",
                    topic="测试",
                    matched_skills=["summarizer"],
                )
                store.record_judgment(output_id, 1, "偏离")

            judgment = store.get_recent_judgments(1)[0]
            first = generate_evolution_proposals(loader, store, judgment)
            second = generate_evolution_proposals(loader, store, judgment)
            proposals_data = json.loads(store.proposals_path().read_text(encoding="utf-8"))

            self.assertEqual(len(proposals_data), 1)
            self.assertEqual(first[0]["id"], second[0]["id"])


if __name__ == "__main__":
    unittest.main()
