import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_v2.env_config import masked_config, read_env_config, write_env_config


class EnvConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.env_path = self.tmp / ".env"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_and_read_env_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            write_env_config({
                "LLM_API_KEY": "secret-key",
                "LLM_BASE_URL": "https://api.deepseek.com",
                "LLM_MODEL": "deepseek-v4-flash",
                "LLM_THINKING": "enabled",
            }, self.env_path)
            data = read_env_config(self.env_path)

        self.assertEqual(data["LLM_API_KEY"], "secret-key")
        self.assertEqual(data["LLM_BASE_URL"], "https://api.deepseek.com")
        self.assertEqual(data["LLM_MODEL"], "deepseek-v4-flash")
        self.assertEqual(data["LLM_THINKING"], "enabled")

    def test_masked_config_hides_key(self) -> None:
        self.env_path.write_text("LLM_API_KEY=abcdefghijk\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            data = masked_config(self.env_path)

        self.assertEqual(data["LLM_API_KEY"], "")
        self.assertEqual(data["LLM_API_KEY_MASKED"], "abcd...hijk")


if __name__ == "__main__":
    unittest.main()
