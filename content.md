## [WIP] feat: 实现无状态的 `quipu axon` 子命令

### 错误分析
当前 Quipu 的所有执行逻辑都绑定在 `quipu run` 命令中，该命令强制初始化 `Engine`，要求工作区必须是 Git 仓库且存在 `.quipu` 目录。这限制了 `quipu-runtime` 在非 Git 环境或纯任务执行场景（如 CI/CD 脚本、脚手架初始化）下的使用。

### 用户需求
1.  **独立命令**: 提供一个 `quipu axon` 命令。
2.  **无状态执行**: 该命令不应尝试连接数据库、加载历史图谱或检查 Git 状态。
3.  **标准输入支持**: 支持像 `run` 一样通过管道 (`|`) 接收 Markdown 内容。
4.  **功能对齐**: 保留 `run` 命令中的 `--yolo`, `--list-acts`, `--parser` 等实用参数。

### 评论
将执行能力解耦是架构成熟的重要标志。这使得 Quipu 不仅仅是一个版本控制增强工具，更是一个通用的、基于 Markdown 的自动化任务执行引擎。

### 目标
1.  创建 `packages/quipu-cli/src/quipu/cli/commands/axon.py`。
2.  在 `axon.py` 中实现独立的执行流程：解析参数 -> 初始化无状态 Executor -> 加载插件 -> 解析内容 -> 执行。
3.  在 `packages/quipu-cli/src/quipu/cli/main.py` 中注册新命令。

### 基本原理
-   **代码复用**: 复用 `quipu-cli` 中的 `Executor` 工厂模式逻辑（稍作修改以去除 Engine 依赖）和 `PluginManager`。
-   **架构解耦**: 显式避开 `quipu.cli.controller.run_quipu` 入口，直接调用 `quipu.core` 层级的基础组件。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/executor #scope/api #ai/instruct #task/domain/cli #task/object/subcommand-axon #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 axon 命令实现文件

这个文件将包含 `axon` 命令的所有逻辑，包括参数处理、Executor 初始化（包含 TUI 确认逻辑的复刻）以及执行流程。

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
~~~~~
~~~~~python
import inspect
import logging
import sys
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from quipu.acts import register_core_acts
from quipu.core.exceptions import ExecutionError
from quipu.core.executor import Executor
from quipu.core.parser import detect_best_parser, get_parser

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command(name="axon")
    def axon_command(
        ctx: typer.Context,
        file: Annotated[Optional[Path], typer.Argument(help="包含 Markdown 指令的文件路径。", resolve_path=True)] = None,
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
            typer.echo("")

            if not sys.stdin.isatty():
                logger.warning("非交互式环境，自动跳过确认。使用 --yolo 参数可自动批准。")
                return False

            return typer.confirm(prompt, default=True)

        # 2. 初始化无状态 Executor
        # 注意：这里不初始化 Engine，因此没有历史记录功能
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=typer_confirmation_handler,
        )
        register_core_acts(executor)
        
        # 3. 加载插件
        # PluginManager 会尝试查找 Git 根目录加载项目级插件，如果找不到 Git 根目录则跳过，符合无状态设计
        PluginManager().load_from_sources(executor, work_dir)

        # 4. 处理 --list-acts
        if list_acts:
            typer.secho("\n📋 可用的 Axon 指令列表:\n", fg=typer.colors.GREEN, bold=True, err=True)
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True, err=True)
                typer.echo(f"{indented_doc}\n", err=True)
            ctx.exit(0)

        # 5. 获取输入内容 (文件 或 STDIN 或 默认文件)
        content = ""
        source_desc = ""
        if file:
            if not file.exists():
                typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
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
        
        # 如果没有指定文件且没有 STDIN，尝试读取当前目录下的默认入口文件 (如 o.md)
        if not content and not file and DEFAULT_ENTRY_FILE.exists():
             content = DEFAULT_ENTRY_FILE.read_text(encoding="utf-8")
             source_desc = f"默认文件 ({DEFAULT_ENTRY_FILE.name})"

        if not content.strip():
             typer.secho("⚠️  提示: 未提供输入 (文件或管道)，且未找到默认文件。", fg=typer.colors.YELLOW, err=True)
             ctx.exit(0)

        logger.info(f"Axon 启动 | 源: {source_desc} | 工作区: {work_dir}")

        # 6. 解析
        final_parser_name = parser_name
        if parser_name == "auto":
            final_parser_name = detect_best_parser(content)
        
        try:
            parser = get_parser(final_parser_name)
            statements = parser.parse(content)
            
            if not statements:
                typer.secho(f"⚠️  未解析到任何有效指令 (Parser: {final_parser_name})。", fg=typer.colors.YELLOW, err=True)
                ctx.exit(0)

            # 7. 执行
            executor.execute(statements)
            typer.secho("\n✨ Axon 执行完成。", fg=typer.colors.GREEN, err=True)

        except ExecutionError as e:
            typer.secho(f"\n❌ 执行失败: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
        except Exception as e:
            logger.error(f"系统错误: {e}", exc_info=True)
            typer.secho(f"\n❌ 系统错误: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
~~~~~

#### Acts 2: 注册 Axon 命令

将新的 `axon` 模块导入并注册到主应用中。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
import logging
import typer
from .commands import cache, navigation, query, remote, run, ui, workspace
~~~~~
~~~~~python
import logging
import typer
from .commands import axon, cache, navigation, query, remote, run, ui, workspace
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
# 注册子命令应用
app.add_typer(cache.cache_app)

# 注册顶级命令
workspace.register(app)
~~~~~
~~~~~python
# 注册子命令应用
app.add_typer(cache.cache_app)

# 注册顶级命令
axon.register(app)
workspace.register(app)
~~~~~
