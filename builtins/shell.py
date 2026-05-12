import subprocess
from contextvars import ContextVar
from typing import Any

from ..registry import tool
from ..sandbox import PathSandbox

_sandbox: PathSandbox | None = None
_sandbox_var: ContextVar[PathSandbox | None] = ContextVar("agent_v2_shell_sandbox", default=None)


def register(sandbox: PathSandbox) -> None:
    global _sandbox
    _sandbox = sandbox
    _sandbox_var.set(sandbox)


def _get_sandbox() -> PathSandbox:
    sandbox = _sandbox_var.get() or _sandbox
    assert sandbox is not None, "sandbox 未初始化"
    return sandbox


@tool(confirm=True)
def run_command(command: str = "", **kwargs: Any) -> str:
    """在项目目录中执行终端命令。

    :param command: 要执行的 shell 命令
    """
    if not command:
        command = kwargs.get("cmd", "") or kwargs.get("shell", "") or kwargs.get("cmdline", "")
    if not command:
        return "错误：未指定命令"
    sb = _get_sandbox()
    try:
        completed = subprocess.run(
            command,
            cwd=sb.root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return "命令执行超时（60 秒限制）。"

    parts = []
    if completed.stdout and completed.stdout.strip():
        parts.append(completed.stdout.strip())
    if completed.stderr and completed.stderr.strip():
        parts.append(completed.stderr.strip())

    output = "\n".join(parts) if parts else "(无输出)"
    if len(output) > 100000:
        output = output[:100000] + "\n...[截断]"

    return f"exit_code={completed.returncode}\n{output}"
