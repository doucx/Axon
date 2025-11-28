好的，我将执行这项重构任务。

这个重构分为两个主要部分：
1.  **CLI 命令拆分**：将 `main.py` 中的命令逻辑分解到 `quipu.cli.commands` 子模块中，使 `main.py` 成为一个清晰的命令注册中心。
2.  **TUI 状态管理重构**：将 TUI 的状态逻辑从 `tui.py` (视图层) 移动到 `view_model.py` (视图模型层)，实现更好的关注点分离。

## refactor: 将 CLI 命令拆分到子模块并重构 TUI 状态管理

### 用户需求
根据改进建议，需要对 `quipu-cli` 包进行两项重构：
1.  `main.py` 文件过于庞大，包含了所有 CLI 命令的实现，难以维护。需要将其中的命令逻辑按功能拆分到 `commands` 子包下的不同模块中。
2.  `tui.py` 中的 `QuipuUiApp` 类承担了过多的状态管理职责，与视图渲染逻辑耦合过紧。需要将这些状态（如可见性切换、节点选择）及其管理逻辑转移到 `GraphViewModel` 中，让 `App` 类更专注于处理 UI 事件和渲染。

### 评论
这是一个重要的健康度重构。拆分 CLI 命令可以提高代码的可读性和模块化程度，方便未来新增或修改命令。重构 TUI 状态管理是 UI 开发的最佳实践，能显著降低 UI 的复杂性，使其更易于测试和维护。

### 目标
1.  创建一个新的 `packages/quipu-cli/src/quipu/cli/commands` 目录。
2.  将 `main.py` 中的命令逻辑按功能（如 `workspace`, `navigation`, `query` 等）移动到新目录下的多个 Python 文件中。
3.  创建一个 `helpers.py` 模块，用于存放被多个命令共享的辅助函数。
4.  重写 `main.py`，使其只负责初始化 `Typer` 应用并注册来自各个子模块的命令。
5.  扩展 `GraphViewModel` 的功能，使其管理 TUI 的大部分状态。
6.  修改 `QuipuUiApp`，将状态管理委托给 `GraphViewModel`，简化其内部逻辑。

### 基本原理
-   **模块化**：通过将相关功能组织在独立的模块中，降低耦合度，提升代码内聚性。遵循“高内聚，低耦合”的设计原则。
-   **MVVM (Model-View-ViewModel)**：在 TUI 重构中，我们强化了 MVVM 模式。`Engine` 是 Model，`QuipuUiApp` 是 View，`GraphViewModel` 是 ViewModel。ViewModel 负责从 Model 获取数据，并将其处理成 View 可以直接使用的格式和状态，从而将 View 从业务逻辑中解放出来。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/refactor #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建新的 CLI 命令目录结构

首先，我们创建 `commands` 子包和其中的模块文件。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/quipu-cli/src/quipu/cli/commands
touch packages/quipu-cli/src/quipu/cli/commands/__init__.py
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/helpers.py
~~~~~
~~~~~python
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional

import click
import typer
from quipu.core.models import QuipuNode
from quipu.core.state_machine import Engine

from ..factory import create_engine
from ..logger_config import setup_logging


@contextmanager
def engine_context(work_dir: Path) -> Generator[Engine, None, None]:
    """Context manager to set up logging, create, and automatically close a Quipu engine."""
    setup_logging()
    engine = None
    try:
        engine = create_engine(work_dir)
        yield engine
    finally:
        if engine:
            engine.close()


def _prompt_for_confirmation(message: str, default: bool = False) -> bool:
    """
    使用单字符输入请求用户确认，无需回车。
    """
    prompt_suffix = " [Y/n]: " if default else " [y/N]: "
    typer.secho(message + prompt_suffix, nl=False, err=True)

    if not sys.stdin.isatty():
        typer.echo(" (non-interactive)", err=True)
        return False

    char = click.getchar()
    click.echo(char, err=True)

    if char.lower() == "y":
        return True
    if char.lower() == "n":
        return False

    return default


def _find_current_node(engine: Engine, graph: Dict[str, QuipuNode]) -> Optional[QuipuNode]:
    """在图中查找与当前工作区状态匹配的节点"""
    current_hash = engine.git_db.get_tree_hash()
    # 修复：直接从 graph 中通过 output_tree hash 查找
    for node in graph.values():
        if node.output_tree == current_hash:
            return node

    typer.secho("⚠️  当前工作区状态未在历史中找到，或存在未保存的变更。", fg=typer.colors.YELLOW, err=True)
    typer.secho("💡  请先运行 'quipu save' 创建一个快照，再进行导航。", fg=typer.colors.YELLOW, err=True)
    return None


