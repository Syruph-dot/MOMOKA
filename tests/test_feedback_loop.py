import tempfile
import unittest
from pathlib import Path

from momoka.config import LIKERT_LABELS
from momoka.feedback import analyze_judgment, build_followup_prompt
from momoka.memory import MemoryStore


class FeedbackLoopTests(unittest.TestCase):
    def test_output_record_can_be_used_as_default_annotation_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_1",
                prompt="写一个项目建议",
                response="第一段建议。\n第二段建议。",
                topic="MOMOKA 自我进化",
                matched_skills=["summarizer"],
                tool_calls=[{"tool": "read_file", "args": "{}", "result": "ok"}],
            )

            judgment = store.record_judgment("out_1", 6, "")

            self.assertEqual(judgment["output_id"], "out_1")
            self.assertEqual(judgment["context"], "第一段建议。\n第二段建议。")
            self.assertEqual(judgment["context_source"], "full_output")
            self.assertEqual(judgment["topic"], "MOMOKA 自我进化")

            stored = store.get_output("out_1")
            self.assertEqual(stored["response"], "第一段建议。\n第二段建议。")
            self.assertEqual(stored["matched_skills"], ["summarizer"])

    def test_selected_text_is_preserved_as_annotation_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_2",
                prompt="继续猜",
                response="用户真正关心的是低成本反馈。",
                topic="批注式判断",
            )

            judgment = store.record_judgment("out_2", 2, "低成本反馈")

            self.assertEqual(judgment["context"], "低成本反馈")
            self.assertEqual(judgment["context_source"], "selected_text")

    def test_structured_reflection_maps_scores_to_next_guess_strategy(self):
        low = analyze_judgment(2, LIKERT_LABELS[2], "过度强调工具", "Agent 主题")
        neutral = analyze_judgment(4, LIKERT_LABELS[4], "自我进化", "Agent 主题")
        high = analyze_judgment(7, LIKERT_LABELS[7], "批注驱动", "Agent 主题")

        self.assertEqual(low["stance"], "reject")
        self.assertEqual(low["next_guess_strategy"], "pivot")
        self.assertIn("不要沿用", low["next_guess_instruction"])

        self.assertEqual(neutral["stance"], "ambivalent")
        self.assertEqual(neutral["next_guess_strategy"], "diverge")
        self.assertIn("并行假设", neutral["next_guess_instruction"])

        self.assertEqual(high["stance"], "endorse")
        self.assertEqual(high["next_guess_strategy"], "deepen")
        self.assertIn("深化", high["next_guess_instruction"])

    def test_followup_prompt_supports_score_only_continuation(self):
        reflection = analyze_judgment(
            5,
            LIKERT_LABELS[5],
            "用户划选了输出里关于零文本输入的部分",
            "MOMOKA 批注协议",
        )

        prompt = build_followup_prompt(
            topic="MOMOKA 批注协议",
            output_text="上一轮 Agent 输出",
            judgment={
                "score": 5,
                "label": LIKERT_LABELS[5],
                "context": "用户划选了输出里关于零文本输入的部分",
            },
            reflection=reflection,
        )

        self.assertIn("不要要求用户补充文字", prompt)
        self.assertIn("MOMOKA 批注协议", prompt)
        self.assertIn("上一轮 Agent 输出", prompt)
        self.assertIn("用户划选了输出里关于零文本输入的部分", prompt)
        self.assertIn(reflection["next_guess_instruction"], prompt)


if __name__ == "__main__":
    unittest.main()
