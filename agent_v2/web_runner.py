from __future__ import annotations

import asyncio
import json
import platform
from pathlib import Path
from string import Template
from typing import Any, AsyncIterator

from .builtins import register_all
from .builtins.fs import _render_tree
from .llm import LLMClient
from .prompt import SYSTEM_PROMPT
from .registry import get_registry, get_tools_payload
from .runner import _make_fake_tool_calls, _strip_tool_calls_from_text
from .sandbox import PathSandbox
from .settings import Settings


class StopRequested(Exception):
    pass


class ConfirmationBroker:
    def __init__(self):
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._counter = 0
        self._lock = asyncio.Lock()

    async def create(self) -> tuple[str, asyncio.Future[bool]]:
        async with self._lock:
            self._counter += 1
            confirmation_id = f"confirm_{self._counter}"
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            self._pending[confirmation_id] = future
            return confirmation_id, future

    def resolve(self, confirmation_id: str, approved: bool) -> bool:
        future = self._pending.pop(confirmation_id, None)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    def cancel_all(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
        self._pending.clear()


class WebAgentRunner:
    """Streaming ReAct runner for the web UI."""

    def __init__(
        self,
        *,
        settings: Settings,
        project_dir: Path,
        confirmation_broker: ConfirmationBroker | None = None,
        stop_event: asyncio.Event | None = None,
        llm: LLMClient | None = None,
    ):
        self.settings = settings
        self.project_dir = project_dir.resolve()
        self.llm = llm or LLMClient(settings)
        self.confirmation_broker = confirmation_broker or ConfirmationBroker()
        self.stop_event = stop_event or asyncio.Event()
        self.sandbox = PathSandbox(self.project_dir)
        self.pending_confirmation_event: dict[str, Any] | None = None
        register_all(self.sandbox)

    async def run(
        self,
        user_input: str,
        history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        messages.extend(_history_to_llm_messages(history or []))
        messages.append({"role": "user", "content": user_input})
        tools_payload = get_tools_payload()

        try:
            for step_num in range(1, self.settings.max_steps + 1):
                self._raise_if_stopped()
                yield {"type": "step", "step": step_num, "message": "正在请求模型..."}

                message = None
                async for event in self._stream_one_message(messages, tools_payload):
                    if event["type"] == "assistant_message":
                        message = event["message"]
                    else:
                        yield {**event, "step": step_num}
                if message is None:
                    yield {"type": "error", "message": "模型没有返回消息。"}
                    return
                self._raise_if_stopped()

                if message.get("content") or message.get("reasoning_content"):
                    yield {
                        "type": "assistant_message_complete",
                        "step": step_num,
                        "content": message.get("content", ""),
                        "reasoning_content": message.get("reasoning_content", ""),
                    }

                if message["tool_calls"]:
                    messages.append(_assistant_tool_message(message))
                    yield {
                        "type": "tool_batch",
                        "step": step_num,
                        "count": len(message["tool_calls"]),
                    }
                    async for event in self._process_tool_calls(step_num, message["tool_calls"], messages):
                        yield event
                    continue

                content = message["content"]
                fallback_calls = self.llm.try_parse_tool_calls_from_text(content)
                if fallback_calls:
                    clean_text = _strip_tool_calls_from_text(content)
                    fake_calls = _make_fake_tool_calls(fallback_calls)
                    messages.append({
                        "role": "assistant",
                        "content": clean_text if clean_text else None,
                        "tool_calls": [
                            {
                                "id": fc.id,
                                "type": "function",
                                "function": {
                                    "name": fc.function.name,
                                    "arguments": fc.function.arguments,
                                },
                            }
                            for fc in fake_calls
                        ],
                    })
                    async for event in self._process_tool_calls(step_num, fake_calls, messages):
                        yield event
                    continue

                yield {
                    "type": "final",
                    "step": step_num,
                    "content": content,
                    "reasoning_content": message.get("reasoning_content", ""),
                }
                return

            yield {
                "type": "error",
                "message": f"超过最大步骤数 {self.settings.max_steps}，任务仍未完成。",
            }
        except StopRequested:
            self.confirmation_broker.cancel_all()
            yield {"type": "stopped", "message": "任务已停止。"}

    async def _stream_one_message(self, messages, tools_payload) -> AsyncIterator[dict[str, Any]]:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        chunk_queue: asyncio.Queue[Any] = asyncio.Queue()
        sentinel = object()
        loop = asyncio.get_running_loop()

        def read_stream() -> None:
            try:
                stream = self.llm.stream_chat(messages, tools_payload)
                for chunk in stream:
                    if self.stop_event.is_set():
                        break
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, sentinel)

        reader_task = asyncio.create_task(asyncio.to_thread(read_stream))
        while True:
            chunk = await chunk_queue.get()
            if chunk is sentinel:
                break
            if isinstance(chunk, Exception):
                raise chunk
            self._raise_if_stopped()
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                text = delta.content or ""
                content_parts.append(text)
                yield {"type": "assistant_delta", "content": text}

            reasoning_content = getattr(delta, "reasoning_content", None)
            if reasoning_content:
                reasoning_parts.append(reasoning_content)
                yield {"type": "reasoning_delta", "content": reasoning_content}

            for tc in getattr(delta, "tool_calls", None) or []:
                idx = int(getattr(tc, "index", 0) or 0)
                current = tool_calls.setdefault(idx, {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                })
                if getattr(tc, "id", None):
                    current["id"] = tc.id
                if getattr(tc, "type", None):
                    current["type"] = tc.type
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        current["function"]["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        current["function"]["arguments"] += fn.arguments

        await reader_task

        yield {
            "type": "assistant_message",
            "message": {
                "content": "".join(content_parts),
                "reasoning_content": "".join(reasoning_parts),
                "tool_calls": [_DictToolCall(tc) for _, tc in sorted(tool_calls.items())],
            },
        }

    async def _process_tool_calls(
        self,
        step_num: int,
        tool_calls: list[Any],
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        for tc in tool_calls:
            self._raise_if_stopped()
            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                func_args = {}

            yield {
                "type": "tool_call",
                "step": step_num,
                "tool_call_id": tc.id,
                "name": func_name,
                "arguments": func_args,
            }
            entry = get_registry().get(func_name)
            if entry is not None and entry.confirm:
                confirmation_id, future = await self.confirmation_broker.create()
                confirmation_event = {
                    "type": "confirmation_required",
                    "confirmation_id": confirmation_id,
                    "step": step_num,
                    "tool_call_id": tc.id,
                    "name": func_name,
                    "arguments": func_args,
                    "project_dir": str(self.project_dir),
                }
                self.pending_confirmation_event = confirmation_event
                yield confirmation_event
                while not future.done():
                    self._raise_if_stopped()
                    await asyncio.sleep(0.05)
                self.pending_confirmation_event = None
                if not future.result():
                    result_str = "用户取消了工具执行。"
                    yield {
                        "type": "tool_result",
                        "step": step_num,
                        "tool_call_id": tc.id,
                        "name": func_name,
                        "arguments": func_args,
                        "result": result_str,
                        "success": False,
                    }
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
                    continue

            result_str = await self._execute_tool(func_name, func_args)
            yield {
                "type": "tool_result",
                "step": step_num,
                "tool_call_id": tc.id,
                "name": func_name,
                "arguments": func_args,
                "result": result_str,
                "success": not result_str.startswith("错误"),
            }
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        entry = get_registry().get(name)
        if entry is None:
            return f"错误：未知工具 {name}"

        try:
            return await asyncio.to_thread(lambda: entry.handler(**args))
        except Exception as exc:
            return f"工具执行错误：{exc}"

    def _build_system_prompt(self) -> str:
        return Template(SYSTEM_PROMPT).substitute(
            tool_list=self._render_tool_list(),
            operating_system=_get_os_name(),
            project_directory=str(self.project_dir),
            file_tree=_render_tree(self.project_dir, max_depth=10, max_entries=1000),
        )

    def _render_tool_list(self) -> str:
        lines = []
        for entry in get_registry().values():
            confirm_tag = " [需确认]" if entry.confirm else ""
            lines.append(f"- {entry.name}{confirm_tag}: {entry.description}")
        return "\n".join(lines)

    def _raise_if_stopped(self) -> None:
        if self.stop_event.is_set():
            raise StopRequested()


class _DictFunction:
    def __init__(self, data: dict[str, Any]):
        self.name = data.get("name", "")
        self.arguments = data.get("arguments", "")


class _DictToolCall:
    def __init__(self, data: dict[str, Any]):
        self.id = data.get("id", "")
        self.function = _DictFunction(data.get("function", {}))


def _assistant_tool_message(message: dict[str, Any]) -> dict[str, Any]:
    assistant_message = {
        "role": "assistant",
        "content": message["content"] or None,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message["tool_calls"]
        ],
    }
    if message.get("reasoning_content"):
        assistant_message["reasoning_content"] = message["reasoning_content"]
    return assistant_message


def _history_to_llm_messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for item in history:
        kind = item.get("type")
        if kind == "user":
            messages.append({"role": "user", "content": item.get("content", "")})
        elif kind == "assistant_final":
            messages.append({"role": "assistant", "content": item.get("content", "")})
    return messages


def _get_os_name() -> str:
    mapping = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}
    return mapping.get(platform.system(), "Unknown")
