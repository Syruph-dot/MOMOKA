import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from momoka.config import load_local_env


class EnvLoadingTests(unittest.TestCase):
    def test_load_local_env_reads_key_without_overriding_existing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "ALIYUN_API_KEY=from_file\nMOMOKA_MODEL=file_model\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"MOMOKA_MODEL": "existing_model"}, clear=True):
                load_local_env(Path(tmp))

                self.assertEqual(os.environ["ALIYUN_API_KEY"], "from_file")
                self.assertEqual(os.environ["MOMOKA_MODEL"], "existing_model")


if __name__ == "__main__":
    unittest.main()
