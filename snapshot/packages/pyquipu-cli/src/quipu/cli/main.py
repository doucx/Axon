import importlib.metadata
import logging
from typing import Annotated, Optional

import typer
from quipu.common.bus import bus

from .commands import axon, cache, export, navigation, query, remote, run, show, ui, workspace
from .rendering import TyperRenderer

# --- Global Setup ---
# Inject the CLI-specific renderer into the common message bus instance.
# This must be done once at the application's entry point.
bus.set_renderer(TyperRenderer())

# Initialize logger, but handler configuration (stderr or file)
# is determined by specific commands at runtime.
logging.getLogger(__name__)


def version_callback(value: bool):
    if value:
        packages = [
            "pyquipu",
            "pyquipu-application",
            "pyquipu-cli",
            "pyquipu-common",
            "pyquipu-engine",
            "pyquipu-spec",
            "pyquipu-runtime",
        ]
        typer.echo("Quipu 套件版本信息:")
        for pkg in packages:
            try:
                v = importlib.metadata.version(pkg)
                typer.echo(f"  {pkg:20}: {v}")
            except importlib.metadata.PackageNotFoundError:
                typer.echo(f"  {pkg:20}: 未安装")
        raise typer.Exit()


# --- App Definition ---
app = typer.Typer(
    add_completion=False,
    name="quipu",
    help="Quipu: 一个基于 Git 的、用于文件系统状态溯源与文学化操作的工具。",
)

# --- Command Registration ---
# 注册子命令应用
app.add_typer(cache.cache_app)


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="显示版本信息并退出。"),
    ] = None,
):
    """
    Quipu: 一个基于 Git 的、用于文件系统状态溯源与文学化操作的工具。
    """
    pass


# 注册顶级命令
axon.register(app)
workspace.register(app)
navigation.register(app)
query.register(app)
remote.register(app)
run.register(app)
ui.register(app)
show.register(app)
export.register(app)


# --- Entry Point ---
if __name__ == "__main__":
    app()
