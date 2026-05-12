from pathlib import Path
from contextvars import ContextVar
from typing import Any

from ..registry import tool
from ..sandbox import PathSandbox

_IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}

# 模块级 sandbox 引用，由 register() 设置
_sandbox: PathSandbox | None = None
_sandbox_var: ContextVar[PathSandbox | None] = ContextVar("agent_v2_fs_sandbox", default=None)


def register(sandbox: PathSandbox) -> None:
    global _sandbox
    _sandbox = sandbox
    _sandbox_var.set(sandbox)


def _get_sandbox() -> PathSandbox:
    sandbox = _sandbox_var.get() or _sandbox
    assert sandbox is not None, "sandbox 未初始化"
    return sandbox


@tool()
def list_files() -> str:
    """列出项目目录的树状结构，帮助了解项目范围。"""
    sb = _get_sandbox()
    return _render_tree(sb.root, max_depth=10, max_entries=1000)


@tool()
def read_file(file_path: str = "", max_lines: int = 10000, **kwargs: Any) -> str:
    """读取项目目录中的文本文件内容。

    :param file_path: 要读取的文件路径（绝对或相对项目目录）
    :param max_lines: 最多读取的行数，默认 300
    """
    # 兼容模型使用不同参数名的情况
    if not file_path:
        file_path = kwargs.get("path", "") or kwargs.get("directory", "") or kwargs.get("file", "")
    if not file_path:
        return "错误：未指定文件路径"
    sb = _get_sandbox()
    path = sb.resolve(file_path)

    if not path.exists():
        return f"错误：文件不存在 {path}"
    if not path.is_file():
        return f"错误：不是文件 {path}"

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    if len(lines) <= max_lines:
        return "".join(lines)

    head = "".join(lines[:max_lines])
    return f"{head}\n...[截断：共 {len(lines)} 行，仅显示前 {max_lines} 行]"


@tool()
def write_file(file_path: str = "", content: str = "", **kwargs: Any) -> str:
    """将文本内容写入项目目录内的文件，不存在时自动创建父目录。

    :param file_path: 要写入的文件路径（绝对或相对项目目录）
    :param content: 要写入的文本内容
    """
    if not file_path:
        file_path = kwargs.get("path", "") or kwargs.get("directory", "") or kwargs.get("file", "")
    if not file_path:
        return "错误：未指定文件路径"
    sb = _get_sandbox()
    path = sb.resolve(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = content.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    path.write_text(normalized, encoding="utf-8")
    return f"写入成功：{path}"


def _render_tree(root: Path, *, max_depth: int, max_entries: int) -> str:
    root = root.resolve()
    lines: list[str] = [f"{root.name}/"]
    counter = [0]
    truncated = [False]

    def walk(current: Path, depth: int) -> None:
        if depth > max_depth or truncated[0]:
            return

        entries = sorted(
            (e for e in current.iterdir() if e.name not in _IGNORED),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
        for entry in entries:
            if counter[0] >= max_entries:
                truncated[0] = True
                return
            prefix = "  " * depth
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}- {entry.name}{suffix}")
            counter[0] += 1
            if entry.is_dir():
                walk(entry, depth + 1)

    walk(root, 1)
    if truncated[0]:
        lines.append("  ...")
    return "\n".join(lines)
