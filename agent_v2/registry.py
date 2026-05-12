from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------- Type → JSON Schema 映射 ----------

_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}

# 全局工具注册表
_REGISTRY: dict[str, ToolEntry] = {}


@dataclass
class ToolEntry:
    name: str
    handler: Callable[..., str]
    description: str
    confirm: bool
    schema: dict[str, Any]


# ---------- @tool 装饰器 ----------

def tool(*, name: str | None = None, confirm: bool = False):
    """将函数注册为 Agent 可调用工具。"""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        entry = ToolEntry(
            name=name or fn.__name__,
            handler=fn,
            description=_extract_doc(fn),
            confirm=confirm,
            schema=_build_json_schema(fn),
        )
        _REGISTRY[entry.name] = entry
        return fn

    return decorator


def get_registry() -> dict[str, ToolEntry]:
    """返回当前全局注册表的副本。"""
    return dict(_REGISTRY)


def clear_registry() -> None:
    """清空全局注册表（测试用）。"""
    _REGISTRY.clear()


def get_tools_payload() -> list[dict[str, Any]]:
    """生成 OpenAI API 所需的 tools 列表格式。"""
    return [
        {
            "type": "function",
            "function": {
                "name": entry.name,
                "description": entry.description,
                "parameters": entry.schema,
            },
        }
        for entry in _REGISTRY.values()
    ]


# ---------- JSON Schema 生成 ----------

def _build_json_schema(fn: Callable) -> dict[str, Any]:
    """从函数签名和类型注解生成 JSON Schema。"""
    sig = inspect.signature(fn)
    param_docs = _parse_param_docs(fn)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # 跳过内部注入参数
        if param_name == "sandbox":
            continue

        prop: dict[str, Any] = {}
        type_name = _resolve_type_name(param.annotation)
        if type_name in _TYPE_MAP:
            prop["type"] = _TYPE_MAP[type_name]

        if param_name in param_docs:
            prop["description"] = param_docs[param_name]

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _resolve_type_name(annotation: Any) -> str:
    """将类型注解转为字符串名称。"""
    if annotation is inspect.Parameter.empty:
        return "str"
    name = getattr(annotation, "__name__", str(annotation))
    return name


def _extract_doc(fn: Callable) -> str:
    """提取函数文档字符串的第一段（描述部分）。"""
    doc = inspect.getdoc(fn) or ""
    return doc.split("\n\n")[0].strip()


def _parse_param_docs(fn: Callable) -> dict[str, str]:
    """从 docstring 中解析 :param xxx: description 格式的参数说明。"""
    doc = inspect.getdoc(fn) or ""
    result: dict[str, str] = {}
    for match in re.finditer(r":param\s+(\w+)\s*:\s*(.+)", doc):
        result[match.group(1)] = match.group(2).strip()
    return result
