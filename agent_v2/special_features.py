from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .builtins.fs import _render_tree
from .image_generation import generate_image_feedback
from .llm import LLMClient
from .settings import Settings


_IGNORED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}
_KEY_FILENAMES = {
    "README.md",
    "README.txt",
    "README",
    "AGENTS.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "CHANGELOG.md",
}


@dataclass
class ProjectPosterResult:
    prompt: str
    urls: list[str]


def generate_project_poster(project_dir: Path, settings: Settings) -> ProjectPosterResult:
    context = build_project_context(project_dir)
    prompt = generate_project_poster_prompt(context, settings)
    urls = generate_image_feedback(prompt)
    return ProjectPosterResult(prompt=prompt, urls=urls)


def generate_project_poster_prompt(context: str, settings: Settings) -> str:
    llm = LLMClient(settings)
    message = llm.chat([
        {
            "role": "system",
            "content": (
                "你是资深技术品牌视觉总监和文生图提示词工程师。"
                "你的任务是根据项目仓库信息，生成一段可直接交给文生图模型的中文海报 prompt。"
                "只输出 prompt 正文，不要解释、不要 Markdown 代码块。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请阅读下面的项目仓库摘要，为这个项目生成一张“项目介绍海报”的文生图 prompt。\n\n"
                "要求：\n"
                "- prompt 必须细致，能体现项目名称、核心功能、使用场景、技术气质和目标用户。\n"
                "- 海报应是现代软件产品/开发者工具宣传海报，不要做成网页截图或聊天界面截图。\n"
                "- 可以包含少量标题文字区域，但不要要求模型生成大段可读小字。\n"
                "- 描述构图、主视觉、背景、光影、色彩、材质、空间层次、图标/代码/模块等视觉元素。\n"
                "- 生成 16:9 横版海报风格，适合 README 顶部或项目展示页。\n"
                "- 不要虚构与仓库完全无关的功能。\n\n"
                f"项目仓库摘要：\n{context}"
            ),
        },
    ])
    content = (getattr(message, "content", "") or "").strip()
    return _strip_code_fence(content)


def build_project_context(project_dir: Path) -> str:
    root = project_dir.resolve()
    sections = [
        f"项目目录：{root}",
        "目录结构：",
        _render_tree(root, max_depth=4, max_entries=220),
    ]
    for path in _select_key_files(root):
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="replace")
        sections.append(f"\n关键文件：{rel}\n{_trim_text(text)}")
    return "\n".join(sections)


def _select_key_files(root: Path, limit: int = 10) -> list[Path]:
    selected: list[Path] = []
    for name in _KEY_FILENAMES:
        path = root / name
        if path.is_file():
            selected.append(path)
    if len(selected) >= limit:
        return selected[:limit]

    for path in sorted(root.rglob("*"), key=lambda item: (len(item.parts), str(item).lower())):
        if len(selected) >= limit:
            break
        if not path.is_file() or path in selected:
            continue
        if any(part in _IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".md"}:
            continue
        if path.stat().st_size > 80_000:
            continue
        selected.append(path)
    return selected[:limit]


def _trim_text(text: str, limit: int = 5000) -> str:
    compact = text.strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "\n...[截断]"


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped
