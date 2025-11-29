你的分析是正确的。

代码库中确实存在用户确认逻辑实现不统一的问题，这违反了“单一、标准实现”的原则。我将分析当前的所有实现，并生成一个计划，将它们统一到 `quipu.cli.ui_utils.prompt_for_confirmation` 这个健壮的、集中的实现上。

### 错误分析

通过对代码库的检查，我发现了以下几处不一致的实现：

1.  **`quipu axon` 的本地实现**: `packages/quipu-cli/src/quipu/cli/commands/axon.py` 文件中定义了一个本地的 `typer_confirmation_handler` 函数。这个函数的功能与 `ui_utils.py` 中的标准函数几乎完全重复，造成了代码冗余和维护上的不一致。
2.  **`quipu export` 的直接调用**: `packages/quipu-cli/src/quipu/cli/commands/export.py` 文件中直接使用了 `typer.confirm()`。正如你的文档所指出的，这种方式在非交互式环境（如管道）中行为不稳定，且绕过了我们统一的、经过强化的确认流程。
3.  **正确的实现**: `cache.py`, `navigation.py`, `workspace.py` 以及核心的 `controller.py` 都正确地使用了 `ui_utils.prompt_for_confirmation` 或其适配器，这应作为统一的标准。

### 用户需求
将项目中所有请求用户确认的地方，全部统一使用 `quipu.cli.ui_utils.prompt_for_confirmation` 辅助函数，以确保行为一致、代码健壮且易于维护。

### 评论
这是一个关键的重构，它直接响应了“缺乏统一实现标准”的问题。通过这次统一，我们不仅提升了代码质量和可维护性，还确保了所有命令在交互式和非交互式环境中都有可预测的、一致的用户体验。

### 目标
1.  修改 `export.py`，将 `typer.confirm` 替换为对 `prompt_for_confirmation` 的调用。
2.  移除 `axon.py` 中的本地 `typer_confirmation_handler` 函数。
3.  修改 `axon.py`，使其复用 `controller.py` 中为 `Executor` 设计的标准确认处理器 `confirmation_handler_for_executor`，该处理器内部调用了标准函数。