def _execute_visit(ctx: typer.Context, engine: Engine, target_hash: str, description: str):
    """辅助函数：执行 engine.visit 并处理结果"""
    typer.secho(f"🚀 {description}", err=True)
    try:
        engine.visit(target_hash)
        typer.secho(f"✅ 已成功切换到状态 {target_hash[:7]}。", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        typer.secho(f"❌ 导航操作失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/workspace.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Annotated, Optional

import typer

from .helpers import engine_context, _prompt_for_confirmation
from ..config import DEFAULT_WORK_DIR


def register(app: typer.Typer):
    @app.command()
    def save(
        ctx: typer.Context,
        message: Annotated[Optional[str], typer.Argument(help="本次快照的简短描述。")] = None,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
    ):
        """
        捕获当前工作区的状态，创建一个“微提交”快照。
        """
        with engine_context(work_dir) as engine:
            current_tree_hash = engine.git_db.get_tree_hash()
            is_node_clean = (engine.current_node is not None) and (engine.current_node.output_tree == current_tree_hash)
            EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
            is_genesis_clean = (not engine.history_graph) and (current_tree_hash == EMPTY_TREE_HASH)

            if is_node_clean or is_genesis_clean:
                typer.secho("✅ 工作区状态未发生变化，无需创建快照。", fg=typer.colors.GREEN, err=True)
                ctx.exit(0)

            try:
                node = engine.capture_drift(current_tree_hash, message=message)
                msg_suffix = f" ({message})" if message else ""
                typer.secho(f"📸 快照已保存: {node.short_hash}{msg_suffix}", fg=typer.colors.GREEN, err=True)
            except Exception as e:
                typer.secho(f"❌ 创建快照失败: {e}", fg=typer.colors.RED, err=True)
                ctx.exit(1)

    @app.command()
    def discard(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        force: Annotated[bool, typer.Option("--force", "-f", help="强制执行，跳过确认提示。")] = False,
    ):
        """
        丢弃工作区所有未记录的变更，恢复到上一个干净状态。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph
            if not graph:
                typer.secho("❌ 错误: 找不到任何历史记录，无法确定要恢复到哪个状态。", fg=typer.colors.RED, err=True)
                ctx.exit(1)

            target_tree_hash = engine._read_head()
            if not target_tree_hash or target_tree_hash not in graph:
                latest_node = max(graph.values(), key=lambda n: n.timestamp)
                target_tree_hash = latest_node.output_tree
                typer.secho(
                    f"⚠️  HEAD 指针丢失或无效，将恢复到最新历史节点: {latest_node.short_hash}",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
            else:
                latest_node = graph[target_tree_hash]

            current_hash = engine.git_db.get_tree_hash()
            if current_hash == target_tree_hash:
                typer.secho(f"✅ 工作区已经是干净状态 ({latest_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
                ctx.exit(0)

            diff_stat = engine.git_db.get_diff_stat(target_tree_hash, current_hash)
            typer.secho("\n以下是即将被丢弃的变更:", fg=typer.colors.YELLOW, err=True)
            typer.secho("-" * 20, err=True)
            typer.echo(diff_stat, err=True)
            typer.secho("-" * 20, err=True)

            if not force:
                prompt = f"🚨 即将丢弃上述所有变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？"
                if not _prompt_for_confirmation(prompt, default=False):
                    typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
                    raise typer.Abort()

            try:
                engine.visit(target_tree_hash)
                typer.secho(f"✅ 工作区已成功恢复到节点 {latest_node.short_hash}。", fg=typer.colors.GREEN, err=True)
            except Exception as e:
                typer.secho(f"❌ 恢复状态失败: {e}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/navigation.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Annotated

import typer

from .helpers import engine_context, _find_current_node, _execute_visit
from ..config import DEFAULT_WORK_DIR


def register(app: typer.Typer):
    @app.command()
    def checkout(
        ctx: typer.Context,
        hash_prefix: Annotated[str, typer.Argument(help="目标状态节点 output_tree 的哈希前缀。")],
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        force: Annotated[bool, typer.Option("--force", "-f", help="强制执行，跳过确认提示。")] = False,
    ):
        """
        将工作区恢复到指定的历史节点状态。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph

            matches = [node for output_tree, node in graph.items() if output_tree.startswith(hash_prefix)]
            if not matches:
                typer.secho(
                    f"❌ 错误: 未找到 output_tree 哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True
                )
                ctx.exit(1)
            if len(matches) > 1:
                typer.secho(
                    f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。", fg=typer.colors.RED, err=True
                )
                ctx.exit(1)
            target_node = matches[0]
            target_output_tree_hash = target_node.output_tree

            current_hash = engine.git_db.get_tree_hash()
            if current_hash == target_output_tree_hash:
                typer.secho(f"✅ 工作区已处于目标状态 ({target_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
                ctx.exit(0)

            is_dirty = engine.current_node is None or engine.current_node.output_tree != current_hash
            if is_dirty:
                typer.secho("⚠️  检测到当前工作区存在未记录的变更，将自动创建捕获节点...", fg=typer.colors.YELLOW, err=True)
                engine.capture_drift(current_hash)
                typer.secho("✅ 变更已捕获。", fg=typer.colors.GREEN, err=True)
                current_hash = engine.git_db.get_tree_hash()

            diff_stat = engine.git_db.get_diff_stat(current_hash, target_output_tree_hash)
            if diff_stat:
                typer.secho("\n以下是将要发生的变更:", fg=typer.colors.YELLOW, err=True)
                typer.secho("-" * 20, err=True)
                typer.echo(diff_stat, err=True)
                typer.secho("-" * 20, err=True)

            if not force:
                prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
                if not typer.confirm(prompt, default=False):
                    typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
                    raise typer.Abort()

            _execute_visit(ctx, engine, target_output_tree_hash, f"正在导航到节点: {target_node.short_hash}")

    @app.command()
    def undo(
        ctx: typer.Context,
        count: Annotated[int, typer.Option("--count", "-n", help="向上移动的步数。")] = 1,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [结构化导航] 向上移动到当前状态的父节点。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph
            current_node = _find_current_node(engine, graph)
            if not current_node:
                ctx.exit(1)
            target_node = current_node
            for i in range(count):
                if not target_node.parent:
                    msg = f"已到达历史根节点 (移动了 {i} 步)。" if i > 0 else "已在历史根节点。"
                    typer.secho(f"✅ {msg}", fg=typer.colors.GREEN, err=True)
                    if target_node == current_node:
                        ctx.exit(0)
                    break
                target_node = target_node.parent

            _execute_visit(ctx, engine, target_node.output_tree, f"正在撤销到父节点: {target_node.short_hash}")

    @app.command()
    def redo(
        ctx: typer.Context,
        count: Annotated[int, typer.Option("--count", "-n", help="向下移动的步数。")] = 1,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [结构化导航] 向下移动到子节点 (默认最新)。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph
            current_node = _find_current_node(engine, graph)
            if not current_node:
                ctx.exit(1)
            target_node = current_node
            for i in range(count):
                if not target_node.children:
                    msg = f"已到达分支末端 (移动了 {i} 步)。" if i > 0 else "已在分支末端。"
                    typer.secho(f"✅ {msg}", fg=typer.colors.GREEN, err=True)
                    if target_node == current_node:
                        ctx.exit(0)
                    break
                target_node = target_node.children[-1]
                if len(current_node.children) > 1:
                    typer.secho(
                        f"💡 当前节点有多个分支，已自动选择最新分支 -> {target_node.short_hash}",
                        fg=typer.colors.YELLOW,
                        err=True,
                    )

            _execute_visit(ctx, engine, target_node.output_tree, f"正在重做到子节点: {target_node.short_hash}")

    @app.command()
    def prev(
        ctx: typer.Context,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [结构化导航] 切换到上一个兄弟分支。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph
            current_node = _find_current_node(engine, graph)
            if not current_node:
                ctx.exit(1)
            siblings = current_node.siblings
            if len(siblings) <= 1:
                typer.secho("✅ 当前节点没有兄弟分支。", fg=typer.colors.GREEN, err=True)
                ctx.exit(0)
            try:
                idx = siblings.index(current_node)
                if idx == 0:
                    typer.secho("✅ 已在最旧的兄弟分支。", fg=typer.colors.GREEN, err=True)
                    ctx.exit(0)
                target_node = siblings[idx - 1]
                _execute_visit(ctx, engine, target_node.output_tree, f"正在切换到上一个兄弟节点: {target_node.short_hash}")
            except ValueError:
                pass

    @app.command()
    def next(
        ctx: typer.Context,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [结构化导航] 切换到下一个兄弟分支。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph
            current_node = _find_current_node(engine, graph)
            if not current_node:
                ctx.exit(1)
            siblings = current_node.siblings
            if len(siblings) <= 1:
                typer.secho("✅ 当前节点没有兄弟分支。", fg=typer.colors.GREEN, err=True)
                ctx.exit(0)
            try:
                idx = siblings.index(current_node)
                if idx == len(siblings) - 1:
                    typer.secho("✅ 已在最新的兄弟分支。", fg=typer.colors.GREEN, err=True)
                    ctx.exit(0)
                target_node = siblings[idx + 1]
                _execute_visit(ctx, engine, target_node.output_tree, f"正在切换到下一个兄弟节点: {target_node.short_hash}")
            except ValueError:
                pass

    @app.command()
    def back(
        ctx: typer.Context,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [时序性导航] 后退：回到上一次访问的历史状态。
        """
        with engine_context(work_dir) as engine:
            try:
                result_hash = engine.back()
                if result_hash:
                    typer.secho(f"✅ 已后退到状态: {result_hash[:7]}", fg=typer.colors.GREEN, err=True)
                else:
                    typer.secho("⚠️  已到达访问历史的起点。", fg=typer.colors.YELLOW, err=True)
            except Exception as e:
                typer.secho(f"❌ 后退操作失败: {e}", fg=typer.colors.RED, err=True)
                ctx.exit(1)

    @app.command()
    def forward(
        ctx: typer.Context,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        [时序性导航] 前进：撤销后退操作。
        """
        with engine_context(work_dir) as engine:
            try:
                result_hash = engine.forward()
                if result_hash:
                    typer.secho(f"✅ 已前进到状态: {result_hash[:7]}", fg=typer.colors.GREEN, err=True)
                else:
                    typer.secho("⚠️  已到达访问历史的终点。", fg=typer.colors.YELLOW, err=True)
            except Exception as e:
                typer.secho(f"❌ 前进操作失败: {e}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/query.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Annotated, Optional

import typer

from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR


def register(app: typer.Typer):
    @app.command()
    def log(
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
    ):
        """
        显示 Quipu 历史图谱日志。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph

            if not graph:
                typer.secho("📜 历史记录为空。", fg=typer.colors.YELLOW, err=True)
                raise typer.Exit(0)
            nodes = sorted(graph.values(), key=lambda n: n.timestamp, reverse=True)
            typer.secho("--- Quipu History Log ---", bold=True, err=True)
            for node in nodes:
                ts = node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                color = typer.colors.CYAN if node.node_type == "plan" else typer.colors.MAGENTA
                tag = f"[{node.node_type.upper()}]"
                summary = node.summary
                typer.secho(f"{ts} {tag:<9} {node.short_hash}", fg=color, nl=False, err=True)
                typer.echo(f" - {summary}", err=True)

    @app.command(name="find")
    def find_command(
        ctx: typer.Context,
        summary_regex: Annotated[
            Optional[str], typer.Option("--summary", "-s", help="用于匹配节点摘要的正则表达式 (不区分大小写)。")
        ] = None,
        node_type: Annotated[Optional[str], typer.Option("--type", "-t", help="节点类型 ('plan' 或 'capture')。")] = None,
        limit: Annotated[int, typer.Option("--limit", "-n", help="返回的最大结果数量。")] = 10,
        work_dir: Annotated[Path, typer.Option("--work-dir", "-w", help="工作区根目录。")] = DEFAULT_WORK_DIR,
    ):
        """
        根据条件查找历史节点。
        """
        with engine_context(work_dir) as engine:
            if not engine.history_graph:
                typer.secho("📜 历史记录为空。", fg=typer.colors.YELLOW, err=True)
                ctx.exit(0)

            nodes = engine.find_nodes(summary_regex=summary_regex, node_type=node_type, limit=limit)

            if not nodes:
                typer.secho("🤷 未找到符合条件的历史节点。", fg=typer.colors.YELLOW, err=True)
                ctx.exit(0)

            typer.secho("--- 查找结果 ---", bold=True, err=True)
            for node in nodes:
                ts = node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                color = typer.colors.CYAN if node.node_type == "plan" else typer.colors.MAGENTA
                tag = f"[{node.node_type.upper()}]"
                typer.secho(f"{ts} {tag:<9} {node.output_tree}", fg=color, nl=False, err=True)
                typer.echo(f" - {node.summary}", err=True)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/remote.py
~~~~~
~~~~~python
import subprocess
from pathlib import Path
from typing import Annotated, Optional

import typer
from quipu.common.identity import get_user_id_from_email
from quipu.core.config import ConfigManager
from quipu.core.git_db import GitDB

from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..utils import find_git_repository_root


def register(app: typer.Typer):
    @app.command()
    def sync(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        remote_option: Annotated[Optional[str], typer.Option("--remote", "-r", help="Git 远程仓库的名称 (覆盖配置文件)。")] = None,
    ):
        """
        与远程仓库同步 Quipu 历史图谱。
        """
        setup_logging()
        sync_dir = find_git_repository_root(work_dir) or work_dir
        config = ConfigManager(sync_dir)
        remote = remote_option or config.get("sync.remote_name", "origin")

        final_user_id = config.get("sync.user_id")
        if not final_user_id:
            typer.secho("🤝 首次使用 sync 功能，正在自动配置用户身份...", fg=typer.colors.BLUE, err=True)
            try:
                result = subprocess.run(
                    ["git", "config", "user.email"], cwd=sync_dir, capture_output=True, text=True, check=True
                )
                email = result.stdout.strip()
                if not email:
                    raise ValueError("Git user.email is empty.")

                final_user_id = get_user_id_from_email(email)
                config.set("sync.user_id", final_user_id)
                config.save()
                typer.secho(
                    f"✅ 已根据你的 Git 邮箱 '{email}' 生成并保存用户 ID: {final_user_id}", fg=typer.colors.GREEN, err=True
                )

            except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
                typer.secho("❌ 错误：无法获取你的 Git 用户邮箱。", fg=typer.colors.RED, err=True)
                typer.secho("💡 请先运行以下命令进行设置:", fg=typer.colors.YELLOW, err=True)
                typer.echo("  git config --global user.email \"you@example.com\"")
                ctx.exit(1)

        try:
            git_db = GitDB(sync_dir)

            typer.secho(f"⬆️  正在向 '{remote}' 推送你的本地历史...", fg=typer.colors.BLUE, err=True)
            git_db.push_quipu_refs(remote, final_user_id)

            subscriptions = config.get("sync.subscriptions", [])
            target_ids_to_fetch = set(subscriptions)
            target_ids_to_fetch.add(final_user_id)

            if target_ids_to_fetch:
                typer.secho(
                    f"⬇️  正在从 '{remote}' 拉取 {len(target_ids_to_fetch)} 个用户的历史...", fg=typer.colors.BLUE, err=True
                )
                for target_id in sorted(list(target_ids_to_fetch)):
                    git_db.fetch_quipu_refs(remote, target_id)

            typer.secho("\n✅ Quipu 引用同步完成。", fg=typer.colors.GREEN, err=True)
            typer.secho("\n💡 提示: 运行 `quipu cache sync` 来更新本地数据库和 UI 视图。", fg=typer.colors.YELLOW, err=True)

        except RuntimeError as e:
            typer.secho(f"\n❌ 同步操作失败: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/run.py
~~~~~
~~~~~python
import inspect
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from quipu.core.executor import Executor

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import run_quipu
from ..logger_config import setup_logging

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command(name="run")
    def run_command(
        ctx: typer.Context,
        file: Annotated[Optional[Path], typer.Argument(help=f"包含 Markdown 指令的文件路径。", resolve_path=True)] = None,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        parser_name: Annotated[str, typer.Option("--parser", "-p", help=f"选择解析器语法。默认为 'auto'。")] = "auto",
        yolo: Annotated[
            bool, typer.Option("--yolo", "-y", help="跳过所有确认步骤，直接执行 (You Only Look Once)。")
        ] = False,
        list_acts: Annotated[bool, typer.Option("--list-acts", "-l", help="列出所有可用的操作指令及其说明。")] = False,
    ):
        """
        Quipu: 执行 Markdown 文件中的操作指令。
        """
        setup_logging()
        if list_acts:
            executor = Executor(root_dir=Path("."), yolo=True)
            from quipu.acts import register_core_acts

            register_core_acts(executor)
            typer.secho("\n📋 可用的 Quipu 指令列表:\n", fg=typer.colors.GREEN, bold=True, err=True)
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True, err=True)
                typer.echo(f"{indented_doc}\n", err=True)
            ctx.exit(0)

        content = ""
        source_desc = ""
        if file:
            if not file.exists():
                typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
            if not file.is_file():
                typer.secho(f"❌ 错误: 路径不是文件: {file}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
        elif not sys.stdin.isatty():
            try:
                stdin_content = sys.stdin.read()
                if stdin_content:
                    content = stdin_content
                    source_desc = "STDIN (管道流)"
            except Exception:
                pass
        if not content and DEFAULT_ENTRY_FILE.exists():
            content = DEFAULT_ENTRY_FILE.read_text(encoding="utf-8")
            source_desc = f"默认文件 ({DEFAULT_ENTRY_FILE.name})"
        if file and not file.exists() and file.name in ["log", "checkout", "sync", "init", "ui", "find"]:
            typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
            typer.secho(f"💡 提示: 你是不是想执行 'quipu {file.name}' 命令？", fg=typer.colors.YELLOW, err=True)
            ctx.exit(1)
        if not content.strip():
            if not file:
                typer.secho(
                    f"⚠️  提示: 未提供输入，且当前目录下未找到默认文件 '{DEFAULT_ENTRY_FILE.name}'。",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                typer.echo("\n用法示例:", err=True)
                typer.echo("  quipu run my_plan.md", err=True)
                typer.echo("  echo '...' | quipu run", err=True)
                ctx.exit(0)

        logger.info(f"已加载指令源: {source_desc}")
        logger.info(f"工作区根目录: {work_dir}")
        if yolo:
            logger.warning("⚠️  YOLO 模式已开启：将自动确认所有修改。")
        result = run_quipu(content=content, work_dir=work_dir, parser_name=parser_name, yolo=yolo)
        if result.message:
            color = typer.colors.GREEN if result.success else typer.colors.RED
            typer.secho(f"\n{result.message}", fg=color, err=True)
        if result.data:
            typer.echo(result.data)
        ctx.exit(result.exit_code)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/cache.py
~~~~~
~~~~~python
import logging
from pathlib import Path
from typing import Annotated

import typer

from .helpers import engine_context, _prompt_for_confirmation
from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging

logger = logging.getLogger(__name__)

cache_app = typer.Typer(name="cache", help="管理本地 SQLite 缓存。")


@cache_app.command("sync")
def cache_sync(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
):
    """
    将 Git 历史增量同步到 SQLite 缓存。
    """
    typer.secho("💧 正在执行增量数据补水...", fg=typer.colors.BLUE, err=True)
    try:
        with engine_context(work_dir):
            pass
        typer.secho("✅ 数据同步完成。", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        typer.secho(f"❌ 数据同步失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)


@cache_app.command("rebuild")
def cache_rebuild(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制执行，跳过确认提示。")] = False,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
):
    """
    强制全量重建 SQLite 缓存。
    """
    setup_logging()
    db_path = work_dir.resolve() / ".quipu" / "history.sqlite"
    if not db_path.exists():
        typer.secho("🤷 数据库文件不存在，将直接创建。无需重建。", fg=typer.colors.YELLOW, err=True)
        cache_sync(ctx, work_dir)
        return

    if not force:
        prompt = f"🚨 即将删除并重建数据库 {db_path}。\n此操作不可逆。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    try:
        db_path.unlink()
        typer.secho("🗑️  旧数据库已删除。", err=True)
    except Exception as e:
        typer.secho(f"❌ 删除旧数据库失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)

    cache_sync(ctx, work_dir)
~~~~~

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~
~~~~~python
import logging
from pathlib import Path
from typing import Annotated

import typer

from .helpers import engine_context, _execute_visit
from ..config import DEFAULT_WORK_DIR
from ..factory import create_engine
from ..logger_config import configure_file_logging

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command()
    def ui(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
    ):
        """
        以交互式 TUI 模式显示 Quipu 历史图谱。
        """
        try:
            from ..tui import QuipuUiApp
        except ImportError:
            typer.secho("❌ TUI 依赖 'textual' 未安装。", fg=typer.colors.RED, err=True)
            typer.secho("💡 请运行: pip install 'textual>=0.58.0'", err=True)
            ctx.exit(1)

        log_file = work_dir / ".quipu" / "tui.debug.log"
        configure_file_logging(log_file)
        logging.info("Starting Quipu UI command...")

        temp_engine = create_engine(work_dir, lazy=True)
        try:
            count = temp_engine.reader.get_node_count()
            if count == 0:
                typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
                ctx.exit(0)
        finally:
            temp_engine.close()

        app_instance = QuipuUiApp(work_dir=work_dir)
        result = app_instance.run()

        if result:
            action, data = result
            if action == "checkout":
                target_hash = data
                with engine_context(work_dir) as action_engine:
                    typer.secho(f"\n> TUI 请求检出到: {target_hash[:7]}", err=True)
                    _execute_visit(ctx, action_engine, target_hash, f"正在导航到 TUI 选定节点: {target_hash[:7]}")

            elif action == "dump":
                print(data)
                ctx.exit(0)
~~~~~

#### Acts 2: 重构 `main.py` 作为命令注册中心

现在，我们将 `main.py` 的内容替换为新的、简洁的注册逻辑。

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
import logging
import typer
from .commands import cache, navigation, query, remote, run, ui, workspace

# 初始化日志记录器，但不配置 handler
# handler 的配置（stderr 或 file）由具体命令在执行时决定
logging.getLogger(__name__)

# --- App Definition ---
app = typer.Typer(
    add_completion=False,
    name="quipu",
    help="Quipu: 一个基于 Git 的、用于文件系统状态溯源与文学化操作的工具。",
)

# --- Command Registration ---
# 注册子命令应用
app.add_typer(cache.cache_app)

# 注册顶级命令
workspace.register(app)
navigation.register(app)
query.register(app)
remote.register(app)
run.register(app)
ui.register(app)


# --- Entry Point ---
if __name__ == "__main__":
    app()
~~~~~

#### Acts 3: 重构 TUI 状态管理 (`ViewModel` 和 `TUI`)

我们将状态逻辑移入 `GraphViewModel` 并更新 `tui.py` 以使用它。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/view_model.py
~~~~~
~~~~~python
import math
from typing import List, Optional, Set

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader


class GraphViewModel:
    """
    一个 ViewModel, 用于解耦 TUI (View) 和 HistoryReader (Model)。

    它负责管理分页状态、缓存可达性数据，并为 UI 提供简洁的数据接口。
    """

    def __init__(self, reader: HistoryReader, current_output_tree_hash: Optional[str], page_size: int = 50):
        self.reader = reader
        self.current_output_tree_hash = current_output_tree_hash
        self.page_size = page_size

        # 状态属性
        self.total_nodes: int = 0
        self.total_pages: int = 1
        self.current_page: int = 0  # 页码从 1 开始
        self.reachable_set: Set[str] = set()

    def initialize(self):
~~~~~
~~~~~python
import math
from typing import Dict, List, Optional, Set

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader


class GraphViewModel:
    """
    一个 ViewModel, 用于解耦 TUI (View) 和 HistoryReader (Model)。

    它负责管理分页状态、缓存可达性数据，并为 UI 提供简洁的数据接口。
    """

    def __init__(self, reader: HistoryReader, current_output_tree_hash: Optional[str], page_size: int = 50):
        self.reader = reader
        self.current_output_tree_hash = current_output_tree_hash
        self.page_size = page_size

        # --- 核心状态 ---
        self.total_nodes: int = 0
        self.total_pages: int = 1
        self.current_page: int = 0

        # --- TUI 交互状态 ---
        self.show_unreachable: bool = True
        self.current_page_nodes: List[QuipuNode] = []
        self.current_selected_node: Optional[QuipuNode] = None
        self._node_by_key: Dict[str, QuipuNode] = {}
        self.reachable_set: Set[str] = set()

    def initialize(self):
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/view_model.py
~~~~~
~~~~~python
    def load_page(self, page_number: int) -> List[QuipuNode]:
        """
        加载指定页码的数据，更新内部状态，并返回该页的节点列表。
        """
        if not (1 <= page_number <= self.total_pages):
            return []  # 页码无效

        self.current_page = page_number
        offset = (self.current_page - 1) * self.page_size

        nodes = self.reader.load_nodes_paginated(limit=self.page_size, offset=offset)
        return nodes

    def previous_page(self) -> List[QuipuNode]:
~~~~~
~~~~~python
    def load_page(self, page_number: int) -> List[QuipuNode]:
        """
        加载指定页码的数据，更新内部状态，并返回该页的节点列表。
        """
        if not (1 <= page_number <= self.total_pages):
            self.current_page_nodes = []
            self._node_by_key = {}
            return []

        self.current_page = page_number
        offset = (self.current_page - 1) * self.page_size

        self.current_page_nodes = self.reader.load_nodes_paginated(limit=self.page_size, offset=offset)
        self._node_by_key = {str(node.filename): node for node in self.current_page_nodes}
        return self.current_page_nodes

    def toggle_unreachable(self):
        """切换是否显示不可达节点。"""
        self.show_unreachable = not self.show_unreachable

    def get_nodes_to_render(self) -> List[QuipuNode]:
        """根据当前可见性设置，返回需要渲染的节点列表。"""
        if self.show_unreachable:
            return self.current_page_nodes
        return [node for node in self.current_page_nodes if self.is_reachable(node.output_tree)]

    def select_node_by_key(self, key: str) -> Optional[QuipuNode]:
        """根据行 Key 选择节点并更新状态。"""
        node = self._node_by_key.get(key)
        self.current_selected_node = node
        return node

    def get_selected_node(self) -> Optional[QuipuNode]:
        return self.current_selected_node

    def previous_page(self) -> List[QuipuNode]:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def __init__(self, work_dir: Path):
        super().__init__()
        self.work_dir = work_dir
        self.engine: Optional[Engine] = None
        self.view_model: Optional[GraphViewModel] = None
        self.show_unreachable = True
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
        self.node_by_filename: dict[str, QuipuNode] = {}

    def compose(self) -> ComposeResult:
~~~~~
~~~~~python
    def __init__(self, work_dir: Path):
        super().__init__()
        self.work_dir = work_dir
        self.engine: Optional[Engine] = None
        self.view_model: Optional[GraphViewModel] = None
        # is_split_mode 是纯视图状态，保留在 App 中
        self.is_split_mode = False

    def compose(self) -> ComposeResult:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _load_page(self, page_number: int) -> None:
        """Loads and displays a specific page of nodes."""
        logger.debug(f"TUI: Loading page {page_number}")
        nodes = self.view_model.load_page(page_number)
        logger.debug(f"TUI: Page {page_number} loaded with {len(nodes)} nodes.")

        if not nodes:
            return

        self.node_by_filename = {str(node.filename): node for node in nodes}
        table = self.query_one(DataTable)
        table.clear()
        self._populate_table(table, nodes)
        self._focus_current_node(table)
        self._update_header()

    def action_move_up(self) -> None:
~~~~~
~~~~~python
    def _load_page(self, page_number: int) -> None:
        """Loads and displays a specific page of nodes."""
        logger.debug(f"TUI: Loading page {page_number}")
        self.view_model.load_page(page_number)
        logger.debug(f"TUI: Page {page_number} loaded with {len(self.view_model.current_page_nodes)} nodes.")

        table = self.query_one(DataTable)
        table.clear()
        # 从 ViewModel 获取过滤后的节点列表进行渲染
        self._populate_table(table, self.view_model.get_nodes_to_render())
        self._focus_current_node(table)
        self._update_header()

    def action_move_up(self) -> None:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.show_unreachable = not self.show_unreachable
        self._refresh_table()

    def action_toggle_view(self) -> None:
~~~~~
~~~~~python
    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.view_model.toggle_unreachable()
        self._refresh_table()

    def action_toggle_view(self) -> None:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def action_checkout_node(self) -> None:
        if self.current_selected_node:
            self.exit(result=("checkout", self.current_selected_node.output_tree))

    def action_dump_content(self) -> None:
        if self.current_selected_node:
            content = self.view_model.get_content_bundle(self.current_selected_node)
            self.exit(result=("dump", content))

    def action_previous_page(self) -> None:
~~~~~
~~~~~python
    def action_checkout_node(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            self.exit(result=("checkout", selected_node.output_tree))

    def action_dump_content(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            content = self.view_model.get_content_bundle(selected_node)
            self.exit(result=("dump", content))

    def action_previous_page(self) -> None:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _refresh_table(self):
        table = self.query_one(DataTable)
        current_page_nodes = list(self.node_by_filename.values())
        sorted_nodes = sorted(current_page_nodes, key=lambda n: n.timestamp, reverse=True)
        table.clear()
        self._populate_table(table, sorted_nodes)
        self._focus_current_node(table)
        self._update_header()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []

        for node in nodes_to_render:
            is_reachable = self.view_model.is_reachable(node.output_tree)
~~~~~
~~~~~python
    def _refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        # 从 ViewModel 获取要渲染的节点
        nodes_to_render = self.view_model.get_nodes_to_render()
        self._populate_table(table, nodes_to_render)
        self._focus_current_node(table)
        self._update_header()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        # 移除了过滤逻辑，因为 ViewModel 已经处理
        tracks: list[Optional[str]] = []

        for node in nodes:
            is_reachable = self.view_model.is_reachable(node.output_tree)
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
        # 查找当前页面中匹配 HEAD 的所有节点
        matching = [n for n in self.node_by_filename.values() if n.output_tree == current_output_tree_hash]
        logger.debug(f"DEBUG: Found {len(matching)} matching nodes in current page map.")

        target_node = matching[0] if matching else None
~~~~~
~~~~~python
        # 查找当前页面中匹配 HEAD 的所有节点
        matching = [
            n for n in self.view_model.current_page_nodes if n.output_tree == current_output_tree_hash
        ]
        logger.debug(f"DEBUG: Found {len(matching)} matching nodes in current page map.")

        target_node = matching[0] if matching else None
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
                table.cursor_coordinate = Coordinate(row=row_index, column=0)

                # 2. 同步逻辑状态 (防止事件未触发)
                self.current_selected_node = target_node

                # 3. 刷新关联视图
                if self.is_split_mode:
~~~~~
~~~~~python
                table.cursor_coordinate = Coordinate(row=row_index, column=0)

                # 2. 同步逻辑状态 (防止事件未触发)
                self.view_model.select_node_by_key(row_key)

                # 3. 刷新关联视图
                if self.is_split_mode:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key and (node := self.node_by_filename.get(row_key)):
            self.current_selected_node = node
            if self.is_split_mode:
                self._update_content_view()

    def _update_content_view(self):
        if not self.current_selected_node:
            return
        node = self.current_selected_node
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")
        content = self.view_model.get_content_bundle(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content)
~~~~~
~~~~~python
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key:
            self.view_model.select_node_by_key(row_key)
            if self.is_split_mode:
                self._update_content_view()

    def _update_content_view(self):
        node = self.view_model.get_selected_node()
        if not node:
            return
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")
        content = self.view_model.get_content_bundle(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content)
~~~~~

### 下一步建议
重构已完成。接下来，可以为新拆分出的命令模块编写独立的单元测试，以提高测试覆盖率和代码健壮性。
