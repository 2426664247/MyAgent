from pathlib import Path
import re


class PathSandbox:
    """限制所有文件操作在指定根目录内，防止路径逃逸。"""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def resolve(self, path_str: str) -> Path:
        if re.match(r"^[A-Za-z]:[\\/]", path_str):
            raise ValueError(f"路径 {path_str} 超出项目目录范围。")

        candidate = Path(path_str).expanduser()
        if not candidate.is_absolute():
            candidate = (self.root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise ValueError(f"路径 {path_str} 超出项目目录范围。")

        return candidate
