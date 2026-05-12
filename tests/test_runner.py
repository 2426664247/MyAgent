import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_v2.llm import LLMClient
from agent_v2.runner import AgentRunner, _make_fake_tool_calls
from agent_v2.settings import Settings


class FakeMessage:
    """模拟 ChatCompletionMessage。"""

    def __init__(
        self,
        content: str | None = None,
        tool_calls: list | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self) -> dict:
        d: dict = {"role": "assistant"}
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in self.tool_calls
            ]
        return d


class FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, call_id: str, name: str, args: dict):
        self.id = call_id
        self.function = FakeFunction(name, json.dumps(args))


def _make_mock_llm(*, chat_side_effect=None, chat_return=None):
    """构造一个行为可控的 mock LLM。"""
    mock_llm = MagicMock()
    if chat_side_effect is not None:
        mock_llm.chat = MagicMock(side_effect=chat_side_effect)
    else:
        mock_llm.chat = MagicMock(return_value=chat_return)
    mock_llm.try_parse_tool_calls_from_text = MagicMock(return_value=None)
    return mock_llm


class RunnerFinalAnswerTests(unittest.TestCase):
    """模型直接返回最终答案的场景。"""

    @patch("agent_v2.runner.register_all")
    @patch.object(LLMClient, "__init__", lambda self, *a, **kw: None)
    def test_direct_answer(self, _mock_register) -> None:
        settings = Settings(model="test", api_key="k", base_url=None)
        agent = AgentRunner(settings=settings, project_dir=Path("."))
        agent.llm = _make_mock_llm(chat_return=FakeMessage(content="42"))

        result = agent.run("what is 6*7?")
        self.assertEqual(result, "42")


class RunnerToolCallTests(unittest.TestCase):
    """模型通过 function calling 调用工具的场景。"""

    @patch("agent_v2.runner.register_all")
    @patch.object(LLMClient, "__init__", lambda self, *a, **kw: None)
    def test_tool_call_then_answer(self, _mock_register) -> None:
        settings = Settings(model="test", api_key="k", base_url=None)
        agent = AgentRunner(settings=settings, project_dir=Path("."))

        tool_tc = FakeToolCall("call_1", "list_files", {})
        step1_msg = FakeMessage(tool_calls=[tool_tc])
        step2_msg = FakeMessage(content="Here are the files.")

        agent.llm = _make_mock_llm(chat_side_effect=[step1_msg, step2_msg])

        with patch("agent_v2.runner.get_registry") as mock_reg:
            mock_entry = MagicMock()
            mock_entry.confirm = False
            mock_entry.handler.return_value = "file1.py\nfile2.py"
            mock_reg.return_value = {"list_files": mock_entry}

            result = agent.run("list files")

        self.assertEqual(result, "Here are the files.")
        self.assertEqual(agent.llm.chat.call_count, 2)


class MakeFakeToolCallsTests(unittest.TestCase):
    def test_basic(self) -> None:
        raw = [{"name": "read_file", "arguments": '{"file_path": "a.txt"}'}]
        result = _make_fake_tool_calls(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].function.name, "read_file")


class LLMFallbackParseTests(unittest.TestCase):
    """测试 llm.py 中的兼容回退解析。"""

    def test_parse_json_object(self) -> None:
        client = LLMClient.__new__(LLMClient)
        text = '{"name": "read_file", "arguments": {"file_path": "a.txt"}}'
        result = client.try_parse_tool_calls_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["name"], "read_file")  # type: ignore[index]

    def test_parse_json_in_code_fence(self) -> None:
        client = LLMClient.__new__(LLMClient)
        text = '```json\n{"name": "list_files", "arguments": {}}\n```'
        result = client.try_parse_tool_calls_from_text(text)
        self.assertIsNotNone(result)

    def test_parse_plain_text_returns_none(self) -> None:
        client = LLMClient.__new__(LLMClient)
        result = client.try_parse_tool_calls_from_text("I don't know.")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
