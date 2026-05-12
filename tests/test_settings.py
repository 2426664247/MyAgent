import os
import unittest
from unittest.mock import patch

from agent_v2.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_deepseek_defaults(self) -> None:
        env = {
            "DEEPSEEK_API_KEY": "ds-key",
        }
        with patch("agent_v2.settings.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.api_key, "ds-key")
        self.assertEqual(settings.base_url, "https://api.deepseek.com")
        self.assertEqual(settings.model, "deepseek-v4-flash")
        self.assertTrue(settings.thinking_enabled)

    def test_llm_api_key_still_has_priority(self) -> None:
        env = {
            "LLM_API_KEY": "llm-key",
            "DEEPSEEK_API_KEY": "ds-key",
            "LLM_BASE_URL": "https://example.com/v1",
            "LLM_MODEL": "custom-model",
        }
        with patch("agent_v2.settings.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.api_key, "llm-key")
        self.assertEqual(settings.base_url, "https://example.com/v1")
        self.assertEqual(settings.model, "custom-model")

    def test_thinking_can_be_disabled(self) -> None:
        env = {
            "DEEPSEEK_API_KEY": "ds-key",
            "LLM_THINKING": "disabled",
        }
        with patch("agent_v2.settings.load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertFalse(settings.thinking_enabled)


if __name__ == "__main__":
    unittest.main()
