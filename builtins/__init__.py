from ..sandbox import PathSandbox
from ..registry import tool
from . import fs, shell


def register_all(sandbox: PathSandbox) -> None:
    """注入沙箱到各工具模块（工具已通过 @tool 装饰器注册）。"""
    fs.register(sandbox)
    shell.register(sandbox)
    # Tests may clear the global registry after module import. Re-registering is
    # idempotent because entries are keyed by tool name.
    tool()(fs.list_files)
    tool()(fs.read_file)
    tool()(fs.write_file)
    tool(confirm=True)(shell.run_command)
