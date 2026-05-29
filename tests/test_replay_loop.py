import tempfile
import unittest
from pathlib import Path

from momoka.config import LIKERT_LABELS
from momoka.feedback import analyze_judgment
from momoka.memory import MemoryStore
from momoka.replay import write_replay_record


class ReplayLoopTests(unittest.TestCase):
    def test_replay_record_covers_score_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = MemoryStore(tmp_path / "memory")

            steps = []
            topic = "MOMOKA 回放"
            for idx, score in enumerate([1, 4, 7], 1):
                output_id = f"out_replay_{idx}"
                output_text = f"输出 {score}"
                store.record_output(
                    output_id=output_id,
                    prompt="回放",
                    response=output_text,
                    topic=topic,
                )
                judgment = store.record_judgment(output_id, score, "")
                reflection = analyze_judgment(score, LIKERT_LABELS[score], judgment["context"], topic)

                steps.append({
                    "output_id": output_id,
                    "output_text": output_text,
                    "score": score,
                    "annotated_text": judgment["context"],
                    "reflection": reflection,
                    "next_output": f"下一轮 {score}",
                })

            record_path = write_replay_record(topic, steps, path=tmp_path / "replay.md")
            content = record_path.read_text(encoding="utf-8")

            self.assertIn("score: 1", content)
            self.assertIn("score: 4", content)
            self.assertIn("score: 7", content)
            self.assertTrue(record_path.exists())


if __name__ == "__main__":
    unittest.main()
