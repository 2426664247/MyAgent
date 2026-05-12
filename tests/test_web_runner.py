import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent_v2.registry import clear_registry, tool
from agent_v2.settings import Settings
from agent_v2.web_runner import ConfirmationBroker, WebAgentRunner


class FakeLLM:
    def __init__(self, messages):
        self.messages = messages

    def stream_chat(self, _messages, _tools_payload):
        return iter(self.messages.pop(0))

    def try_parse_tool_calls_from_text(self, _text):
        return None


def chunk(*, content=None, reasoning_content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    reasoning_content=reasoning_content,
                    tool_calls=tool_calls or [],
                )
            )
        ]
    )


def tool_delta(index, call_id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class WebRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_registry()
        self.tmp = Path(tempfile.mkdtemp())
        self.settings = Settings(model="test", api_key="k", base_url=None, max_steps=3)

    def tearDown(self) -> None:
        clear_registry()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stream_direct_answer(self) -> None:
        llm = FakeLLM([[chunk(content="hi"), chunk(content=" there")]])
        runner = WebAgentRunner(settings=self.settings, project_dir=self.tmp, llm=llm)

        events = asyncio.run(_collect(runner.run("hello")))

        self.assertEqual([e["type"] for e in events], [
            "step",
            "assistant_delta",
            "assistant_delta",
            "assistant_message_complete",
            "final",
        ])
        self.assertEqual(events[-1]["content"], "hi there")
        self.assertEqual(events[-2]["content"], "hi there")

    def test_stream_reasoning_content(self) -> None:
        llm = FakeLLM([[chunk(reasoning_content="thinking"), chunk(content="answer")]])
        runner = WebAgentRunner(settings=self.settings, project_dir=self.tmp, llm=llm)

        events = asyncio.run(_collect(runner.run("hello")))

        self.assertEqual([e["type"] for e in events], [
            "step",
            "reasoning_delta",
            "assistant_delta",
            "assistant_message_complete",
            "final",
        ])
        self.assertEqual(events[-1]["reasoning_content"], "thinking")
        self.assertEqual(events[-2]["reasoning_content"], "thinking")

    def test_confirmation_flow(self) -> None:
        @tool(confirm=True)
        def danger(command: str) -> str:
            """Danger tool."""
            return f"ran {command}"

        args = json.dumps({"command": "echo ok"})
        llm = FakeLLM([
            [
                chunk(tool_calls=[
                    tool_delta(0, call_id="call_1", name="danger", arguments=args)
                ])
            ],
            [chunk(content="done")],
        ])
        broker = ConfirmationBroker()
        runner = WebAgentRunner(
            settings=self.settings,
            project_dir=self.tmp,
            confirmation_broker=broker,
            llm=llm,
        )

        async def scenario():
            events = []
            async for event in runner.run("run"):
                events.append(event)
                if event["type"] == "confirmation_required":
                    self.assertTrue(broker.resolve(event["confirmation_id"], True))
            return events

        events = asyncio.run(scenario())
        types = [e["type"] for e in events]
        self.assertIn("confirmation_required", types)
        self.assertIn("tool_result", types)
        self.assertEqual(events[-1]["content"], "done")

    def test_stop_flow(self) -> None:
        stop_event = asyncio.Event()
        llm = FakeLLM([[chunk(content="partial")]])
        runner = WebAgentRunner(
            settings=self.settings,
            project_dir=self.tmp,
            stop_event=stop_event,
            llm=llm,
        )

        async def scenario():
            events = []
            async for event in runner.run("hello"):
                events.append(event)
                stop_event.set()
            return events

        events = asyncio.run(scenario())
        self.assertEqual(events[-1]["type"], "stopped")


async def _collect(source):
    return [event async for event in source]


if __name__ == "__main__":
    unittest.main()
