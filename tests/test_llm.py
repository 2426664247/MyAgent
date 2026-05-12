import unittest

from agent_v2.llm import LLMClient
from agent_v2.settings import Settings


class LLMClientTests(unittest.TestCase):
    def test_deepseek_thinking_kwargs_enabled(self) -> None:
        client = LLMClient.__new__(LLMClient)
        client.settings = Settings(
            model="deepseek-v4-flash",
            api_key="k",
            base_url="https://api.deepseek.com",
            thinking_enabled=True,
        )

        kwargs = client._thinking_kwargs()

        self.assertEqual(kwargs["extra_body"]["thinking"]["type"], "enabled")
        self.assertEqual(kwargs["reasoning_effort"], "high")

    def test_deepseek_thinking_kwargs_disabled(self) -> None:
        client = LLMClient.__new__(LLMClient)
        client.settings = Settings(
            model="deepseek-v4-pro",
            api_key="k",
            base_url="https://api.deepseek.com",
            thinking_enabled=False,
        )

        kwargs = client._thinking_kwargs()

        self.assertEqual(kwargs["extra_body"]["thinking"]["type"], "disabled")
        self.assertNotIn("reasoning_effort", kwargs)

    def test_non_deepseek_no_extra_body(self) -> None:
        client = LLMClient.__new__(LLMClient)
        client.settings = Settings(
            model="gpt-4o-mini",
            api_key="k",
            base_url="https://api.openai.com/v1",
            thinking_enabled=True,
        )

        self.assertEqual(client._thinking_kwargs(), {})


if __name__ == "__main__":
    unittest.main()
