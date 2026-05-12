from pathlib import Path

import click

from .runner import AgentRunner
from .settings import Settings

EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}


@click.command()
@click.argument(
    "project_directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("--model", default=None, help="覆盖 .env 中配置的模型名。")
@click.option("--max-steps", default=999, show_default=True, type=int, help="最大推理步数。")
def main(project_directory: Path, model: str | None, max_steps: int) -> None:
    """启动基于原生 Function Calling 的 ReAct 终端 Agent。"""
    try:
        settings = Settings.from_env(model=model, max_steps=max_steps)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    agent = AgentRunner(settings=settings, project_dir=project_directory)

    click.echo("会话已启动。输入 /exit 或 /quit 退出。")
    click.echo(f"模型：{settings.model}  |  项目：{project_directory}")

    while True:
        try:
            task = click.prompt("\n请输入任务", type=str).strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\n会话结束。")
            break

        if not task:
            continue
        if task.lower() in EXIT_COMMANDS:
            click.echo("会话结束。")
            break

        try:
            answer = agent.run(task)
        except KeyboardInterrupt:
            click.echo("\n当前任务已中断。")
            continue
        except Exception as exc:
            click.echo(f"\n错误：{exc}")
            continue

        click.echo(f"\n最终回答：\n{answer}")
