from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallResult:
    """记录一次工具调用的完整信息。"""
    tool_call_id: str
    name: str
    arguments: dict[str, Any]
    result: str
    success: bool


@dataclass
class AgentStep:
    """Agent 推理循环中的一步。"""
    step_number: int
    thought: str | None = None
    tool_calls: list[ToolCallResult] = field(default_factory=list)
    final_answer: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def is_final(self) -> bool:
        return self.final_answer is not None
