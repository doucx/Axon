import click
import typer
from needle.pointer import L
from quipu.common.bus import bus
from quipu.spec.exceptions import OperationCancelledError


def confirmation_handler_for_executor(diff_lines: list[str], prompt: str) -> bool:
    # 原始逻辑是 `char.lower() != "n"`，这相当于默认为 True
    confirmed = prompt_for_confirmation(prompt=prompt, diff_lines=diff_lines, default=True)
    if not confirmed:
        raise OperationCancelledError("User cancelled the operation.")
    # 执行器的处理器不使用布尔返回值，它依赖于异常。
    # 但为保持契约一致性，我们返回 True。
    return True


def prompt_for_confirmation(prompt: str, diff_lines: list[str] | None = None, default: bool = False) -> bool:
    if diff_lines:
        bus.info(L.prompt.ui.diffHeader)
        for line in diff_lines:
            if line.startswith("+"):
                typer.secho(line.strip("\n"), fg=typer.colors.GREEN, err=True)
            elif line.startswith("-"):
                typer.secho(line.strip("\n"), fg=typer.colors.RED, err=True)
            elif line.startswith("^"):
                typer.secho(line.strip("\n"), fg=typer.colors.BLUE, err=True)
            else:
                typer.echo(line.strip("\n"), err=True)
        typer.echo("", err=True)

    prompt_suffix = (
        bus.render_to_string(L.prompt.suffix.yesDefault) if default else bus.render_to_string(L.prompt.suffix.noDefault)
    )
    typer.secho(prompt + prompt_suffix, nl=False, err=True)

    try:
        # click.getchar() 会智能地尝试从 /dev/tty 读取
        char = click.getchar(echo=False)
        click.echo(char, err=True)  # 手动回显到 stderr
    except (OSError, EOFError):
        # 在完全没有 tty 的环境中 (例如 CI runner)，会抛出异常
        bus.info(L.prompt.info.nonInteractive)
        return False  # 非交互式环境应安全失败

    if not char or char == "\r" or char == "\n":
        return default

    if char.lower() == "y":
        return True
    if char.lower() == "n":
        return False

    return default
