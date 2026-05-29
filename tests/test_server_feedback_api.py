import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.testclient import TestClient

import server
from momoka.memory import MemoryStore


class FakeResult:
    def __init__(self, output: str):
        self.final_output = output
        self.new_items = []


async def fake_runner_run(agent, message):
    if "上一轮输出" in message:
        return FakeResult("下一轮主动猜测")
    return FakeResult("第一轮输出")


class ServerFeedbackApiTests(unittest.TestCase):
    def test_judge_rejects_unknown_output_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            client = TestClient(server.app)

            with patch.object(server, "memory_store", store):
                res = client.post(
                    "/api/judge",
                    json={"output_id": "missing", "score": 5, "context": ""},
                )

                self.assertEqual(res.status_code, 404)
                self.assertIn("output_id", res.json()["error"])

    def test_chat_generates_output_id_when_client_omits_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            client = TestClient(server.app)

            with (
                patch.object(server, "memory_store", store),
                patch.object(server.Runner, "run", side_effect=fake_runner_run),
                patch.object(server, "trace", _noop_trace),
            ):
                chat_res = client.post(
                    "/api/chat",
                    json={"message": "MOMOKA 的默认主题"},
                )

                self.assertEqual(chat_res.status_code, 200)
                output_id = chat_res.json()["output_id"]
                self.assertTrue(output_id.startswith("out_"))
                self.assertEqual(store.get_output(output_id)["response"], "第一轮输出")

    def test_chat_records_output_and_judge_can_continue_without_user_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            client = TestClient(server.app)

            with (
                patch.object(server, "memory_store", store),
                patch.object(server.Runner, "run", side_effect=fake_runner_run),
                patch.object(server, "trace", _noop_trace),
            ):
                chat_res = client.post(
                    "/api/chat",
                    json={
                        "message": "本轮主题是 MOMOKA 的批注式判断",
                        "output_id": "out_api_1",
                        "topic": "MOMOKA 批注式判断",
                    },
                )
                self.assertEqual(chat_res.status_code, 200)
                self.assertEqual(chat_res.json()["response"], "第一轮输出")

                recorded = store.get_output("out_api_1")
                self.assertEqual(recorded["response"], "第一轮输出")
                self.assertEqual(recorded["topic"], "MOMOKA 批注式判断")

                judge_res = client.post(
                    "/api/judge",
                    json={
                        "output_id": "out_api_1",
                        "score": 7,
                        "context": "",
                        "comment": "继续深化这个方向",
                        "continue": True,
                    },
                )

                self.assertEqual(judge_res.status_code, 200)
                data = judge_res.json()
                self.assertEqual(data["annotated_text"], "第一轮输出")
                self.assertEqual(data["comment"], "继续深化这个方向")
                self.assertIn("继续深化这个方向", data["analysis"])
                self.assertEqual(data["reflection"]["next_guess_strategy"], "deepen")
                self.assertEqual(data["next_response"], "下一轮主动猜测")
                self.assertTrue(data["next_output_id"].startswith("out_"))


class _noop_trace:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


if __name__ == "__main__":
    unittest.main()
