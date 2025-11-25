### `fix-cli`: 优化破坏性操作的确认流程

#### 目标
改进 `quipu` 中破坏性命令 (`discard`, `checkout`) 的用户确认流程，使其更安全、响应更迅速。
1.  将确认提示的默认选项从 `yes` 更改为 `no`，防止意外操作。
2.  实现单字符确认，用户按下 `n` 后无需再按回车即可立即取消操作。

#### 基本原理
标准 `typer.confirm` 使用行缓冲输入，无法满足“按 `n` 立即退出”的需求。因此，我们将引入 `click` 库 (Typer 的底层依赖) 中的 `click.getchar()` 函数。

1.  在 `packages/quipu-cli/src/quipu/cli/main.py` 中创建一个新的辅助函数，例如 `_prompt_for_confirmation`。
2.  该函数将使用 `click.getchar()` 来捕获用户的单个按键输入。
3.  它会处理 `y/Y` (确认)、`n/N` (取消) 以及回车 (使用默认值) 的逻辑。
4.  在 `discard` 和 `checkout` 命令中，用这个新的自定义函数替换原有的 `typer.confirm` 调用。
5.  如果用户取消操作，我们将使用 `typer.Abort()` 来干净地中止程序执行。

#### 标签
#fix #cli #ux

---

## Script

### Act 1: 在 `main.py` 中实现单字符确认辅助函数

首先，我将 `click` 导入到 `main.py`，并添加新的 `_prompt_for_confirmation` 函数。这个函数将封装单字符输入的逻辑。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
import typer
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional, Dict

from .logger_config import setup_logging
~~~~~

~~~~~python
import typer
import logging
import sys
import click # 导入 click 库
from pathlib import Path
from typing import Annotated, Optional, Dict

from .logger_config import setup_logging
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
# 注意：不要在模块级别直接调用 setup_logging()，
# 否则会导致 CliRunner 测试中的 I/O 流过早绑定/关闭问题。
logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, name="quipu")
~~~~~

~~~~~python
# 注意：不要在模块级别直接调用 setup_logging()，
# 否则会导致 CliRunner 测试中的 I/O 流过早绑定/关闭问题。
logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, name="quipu")

def _prompt_for_confirmation(message: str, default: bool = False) -> bool:
    """
    使用单字符输入请求用户确认，无需回车。
    """
    prompt_suffix = " [Y/n]: " if default else " [y/N]: "
    typer.secho(message + prompt_suffix, nl=False, err=True)
    
    # click.getchar() 不适用于非 TTY 环境 (如 CI/CD 或管道)
    # 在这种情况下，我们回退到 False，强制使用 --force
    if not sys.stdin.isatty():
        typer.echo(" (non-interactive)", err=True)
        return False # 在非交互环境中，安全起见总是拒绝

    char = click.getchar()
    click.echo(char, err=True) # 回显用户输入

    if char.lower() == 'y':
        return True
    if char.lower() == 'n':
        return False
    
    # 对于回车或其他键，返回默认值
    return default
~~~~~

### Act 2: 更新 `discard` 命令以使用新的确认方式

现在，我将修改 `discard` 命令，用我们刚刚创建的函数替换 `typer.confirm`，并设置默认值为 `False`。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    if not force:
        typer.confirm(f"🚨 即将丢弃上述所有变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？", abort=True)
    try:
        engine.checkout(target_tree_hash)
~~~~~

~~~~~python
    if not force:
        prompt = f"🚨 即将丢弃上述所有变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    try:
        engine.checkout(target_tree_hash)
~~~~~

### Act 3: 更新 `checkout` 命令以使用新的确认方式

同样地，我也将 `checkout` 命令中的确认逻辑替换为新的实现。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    if not force:
        typer.confirm(f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？", abort=True)
    try:
        engine.checkout(target_tree_hash)
~~~~~

~~~~~python
    if not force:
        prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    try:
        engine.checkout(target_tree_hash)
~~~~~