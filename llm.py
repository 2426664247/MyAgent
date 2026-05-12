from __future__ import annotations

import ast
import json
import re
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from .registry import get_registry
from .settings import Settings


class LLMClient:
    """封装 OpenAI API 调用，支持原生 function calling 和兼容回退。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)

    def chat(self, messages, tools_payload=None):
        kwargs = {"model": self.settings.model, "messages": messages}
        kwargs.update(self._thinking_kwargs())
        if tools_payload:
            kwargs["tools"] = tools_payload
            kwargs["tool_choice"] = "auto"
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

    def stream_chat(self, messages, tools_payload=None):
        kwargs = {"model": self.settings.model, "messages": messages, "stream": True}
        kwargs.update(self._thinking_kwargs())
        if tools_payload:
            kwargs["tools"] = tools_payload
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def _thinking_kwargs(self) -> dict[str, Any]:
        if not _is_deepseek_endpoint(self.settings.model, self.settings.base_url):
            return {}
        thinking_type = "enabled" if self.settings.thinking_enabled else "disabled"
        kwargs: dict[str, Any] = {"extra_body": {"thinking": {"type": thinking_type}}}
        if self.settings.thinking_enabled:
            kwargs["reasoning_effort"] = "high"
        return kwargs

    def try_parse_tool_calls_from_text(self, text):
        """尝试从文本中解析工具调用，按优先级尝试多种格式。"""
        for parser in [
            self._parse_function_calls_block,
            self._parse_invoke_block,
            self._parse_custom_tag,
            self._parse_json,
            self._parse_python_call,
        ]:
            result = parser(text)
            if result:
                return result
        return None

    def _parse_function_calls_block(self, text):
        """格式: function_calls 块"""
        open_tag = chr(60) + "function_calls" + chr(62)
        close_tag = chr(60) + "/function_calls" + chr(62)
        block = re.search(open_tag + "(.*?)" + close_tag, text, re.DOTALL)
        if not block:
            return None
        results = []
        fc_open = chr(60) + "function_call"
        fc_end = "/" + chr(62)
        for m in re.finditer(
            fc_open + r'\s+name="([^"]+)"\s+arguments=(.*?)\s*' + fc_end,
            block.group(1), re.DOTALL,
        ):
            name = m.group(1)
            try:
                args = json.dumps(json.loads(m.group(2).strip()))
            except (json.JSONDecodeError, TypeError):
                args = json.dumps({})
            results.append({"name": name, "arguments": args})
        return results or None

    def _parse_invoke_block(self, text):
        """格式: invoke 块 (Anthropic 风格)"""
        inv_open = chr(60) + "invoke"
        inv_close = chr(60) + "/invoke" + chr(62)
        param_open = chr(60) + "parameter"
        param_close = chr(60) + "/parameter" + chr(62)
        results = []
        for block in re.finditer(
            inv_open + r'\s+name="([^"]+)">(.*?)' + inv_close, text, re.DOTALL
        ):
            name = block.group(1)
            inner = block.group(2)
            args = {}
            for p in re.finditer(
                param_open + r'\s+name="([^"]+)">(.*?)' + param_close, inner, re.DOTALL
            ):
                args[p.group(1)] = p.group(2).strip()
            results.append({"name": name, "arguments": json.dumps(args)})
        return results or None

    def _parse_custom_tag(self, text):
        """格式: 自定义标签 (标签名=已注册工具名)"""
        tool_names = set(get_registry().keys())
        if not tool_names:
            return None
        results = []
        for name in tool_names:
            open_tag = chr(60) + name + chr(62)
            close_tag = chr(60) + "/" + name + chr(62)
            pattern = re.compile(open_tag + r"\s*(.*?)\s*" + close_tag, re.DOTALL)
            for m in pattern.finditer(text):
                inner = m.group(1)
                args = {}
                t_open = chr(60)
                t_close = chr(62)
                for tm in re.finditer(
                    t_open + r"(\w+)" + t_close + r"(.*?)" + t_open + r"/\1" + t_close,
                    inner, re.DOTALL,
                ):
                    args[tm.group(1)] = self._coerce(tm.group(2).strip())
                results.append({"name": name, "arguments": json.dumps(args)})
        return results or None

    def _parse_json(self, text):
        """格式: JSON"""
        json_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        raw = json_match.group(1).strip() if json_match else text.strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return [{"name": data["name"], "arguments": json.dumps(data["arguments"])}]
            if isinstance(data, list):
                results = []
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        results.append({"name": item["name"], "arguments": json.dumps(item.get("arguments", {}))})
                return results or None
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def _parse_python_call(self, text):
        """格式: Python 代码块中的函数调用"""
        code_blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
        if not code_blocks:
            code_blocks = [text]
        results = []
        call_pattern = re.compile(r"(\w+)\s*\((.*?)\)\s*$", re.MULTILINE | re.DOTALL)
        skip = {"print", "len", "str", "int", "float", "list", "dict", "set", "type"}
        for block in code_blocks:
            for m in call_pattern.finditer(block):
                name = m.group(1)
                if name in skip:
                    continue
                args = self._parse_py_args(m.group(2).strip())
                results.append({"name": name, "arguments": json.dumps(args)})
        return results or None

    def _parse_py_args(self, args_str):
        """解析 Python 函数调用的参数。"""
        if not args_str:
            return {}
        try:
            tree = ast.parse(f"f({args_str})", mode="eval")
            call = tree.body
            result = {}
            for kw in call.keywords:
                try:
                    result[kw.arg] = ast.literal_eval(kw.value)
                except (ValueError, TypeError):
                    if isinstance(kw.value, ast.Constant):
                        result[kw.arg] = kw.value.value
            if not result and call.args:
                for arg in call.args:
                    try:
                        val = ast.literal_eval(arg)
                        if isinstance(val, str):
                            result["file_path"] = val
                    except (ValueError, TypeError):
                        pass
            return result
        except SyntaxError:
            return {}

    @staticmethod
    def _coerce(val):
        """尝试将字符串值转为合适的 Python 类型。"""
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        try:
            return int(val)
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            pass
        return val


def _is_deepseek_endpoint(model: str, base_url: str | None) -> bool:
    return model.startswith("deepseek-") or bool(base_url and "deepseek.com" in base_url.lower())
