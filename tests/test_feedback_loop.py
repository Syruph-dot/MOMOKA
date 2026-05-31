import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_agent
from momoka.config import LIKERT_LABELS
from momoka.feedback import analyze_judgment, build_followup_prompt
from momoka.memory import MemoryStore
from momoka.runtime_context import AnnotationRuntimeController


class FeedbackLoopTests(unittest.TestCase):
    def test_sync_runtime_control_can_auto_revise_output(self):
        class FakeResult:
            def __init__(self, output: str):
                self.final_output = output
                self.new_items = []

        def fake_run_sync(agent, message):
            if "## 输出修订指令" in message:
                return FakeResult("修订后的输出")
            if "继续写这个小说" in message:
                return FakeResult("终端里再次闪过蓝光")
            return FakeResult("第一轮输出")

        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_sync_block",
                prompt="继续写小说",
                response="这里用了蓝光",
                topic="小说",
            )
            store.record_judgment("out_sync_block", 2, "蓝光", "可以是别的颜色的光")

            with (
                patch.object(file_agent, "memory_store", store),
                patch.object(file_agent.Runner, "run_sync", side_effect=fake_run_sync),
            ):
                result, runtime_context, assessment = file_agent.run_with_annotation_runtime_control_sync(
                    agent=object(),
                    user_message="继续写这个小说",
                    topic="小说",
                )

            self.assertEqual(result.final_output, "修订后的输出")
            self.assertIn("可以是别的颜色的光", runtime_context)
            self.assertEqual(assessment["action"], "revise")
            self.assertTrue(any("蓝光" in reason for reason in assessment["reasons"]))

    def test_system_prompt_excludes_raw_annotation_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_prompt",
                prompt="继续猜",
                response="先沿着这个方向写下去",
                topic="批注账本",
            )
            store.record_judgment("out_prompt", 2, "先沿着这个方向", "这里的判断标准错了")

            with patch.object(file_agent, "memory_store", store):
                prompt = file_agent.build_system_prompt("继续", topic="批注账本")

            self.assertNotIn("用户最近反馈", prompt)
            self.assertNotIn("<AnnotateText>", prompt)
            self.assertNotIn("这里的判断标准错了", prompt)

    def test_annotation_runtime_context_is_built_from_full_ledger_not_recent_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            controller = AnnotationRuntimeController(store)

            comments = [
                "第一条批注",
                "第二条批注",
                "第三条批注",
                "第四条批注",
                "第五条批注",
            ]
            for idx, comment in enumerate(comments, 1):
                output_id = f"out_rule_{idx}"
                store.record_output(
                    output_id=output_id,
                    prompt="继续写",
                    response=f"输出 {idx}",
                    topic="小说",
                )
                store.record_judgment(output_id, 6 if idx % 2 else 2, f"片段 {idx}", comment)

            bundle = controller.build_runtime_bundle(
                user_message="继续写这个小说",
                topic="小说",
            )
            runtime_text = controller.render_runtime_context(bundle)

            self.assertEqual(bundle["ledger_size"], 5)
            self.assertIn("第一条批注", runtime_text)
            self.assertIn("第五条批注", runtime_text)
            self.assertIn("## 批注账本规则", runtime_text)

    def test_system_prompt_filters_annotation_entries_from_daily_memory_and_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.write_daily("**用户**: 普通记录\n**Agent**: 普通回复")
            store.write_daily("**评分**: 2/7\n**分析**: 这里不对\n**文字批注**: 删掉这个判断")
            pref_payload = {
                "candidates": [],
                "promoted": [
                    {
                        "key": "prefer:小说:保留这种判断路径",
                        "polarity": "prefer",
                        "signal": "保留这种判断路径",
                        "topic": "小说",
                        "confidence": 0.9,
                    }
                ],
            }
            store._write_json_obj(store.preferences_path(), pref_payload)

            with patch.object(file_agent, "memory_store", store):
                prompt = file_agent.build_system_prompt("继续", topic="小说")

            self.assertIn("普通记录", prompt)
            self.assertNotIn("删掉这个判断", prompt)
            self.assertNotIn("保留这种判断路径", prompt)

    def test_annotation_runtime_controller_can_flag_output_for_same_turn_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            controller = AnnotationRuntimeController(store)
            store.record_output(
                output_id="out_bad_rule",
                prompt="继续写小说",
                response="这里用了蓝光",
                topic="小说",
            )
            store.record_judgment("out_bad_rule", 2, "蓝光", "可以是别的颜色的光")

            bundle = controller.build_runtime_bundle("继续写这个小说", topic="小说")
            assessment = controller.assess_output(bundle, "终端里再次闪过蓝光")

            self.assertEqual(assessment["action"], "revise")
            self.assertTrue(any("蓝光" in reason for reason in assessment["reasons"]))
            self.assertIn("可以是别的颜色的光", assessment["revision_prompt"])

    def test_annotation_runtime_controller_can_build_runtime_and_revision_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            controller = AnnotationRuntimeController(store)
            store.record_output(
                output_id="out_runtime_build",
                prompt="继续写小说",
                response="这里用了蓝光",
                topic="小说",
            )
            store.record_judgment("out_runtime_build", 2, "蓝光", "可以是别的颜色的光")

            envelope = controller.build_runtime_envelope(
                user_message="继续写这个小说",
                topic="小说",
                request_heading="当前用户请求",
            )
            assessment = controller.assess_output(envelope["bundle"], "终端里再次闪过蓝光")
            revision_input = controller.build_revision_input(
                runtime_context=envelope["runtime_context"],
                request_heading="当前用户请求",
                request_text="继续写这个小说",
                assessment=assessment,
            )

            self.assertIn("## 批注账本规则", envelope["runtime_context"])
            self.assertIn("## 当前用户请求", envelope["runtime_input"])
            self.assertIn("继续写这个小说", envelope["runtime_input"])
            self.assertIn("## 输出修订指令", revision_input)
            self.assertIn("可以是别的颜色的光", revision_input)

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

    def test_optional_comment_is_preserved_with_judgment(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.record_output(
                output_id="out_comment",
                prompt="继续猜",
                response="用户真正关心的是低成本反馈。",
                topic="批注式判断",
            )

            judgment = store.record_judgment("out_comment", 6, "低成本反馈", "这里方向对")

            self.assertEqual(judgment["comment"], "这里方向对")
            self.assertEqual(judgment["comment_source"], "user_comment")

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

    def test_followup_prompt_includes_optional_comment(self):
        reflection = analyze_judgment(
            6,
            LIKERT_LABELS[6],
            "选中的判断",
            "MOMOKA 批注协议",
            "这个判断标准正确",
        )

        prompt = build_followup_prompt(
            topic="MOMOKA 批注协议",
            output_text="上一轮 Agent 输出",
            judgment={
                "score": 6,
                "label": LIKERT_LABELS[6],
                "context": "选中的判断",
                "comment": "这个判断标准正确",
            },
            reflection=reflection,
        )

        self.assertIn("文字批注: 这个判断标准正确", prompt)
        self.assertIn("用户明确补充的判断标准", reflection["intent_hypothesis"])


if __name__ == "__main__":
    unittest.main()