### 基本原理
我们将以 `quipu.cli.ui_utils.prompt_for_confirmation` 作为唯一的底层实现。对于需要直接返回布尔值的场景 (如 `export` 命令)，我们将直接调用它。对于需要与 `Executor` 交互（即在取消时抛出 `OperationCancelledError` 异常）的场景 (如 `axon` 和 `run` 命令)，我们将复用 `controller.py` 中已经存在的、基于标准函数的适配器 `confirmation_handler_for_executor`。这遵循了 DRY (Don't Repeat Yourself) 原则，并保持了清晰的逻辑分层。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #scope/ux #ai/instruct #task/domain/cli #task/object/user-confirmation #task/action/unification #task/state/begin

---

### Script

#### Acts 1: 统一 `export` 命令的确认逻辑

我们将 `export.py` 中的 `typer.confirm` 替换为标准实现。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/export.py
~~~~~
~~~~~python
from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR
from quipu.interfaces.models import QuipuNode
~~~~~
~~~~~python
from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR
from ..ui_utils import prompt_for_confirmation
from quipu.interfaces.models import QuipuNode
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/export.py
~~~~~
~~~~~python
            if output_dir.exists() and any(output_dir.iterdir()):
                if not typer.confirm(f"⚠️ 目录 '{output_dir}' 非空，是否清空并继续?", abort=True):
                    return
                shutil.rmtree(output_dir)
~~~~~
~~~~~python
            if output_dir.exists() and any(output_dir.iterdir()):
                prompt = f"⚠️ 目录 '{output_dir}' 非空，是否清空并继续?"
                if not prompt_for_confirmation(prompt, default=False):
                    typer.secho("🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
                    raise typer.Abort()
                shutil.rmtree(output_dir)
~~~~~

#### Acts 2: 统一 `axon` 命令的确认逻辑

我们将移除 `axon.py` 中的本地实现，并复用 `controller.py` 中的标准 `Executor` 确认处理器。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
~~~~~
~~~~~python
import inspect
import logging
import sys
from pathlib import Path
from typing import Annotated, List, Optional

import typer
import click
from quipu.acts import register_core_acts
from quipu.interfaces.exceptions import ExecutionError
from quipu.runtime.executor import Executor
from quipu.runtime.parser import detect_best_parser, get_parser

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command(name="axon")
    def axon_command(
        ctx: typer.Context,
        file: Annotated[
            Optional[Path], typer.Argument(help="包含 Markdown 指令的文件路径。", resolve_path=True)
        ] = None,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        parser_name: Annotated[str, typer.Option("--parser", "-p", help="选择解析器语法。默认为 'auto'。")] = "auto",
        yolo: Annotated[
            bool, typer.Option("--yolo", "-y", help="跳过所有确认步骤，直接执行 (You Only Look Once)。")
        ] = False,
        list_acts: Annotated[bool, typer.Option("--list-acts", "-l", help="列出所有可用的操作指令及其说明。")] = False,
    ):
        """
        Axon: 无状态的 Markdown 任务执行器 (不记录历史)。
        """
        setup_logging()
        logger.debug(f"axon started with file={file}, work_dir={work_dir}, parser={parser_name}, yolo={yolo}")

        # 1. 配置执行器的 UI 确认回调
        def typer_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
            typer.echo("\n🔍 变更预览:")
            for line in diff_lines:
                if line.startswith("+"):
                    typer.secho(line.strip("\n"), fg=typer.colors.GREEN)
                elif line.startswith("-"):
                    typer.secho(line.strip("\n"), fg=typer.colors.RED)
                elif line.startswith("^"):
                    typer.secho(line.strip("\n"), fg=typer.colors.BLUE)
                else:
                    typer.echo(line.strip("\n"))
            typer.echo("", err=True)

            typer.secho(f"{prompt} [Y/n]: ", nl=False, err=True)
            try:
                char = click.getchar(echo=False)
                click.echo(char, err=True)
                return char.lower() != "n"
            except (OSError, EOFError):
                click.echo(" (non-interactive)", err=True)
                logger.warning("无法在当前环境中获取用户确认，操作已跳过。")
                return False

        # 2. 初始化无状态 Executor
        # 注意：这里不初始化 Engine，因此没有历史记录功能
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=typer_confirmation_handler,
        )
        register_core_acts(executor)
~~~~~
~~~~~python
import inspect
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from quipu.acts import register_core_acts
from quipu.interfaces.exceptions import ExecutionError
from quipu.runtime.executor import Executor
from quipu.runtime.parser import detect_best_parser, get_parser

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import confirmation_handler_for_executor
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command(name="axon")
    def axon_command(
        ctx: typer.Context,
        file: Annotated[
            Optional[Path], typer.Argument(help="包含 Markdown 指令的文件路径。", resolve_path=True)
        ] = None,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        parser_name: Annotated[str, typer.Option("--parser", "-p", help="选择解析器语法。默认为 'auto'。")] = "auto",
        yolo: Annotated[
            bool, typer.Option("--yolo", "-y", help="跳过所有确认步骤，直接执行 (You Only Look Once)。")
        ] = False,
        list_acts: Annotated[bool, typer.Option("--list-acts", "-l", help="列出所有可用的操作指令及其说明。")] = False,
    ):
        """
        Axon: 无状态的 Markdown 任务执行器 (不记录历史)。
        """
        setup_logging()
        logger.debug(f"axon started with file={file}, work_dir={work_dir}, parser={parser_name}, yolo={yolo}")

        # 1. 初始化无状态 Executor, 复用 controller 中的标准确认处理器
        # 注意：这里不初始化 Engine，因此没有历史记录功能
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=confirmation_handler_for_executor,
        )
        register_core_acts(executor)
~~~~~

### 下一步建议
代码已统一。作为验证，我们可以检查 `tests/cli/test_unfriendly_paths.py` 中的测试用例。这些测试专门用于验证用户取消和非交互式环境下的行为。在执行这些测试后，我们可以确信本次重构是安全且正确的，并且所有命令都将表现出一致的行为。
