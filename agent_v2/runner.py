from __future__ import annotations

import json
import platform
from pathlib import Path
from string import Template
from typing import Any, Callable

from .builtins import register_all
from .builtins.fs import _render_tree
from .llm import LLMClient
from .prompt import SYSTEM_PROMPT
from .protocol import AgentStep, ToolCallResult
from .registry import get_registry, get_tools_payload
from .sandbox import PathSandbox
from .settings import Settings


class AgentRunner:
    """ReAct 推理引擎：基于 OpenAI 原生 function calling 的主循环。"""

    def __init__(
        self,
        *,
        settings: Settings,
        project_dir: Path,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.settings = settings
        self.project_dir = project_dir.resolve()
        self.input_fn = input_fn
        self.output = output_fn
        self.llm = LLMClient(settings)

        sandbox = PathSandbox(self.project_dir)
        register_all(sandbox)

    def run(self, user_input: str) -> str:
        """执行一轮完整的推理循环，返回最终答案。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_input},
        ]
        tools_payload = get_tools_payload()

        for step_num in range(1, self.settings.max_steps + 1):
            self.output(f"\n[步骤 {step_num}] 正在请求模型...")

            # 调试：打印当前消息历史的角色序列
            roles = [m.get("role", "?") for m in messages]
            self.output(f"[调试] 消息历史角色序列: {roles}")
            self.output(f"[调试] 消息历史长度: {len(messages)}")

            message = self.llm.chat(messages, tools_payload)

            # 调试：打印模型返回的原始内容
            self.output(f"[调试] 模型返回 tool_calls: {message.tool_calls is not None and len(message.tool_calls) > 0}")
            self.output(f"[调试] 模型返回 content: {(message.content or '')[:200]}")

            # 情况 1：模型返回了工具调用（原生 function calling）
            if message.tool_calls:
                # assistant 消息（含 tool_calls）直接追加到历史
                messages.append(message.model_dump())
                self.output(f"[步骤 {step_num}] 模型请求调用 {len(message.tool_calls)} 个工具")
                step = self._process_tool_calls(step_num, message.tool_calls, messages)

                if step.is_final:
                    return step.final_answer  # type: ignore[return-value]
                continue

            # 情况 2：模型返回了文本内容
            content = message.content or ""

            # 尝试兼容回退：从文本中解析工具调用（XML 或 JSON 格式）
            fallback_calls = self.llm.try_parse_tool_calls_from_text(content)
            if fallback_calls:
                self.output(f"\n[步骤 {step_num}] 检测到文本格式工具调用，尝试兼容执行...")
                # 从文本中剥离工具调用，保留干净的思考部分
                clean_text = _strip_tool_calls_from_text(content)
                # 构造模拟的 tool_calls 并执行
                fake_calls = _make_fake_tool_calls(fallback_calls)
                # 用标准 tool_calls 格式追加 assistant 消息（与原生调用格式一致）
                assistant_msg: dict[str, Any] = {
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
                }
                messages.append(assistant_msg)
                step = self._process_tool_calls(step_num, fake_calls, messages)

                if step.is_final:
                    return step.final_answer  # type: ignore[return-value]
                continue

            # 情况 3：纯文本回复 → 最终答案
            self.output(f"\n[步骤 {step_num}] 模型回复：{content[:2000]}")
            return content

        raise RuntimeError(f"超过最大步骤数 {self.settings.max_steps}，任务仍未完成。")

    def _process_tool_calls(
        self,
        step_num: int,
        tool_calls: list[Any],
        messages: list[dict[str, Any]],
    ) -> AgentStep:
        """执行一组工具调用，将结果追加到消息历史。"""
        step = AgentStep(step_number=step_num)

        for tc in tool_calls:
            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                func_args = {}

            self.output(f"\n[步骤 {step_num}] 调用工具: {func_name}({func_args})")
            result_str = self._execute_tool(func_name, func_args)
            self.output(f"[步骤 {step_num}] 结果: {result_str[:2000]}")

            step.tool_calls.append(ToolCallResult(
                tool_call_id=tc.id,
                name=func_name,
                arguments=func_args,
                result=result_str,
                success=not result_str.startswith("错误"),
            ))

            # tool 角色消息，通过 tool_call_id 关联
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

        return step

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """查找并执行工具。"""
        registry = get_registry()
        entry = registry.get(name)
        if entry is None:
            return f"错误：未知工具 {name}"

        if entry.confirm:
            try:
                answer = self.input_fn(f"确认执行 {name}？(Y/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return "用户取消了工具执行。"
            if answer not in ("y", "yes"):
                return "用户取消了工具执行。"

        try:
            return entry.handler(**args)
        except Exception as exc:
            return f"工具执行错误：{exc}"

    def _build_system_prompt(self) -> str:
        tool_list = self._render_tool_list()
        file_tree = _render_tree(self.project_dir, max_depth=10, max_entries=1000)

        return Template(SYSTEM_PROMPT).substitute(
            tool_list=tool_list,
            operating_system=_get_os_name(),
            project_directory=str(self.project_dir),
            file_tree=file_tree,
        )

    def _render_tool_list(self) -> str:
        lines = []
        for entry in get_registry().values():
            confirm_tag = " [需确认]" if entry.confirm else ""
            lines.append(f"- {entry.name}{confirm_tag}: {entry.description}")
        return "\n".join(lines)


def _get_os_name() -> str:
    mapping = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}
    return mapping.get(platform.system(), "Unknown")


def _make_fake_tool_calls(raw_calls: list[dict[str, str]]) -> list[Any]:
    """从文本解析的工具调用构造模拟的 tool_calls 对象。"""

    class FakeFunction:
        def __init__(self, name: str, arguments: str):
            self.name = name
            self.arguments = arguments

    class FakeToolCall:
        def __init__(self, name: str, arguments: str, idx: int):
            self.id = f"fallback_call_{idx}"
            self.function = FakeFunction(name, arguments)

    return [FakeToolCall(c["name"], c["arguments"], i) for i, c in enumerate(raw_calls)]


def _strip_tool_calls_from_text(text: str) -> str:
    """从文本中剥离工具调用（各种格式），保留干净的思考部分。"""
    import re
    # 去掉 <function_calls>...</function_calls> 块
    fc_open = chr(60) + "function_calls"
    fc_close = chr(60) + "/function_calls" + chr(62)
    cleaned = re.sub(fc_open + ".*?" + fc_close, "", text, flags=re.DOTALL)
    # 去掉 <invoke>...</invoke> 块
    inv_open = chr(60) + "invoke"
    inv_close = chr(60) + "/invoke" + chr(62)
    cleaned = re.sub(inv_open + r".*?" + inv_close, "", cleaned, flags=re.DOTALL)
    # 去掉自定义工具标签 <tool_name>...</tool_name>
    for name in get_registry().keys():
        open_tag = chr(60) + name + chr(62)
        close_tag = chr(60) + "/" + name + chr(62)
        cleaned = re.sub(open_tag + ".*?" + close_tag, "", cleaned, flags=re.DOTALL)
    # 去掉仅包含单个函数调用的 Python 代码块
    cleaned = re.sub(r"```python\s*\n?\w+\s*\(.*?\)\s*\n?```", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()
