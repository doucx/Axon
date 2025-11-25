# fix-test: 修复因移除 `load_history_graph` 导致的测试导入错误

## 用户需求
在执行 `1.3` 计划后，移除了 `quipu.core.history.load_history_graph` 函数，但这导致了多个测试文件和 `quipu-cli` 模块因无法找到该导入而崩溃。需要修复这些引用，使其适应 `Engine` 依赖注入的新架构。

## 评论
这是一个预料之中的重构连锁反应。修复这些错误是完成“面向接口编程”重构的最后一步。核心工作是将之前直接调用 `load_history_graph` 的地方，改为通过正确初始化的 `Engine` 实例来访问历史图谱，这验证了我们新架构的正确性。

## 目标
1.  修改 `quipu.cli.controller` 和 `quipu.cli.main`，使其能够正确地实例化 `Engine` 及其所需的 `HistoryReader` 和 `HistoryWriter` 依赖。
2.  修复所有受影响的测试文件 (`test_engine.py`, `test_graph_loader.py`)，使其不再直接导入或调用 `load_history_graph`，而是通过新的 `Engine` API 或直接测试 `load_all_history_nodes`。
3.  确保所有测试能够重新被 `pytest` 收集并运行。

## 基本原理
我们将在 CLI 的入口层 (`controller` 和 `main`) 负责组装 `Engine` 所需的依赖（即 `FileSystemHistoryReader` 和 `FileSystemHistoryWriter`）。这遵循了依赖注入的原则，将对象的创建和配置与使用分离开。对于测试，我们将更新测试用例以反映这种新的初始化方式，并确保测试目标与代码的当前结构保持一致。

## 标签
#comp/cli #comp/engine #comp/tests #scope/dx #concept/history

---

## Script

### Acts 1: 更新 Controller 和 CLI 主程序以适应 Engine 依赖注入

首先，修复 `controller.py` 中 `Engine` 的实例化，然后重构 `main.py` 中所有命令，使其通过一个辅助函数来正确创建 `Engine` 实例。

~~~~~act
write_file
~~~~~

~~~~~path
packages/quipu-cli/src/quipu/cli/controller.py
~~~~~

~~~~~python
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from quipu.core.result import QuipuResult
from quipu.core.state_machine import Engine
from quipu.core.executor import Executor, ExecutionError
from quipu.core.exceptions import ExecutionError as CoreExecutionError
from quipu.core.parser import get_parser, detect_best_parser
from quipu.core.plugin_loader import load_plugins
from quipu.core.file_system_storage import FileSystemHistoryReader, FileSystemHistoryWriter

# 从配置导入，注意为了解耦，未来可能需要将 config 注入而不是直接导入
from .config import PROJECT_ROOT
from quipu.acts import register_core_acts

logger = logging.getLogger(__name__)

def find_project_root(start_path: Path) -> Optional[Path]:
    """向上递归查找包含 .git 的目录作为项目根目录"""
    try:
        current = start_path.resolve()
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
    except Exception:
        pass
    return None

def _load_extra_plugins(executor: Executor, work_dir: Path):
    """
    按照层级顺序加载外部插件，高优先级会覆盖低优先级。
    优先级顺序: Project > Env > Home
    """
    plugin_sources = []
    
    # 优先级由低到高添加，后面的会覆盖前面的
    # 1. User Home (Lowest priority)
    home_acts = Path.home() / ".quipu" / "acts"
    plugin_sources.append(("🏠 Global", home_acts))

    # 2. Config / Env
    env_path = os.getenv("AXON_EXTRA_ACTS_DIR")
    if env_path:
        plugin_sources.append(("🔧 Env", Path(env_path)))
    
    # 3. Project Root (Highest priority)
    project_root = find_project_root(work_dir)
    if project_root:
        proj_acts = project_root / ".quipu" / "acts"
        plugin_sources.append(("📦 Project", proj_acts))

    seen_paths = set()
    for label, path in plugin_sources:
        if not path.exists() or not path.is_dir():
            continue
        
        resolved_path = path.resolve()
        if resolved_path in seen_paths:
            continue
        
        load_plugins(executor, path)
        seen_paths.add(resolved_path)

def run_quipu(
    content: str,
    work_dir: Path,
    parser_name: str = "auto",
    yolo: bool = False
) -> QuipuResult:
    """
    Axon 核心业务逻辑入口。
    
    负责协调 Engine (状态), Parser (解析), Executor (执行) 三者的工作。
    任何异常都会被捕获并转化为失败的 QuipuResult。
    """
    try:
        # --- Phase 0: Root Canonicalization (根目录规范化) ---
        # 无论用户从哪个子目录启动，都必须找到并使用唯一的项目根。
        # 这是确保 Engine 和 Executor 上下文一致性的关键。
        project_root = find_project_root(work_dir)
        if not project_root:
            # 如果不在 Git 仓库内，则使用原始 work_dir，但 Engine 初始化会失败。
            # 这是预期的行为，因为 Axon 强依赖 Git。
            project_root = work_dir
        
        logger.info(f"Project Root resolved to: {project_root}")

        # --- Phase 1: Engine Initialization & Perception ---
        # 注意：所有核心组件都必须使用规范化后的 project_root 初始化！
        history_dir = project_root / ".quipu" / "history"
        reader = FileSystemHistoryReader(history_dir)
        writer = FileSystemHistoryWriter(history_dir)
        engine = Engine(project_root, reader=reader, writer=writer)

        status = engine.align() # "CLEAN", "DIRTY", "ORPHAN"
        
        current_hash = engine.git_db.get_tree_hash()
        
        # --- Phase 2: Decision (Lazy Capture) ---
        if status in ["DIRTY", "ORPHAN"]:
            # 如果环境有漂移（或全新项目），先生成一个 Capture 节点
            # 这确保了后续的 Plan 是基于一个已知的、干净的状态执行的
            engine.capture_drift(current_hash)
            # 捕获后，status 逻辑上变为 CLEAN，current_node 更新为 CaptureNode
        
        # 记录执行前的状态，作为 Plan 的 input_tree
        if engine.current_node:
            input_tree_hash = engine.current_node.output_tree
        else:
            # 此处处理创世状态：当 align() 返回 CLEAN 但 current_node 为 None 时。
            # 输入哈希就是当前的（空的）哈希。
            input_tree_hash = current_hash

        # --- Phase 3: Action (Execution) ---
        
        # 3.1 Parser
        final_parser_name = parser_name
        if parser_name == "auto":
            final_parser_name = detect_best_parser(content)
            if final_parser_name != "backtick":
                logger.info(f"🔍 自动检测到解析器: {final_parser_name}")

        parser = get_parser(final_parser_name)
        statements = parser.parse(content)
        
        if not statements:
            return QuipuResult(
                success=False, 
                exit_code=0, # 没找到指令不算错误，但也无需继续
                message=f"⚠️  使用 '{final_parser_name}' 解析器未找到任何有效的 'act' 操作块。"
            )

        # 3.2 Executor Setup
        executor = Executor(root_dir=project_root, yolo=yolo) # 使用 project_root
        
        # 加载插件
        register_core_acts(executor) # 内置 (从 runtime 包加载)
        _load_extra_plugins(executor, project_root)       # 外部 (也基于 project_root)

        # 3.3 Execute
        executor.execute(statements)

        # --- Phase 4: Recording (Plan Crystallization) ---
        
        # 执行成功后，计算新的状态
        output_tree_hash = engine.git_db.get_tree_hash()
        
        # 如果状态发生了变化，或者我们想记录即使无变化的 Plan（通常记录一下比较好）
        # 这里我们调用 Engine 的 create_plan_node 方法
        # 注意：该方法需要在 Engine 类中实现
        engine.create_plan_node(
            input_tree=input_tree_hash,
            output_tree=output_tree_hash,
            plan_content=content
        )

        return QuipuResult(success=True, exit_code=0, message="✨ 执行成功")

    except (ExecutionError, CoreExecutionError) as e:
        # 预期的执行错误 (如文件找不到，Git 冲突等)
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(success=False, exit_code=1, message=str(e), error=e)
        
    except Exception as e:
        # 意外的运行时错误
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(success=False, exit_code=1, message=f"系统错误: {e}", error=e)
~~~~~

~~~~~act
write_file
~~~~~

~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
import typer
import logging
import sys
import click # 导入 click 库
from pathlib import Path
from typing import Annotated, Optional, Dict

from .logger_config import setup_logging
from .controller import run_quipu, find_project_root
from .config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
from quipu.core.plugin_loader import load_plugins
from quipu.core.executor import Executor
from quipu.core.state_machine import Engine
from quipu.core.history import load_all_history_nodes
from quipu.core.models import QuipuNode
from quipu.core.file_system_storage import FileSystemHistoryReader, FileSystemHistoryWriter
import inspect
import subprocess
from quipu.core.config import ConfigManager

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

def _resolve_root(work_dir: Path) -> Path:
    """辅助函数：解析项目根目录，如果未找到则回退到 work_dir"""
    root = find_project_root(work_dir)
    return root if root else work_dir

def _setup_engine(work_dir: Path) -> Engine:
    """辅助函数：实例化完整的 Engine 堆栈"""
    real_root = _resolve_root(work_dir)
    # 注意: 当前硬编码为文件系统存储。未来这里可以加入逻辑来检测项目类型。
    history_dir = real_root / ".quipu" / "history"
    reader = FileSystemHistoryReader(history_dir)
    writer = FileSystemHistoryWriter(history_dir)
    engine = Engine(real_root, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱
    return engine

# --- 导航命令辅助函数 ---
def _find_current_node(engine: Engine, graph: Dict[str, QuipuNode]) -> Optional[QuipuNode]:
    """在图中查找与当前工作区状态匹配的节点"""
    current_hash = engine.git_db.get_tree_hash()
    node = graph.get(current_hash)
    if not node:
        typer.secho("⚠️  当前工作区状态未在历史中找到，或存在未保存的变更。", fg=typer.colors.YELLOW, err=True)
        typer.secho("💡  请先运行 'quipu save' 创建一个快照，再进行导航。", fg=typer.colors.YELLOW, err=True)
    return node

def _execute_visit(ctx: typer.Context, engine: Engine, target_hash: str, description: str):
    """辅助函数：执行 engine.visit 并处理结果"""
    typer.secho(f"🚀 {description}", err=True)
    try:
        engine.visit(target_hash)
        typer.secho(f"✅ 已成功切换到状态 {target_hash[:7]}。", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        typer.secho(f"❌ 导航操作失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)

# --- 核心命令 ---

@app.command()
def ui(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
):
    """
    以交互式 TUI 模式显示 Axon 历史图谱。
    """
    try:
        from .tui import QuipuUiApp
    except ImportError:
        typer.secho("❌ TUI 依赖 'textual' 未安装。", fg=typer.colors.RED, err=True)
        typer.secho("💡 请运行: pip install 'textual>=0.58.0'", err=True)
        ctx.exit(1)
        
    setup_logging()
    
    engine = _setup_engine(work_dir)
    all_nodes = engine.reader.load_all_nodes()
    
    if not all_nodes:
        typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
        ctx.exit(0)
        
    graph = engine.history_graph
    current_hash = engine.git_db.get_tree_hash()
    
    app_instance = QuipuUiApp(all_nodes, current_hash=current_hash)
    selected_hash = app_instance.run()

    if selected_hash:
        if selected_hash in graph:
            typer.secho(f"\n> TUI 请求检出到: {selected_hash[:7]}", err=True)
            _execute_visit(ctx, engine, selected_hash, f"正在导航到 TUI 选定节点: {selected_hash[:7]}")
        else:
            typer.secho(f"❌ 错误: 无法在历史图谱中找到目标哈希 {selected_hash[:7]}", fg=typer.colors.RED, err=True)
            ctx.exit(1)


@app.command()
def save(
    ctx: typer.Context,
    message: Annotated[Optional[str], typer.Argument(help="本次快照的简短描述。")] = None,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
):
    """
    捕获当前工作区的状态，创建一个“微提交”快照。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    # align 已经在 _setup_engine 中调用过了
    status = "DIRTY" if engine.current_node is None else "CLEAN" # 简化状态判断
    if engine.current_node:
        current_tree_hash = engine.git_db.get_tree_hash()
        if engine.current_node.output_tree == current_tree_hash:
            status = "CLEAN"
            
    if status == "CLEAN":
        typer.secho("✅ 工作区状态未发生变化，无需创建快照。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)
        
    current_hash = engine.git_db.get_tree_hash()
    try:
        node = engine.capture_drift(current_hash, message=message)
        msg_suffix = f' ({message})' if message else ''
        typer.secho(f"📸 快照已保存: {node.short_hash}{msg_suffix}", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        typer.secho(f"❌ 创建快照失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)

@app.command()
def sync(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
    remote: Annotated[Optional[str], typer.Option("--remote", "-r", help="Git 远程仓库的名称 (覆盖配置文件)。")] = None,
):
    """
    与远程仓库同步 Axon 历史图谱。
    """
    setup_logging()
    work_dir = _resolve_root(work_dir) # Sync needs root
    config = ConfigManager(work_dir)
    if remote is None:
        remote = config.get("sync.remote_name", "origin")
    refspec = "refs/quipu/history:refs/quipu/history"
    def run_git_command(args: list[str]):
        try:
            result = subprocess.run(["git"] + args, cwd=work_dir, capture_output=True, text=True, check=True)
            if result.stdout: typer.echo(result.stdout, err=True)
            if result.stderr: typer.echo(result.stderr, err=True)
        except subprocess.CalledProcessError as e:
            typer.secho(f"❌ Git 命令执行失败: git {' '.join(args)}", fg=typer.colors.RED, err=True)
            typer.secho(e.stderr, fg=typer.colors.YELLOW, err=True)
            ctx.exit(1)
        except FileNotFoundError:
            typer.secho("❌ 错误: 未找到 'git' 命令。", fg=typer.colors.RED, err=True)
            ctx.exit(1)
    typer.secho(f"⬇️  正在从 '{remote}' 拉取 Axon 历史...", fg=typer.colors.BLUE, err=True)
    run_git_command(["fetch", remote, refspec])
    typer.secho(f"⬆️  正在向 '{remote}' 推送 Axon 历史...", fg=typer.colors.BLUE, err=True)
    run_git_command(["push", remote, refspec])
    typer.secho("\n✅ Axon 历史同步完成。", fg=typer.colors.GREEN, err=True)
    config_get_res = subprocess.run(["git", "config", "--get", f"remote.{remote}.fetch"], cwd=work_dir, capture_output=True, text=True)
    if refspec not in config_get_res.stdout:
        typer.secho("\n💡 提示: 为了让 `git pull` 自动同步 Axon 历史，请执行以下命令:", fg=typer.colors.YELLOW, err=True)
        typer.echo(f'  git config --add remote.{remote}.fetch "{refspec}"')

@app.command()
def discard(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="强制执行，跳过确认提示。")
    ] = False,
):
    """
    丢弃工作区所有未记录的变更，恢复到上一个干净状态。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    if not graph:
        typer.secho("❌ 错误: 找不到任何历史记录，无法确定要恢复到哪个状态。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    
    target_tree_hash = engine._read_head()
    if not target_tree_hash or target_tree_hash not in graph:
        latest_node = max(graph.values(), key=lambda n: n.timestamp)
        target_tree_hash = latest_node.output_tree
        typer.secho(f"⚠️  HEAD 指针丢失或无效，将恢复到最新历史节点: {latest_node.short_hash}", fg=typer.colors.YELLOW, err=True)
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

@app.command()
def checkout(
    ctx: typer.Context,
    hash_prefix: Annotated[str, typer.Argument(help="目标状态节点的哈希前缀。")],
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="强制执行，跳过确认提示。")
    ] = False,
):
    """
    将工作区恢复到指定的历史节点状态。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    
    matches = [node for sha, node in graph.items() if sha.startswith(hash_prefix)]
    if not matches:
        typer.secho(f"❌ 错误: 未找到哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    if len(matches) > 1:
        typer.secho(f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    target_node = matches[0]
    target_tree_hash = target_node.output_tree
    
    current_hash = engine.git_db.get_tree_hash()
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已处于目标状态 ({target_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)

    is_dirty = engine.current_node is None or engine.current_node.output_tree != current_hash
    if is_dirty:
        typer.secho("⚠️  检测到当前工作区存在未记录的变更，将自动创建捕获节点...", fg=typer.colors.YELLOW, err=True)
        engine.capture_drift(current_hash)
        typer.secho("✅ 变更已捕获。", fg=typer.colors.GREEN, err=True)
        current_hash = engine.git_db.get_tree_hash()

    diff_stat = engine.git_db.get_diff_stat(current_hash, target_tree_hash)
    if diff_stat:
        typer.secho("\n以下是将要发生的变更:", fg=typer.colors.YELLOW, err=True)
        typer.secho("-" * 20, err=True)
        typer.echo(diff_stat, err=True)
        typer.secho("-" * 20, err=True)

    if not force:
        prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    _execute_visit(ctx, engine, target_tree_hash, f"正在导航到节点: {target_node.short_hash}")

# --- 结构化导航命令 ---
@app.command()
def undo(
    ctx: typer.Context,
    count: Annotated[int, typer.Option("--count", "-n", help="向上移动的步数。")] = 1,
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [结构化导航] 向上移动到当前状态的父节点。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    current_node = _find_current_node(engine, graph)
    if not current_node: ctx.exit(1)
    target_node = current_node
    for i in range(count):
        if not target_node.parent:
            msg = f"已到达历史根节点 (移动了 {i} 步)。" if i > 0 else "已在历史根节点。"
            typer.secho(f"✅ {msg}", fg=typer.colors.GREEN, err=True)
            if target_node == current_node: ctx.exit(0)
            break
        target_node = target_node.parent
    
    _execute_visit(ctx, engine, target_node.output_tree, f"正在撤销到父节点: {target_node.short_hash}")

@app.command()
def redo(
    ctx: typer.Context,
    count: Annotated[int, typer.Option("--count", "-n", help="向下移动的步数。")] = 1,
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [结构化导航] 向下移动到子节点 (默认最新)。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    current_node = _find_current_node(engine, graph)
    if not current_node: ctx.exit(1)
    target_node = current_node
    for i in range(count):
        if not target_node.children:
            msg = f"已到达分支末端 (移动了 {i} 步)。" if i > 0 else "已在分支末端。"
            typer.secho(f"✅ {msg}", fg=typer.colors.GREEN, err=True)
            if target_node == current_node: ctx.exit(0)
            break
        target_node = target_node.children[-1]
        if len(current_node.children) > 1:
            typer.secho(f"💡 当前节点有多个分支，已自动选择最新分支 -> {target_node.short_hash}", fg=typer.colors.YELLOW, err=True)
    
    _execute_visit(ctx, engine, target_node.output_tree, f"正在重做到子节点: {target_node.short_hash}")

@app.command()
def prev(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [结构化导航] 切换到上一个兄弟分支。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    current_node = _find_current_node(engine, graph)
    if not current_node: ctx.exit(1)
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
    except ValueError: pass

@app.command()
def next(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [结构化导航] 切换到下一个兄弟分支。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph
    current_node = _find_current_node(engine, graph)
    if not current_node: ctx.exit(1)
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
    except ValueError: pass

# --- 时序性导航命令 (新增) ---

@app.command()
def back(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [时序性导航] 后退：回到上一次访问的历史状态。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    
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
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", "-w", help="工作区根目录。")
    ] = DEFAULT_WORK_DIR,
):
    """
    [时序性导航] 前进：撤销后退操作。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    
    try:
        result_hash = engine.forward()
        if result_hash:
            typer.secho(f"✅ 已前进到状态: {result_hash[:7]}", fg=typer.colors.GREEN, err=True)
        else:
            typer.secho("⚠️  已到达访问历史的终点。", fg=typer.colors.YELLOW, err=True)
    except Exception as e:
        typer.secho(f"❌ 前进操作失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)


@app.command()
def log(
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
):
    """
    显示 Axon 历史图谱日志。
    """
    setup_logging()
    engine = _setup_engine(work_dir)
    graph = engine.history_graph

    if not graph:
        typer.secho("📜 历史记录为空。", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(0)
    nodes = sorted(graph.values(), key=lambda n: n.timestamp, reverse=True)
    typer.secho("--- Axon History Log ---", bold=True, err=True)
    for node in nodes:
        ts = node.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        color = typer.colors.CYAN if node.node_type == "plan" else typer.colors.MAGENTA
        tag = f"[{node.node_type.upper()}]"
        summary = ""
        content_lines = node.content.strip().split('\n')
        if node.node_type == 'plan':
            in_act_block = False
            for line in content_lines:
                if line.strip().startswith(('~~~act', '```act')): in_act_block = True; continue
                if in_act_block and line.strip(): summary = line.strip(); break
            if not summary: summary = "Plan executed"
        elif node.node_type == 'capture':
            in_diff_block = False; diff_summary_lines = []
            for line in content_lines:
                if "变更文件摘要" in line: in_diff_block = True; continue
                if in_diff_block and line.strip().startswith('```'): break
                if in_diff_block and line.strip(): diff_summary_lines.append(line.strip())
            if diff_summary_lines:
                files_changed = [l.split('|')[0].strip() for l in diff_summary_lines]
                summary = f"Changes captured in: {', '.join(files_changed)}"
            else: summary = "Workspace changes captured"
        summary = (summary[:75] + '...') if len(summary) > 75 else summary
        typer.secho(f"{ts} {tag:<9} {node.short_hash}", fg=color, nl=False, err=True)
        typer.echo(f" - {summary}", err=True)

@app.command(name="run")
def run_command(
    ctx: typer.Context,
    file: Annotated[
        Optional[Path], 
        typer.Argument(help=f"包含 Markdown 指令的文件路径。", resolve_path=True)
    ] = None,
    work_dir: Annotated[
        Path, 
        typer.Option("--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True)
    ] = DEFAULT_WORK_DIR,
    parser_name: Annotated[str, typer.Option("--parser", "-p", help=f"选择解析器语法。默认为 'auto'。")] = "auto",
    yolo: Annotated[bool, typer.Option("--yolo", "-y", help="跳过所有确认步骤，直接执行 (You Only Look Once)。")] = False,
    list_acts: Annotated[bool, typer.Option("--list-acts", "-l", help="列出所有可用的操作指令及其说明。")] = False
):
    """
    Axon: 执行 Markdown 文件中的操作指令。
    """
    setup_logging()
    if list_acts:
        executor = Executor(root_dir=Path("."), yolo=True)
        from quipu.acts import register_core_acts
        register_core_acts(executor)
        typer.secho("\n📋 可用的 Axon 指令列表:\n", fg=typer.colors.GREEN, bold=True, err=True)
        acts = executor.get_registered_acts()
        for name in sorted(acts.keys()):
            doc = acts[name]
            clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
            indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
            typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True, err=True)
            typer.echo(f"{indented_doc}\n", err=True)
        ctx.exit(0)
    content = ""; source_desc = ""
    if file:
        if not file.exists(): typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True); ctx.exit(1)
        if not file.is_file(): typer.secho(f"❌ 错误: 路径不是文件: {file}", fg=typer.colors.RED, err=True); ctx.exit(1)
        content = file.read_text(encoding="utf-8"); source_desc = f"文件 ({file.name})"
    elif not sys.stdin.isatty():
        try:
            stdin_content = sys.stdin.read()
            if stdin_content: content = stdin_content; source_desc = "STDIN (管道流)"
        except Exception: pass
    if not content and DEFAULT_ENTRY_FILE.exists():
        content = DEFAULT_ENTRY_FILE.read_text(encoding="utf-8"); source_desc = f"默认文件 ({DEFAULT_ENTRY_FILE.name})"
    if file and not file.exists() and file.name in ["log", "checkout", "sync", "init", "ui"]:
        typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
        typer.secho(f"💡 提示: 你是不是想执行 'quipu {file.name}' 命令？", fg=typer.colors.YELLOW, err=True)
        ctx.exit(1)
    if not content.strip():
        if not file:
            typer.secho(f"⚠️  提示: 未提供输入，且当前目录下未找到默认文件 '{DEFAULT_ENTRY_FILE.name}'。", fg=typer.colors.YELLOW, err=True)
            typer.echo("\n用法示例:", err=True); typer.echo("  quipu run my_plan.md", err=True); typer.echo("  echo '...' | quipu run", err=True)
            ctx.exit(0)
    logger.info(f"已加载指令源: {source_desc}"); logger.info(f"工作区根目录: {work_dir}")
    if yolo: logger.warning("⚠️  YOLO 模式已开启：将自动确认所有修改。")
    result = run_quipu(content=content, work_dir=work_dir, parser_name=parser_name, yolo=yolo)
    if result.message:
        color = typer.colors.GREEN if result.success else typer.colors.RED
        typer.secho(f"\n{result.message}", fg=color, err=True)
    if result.data: typer.echo(result.data)
    ctx.exit(result.exit_code)

if __name__ == "__main__":
    app()
~~~~~

### Acts 2: 修复测试文件

现在修复 `test_engine.py` 和 `test_graph_loader.py`。

~~~~~act
write_file
~~~~~

~~~~~path
tests/test_engine.py
~~~~~

~~~~~python
import pytest
import subprocess
from pathlib import Path
from datetime import datetime
from quipu.core.state_machine import Engine
from quipu.core.git_db import GitDB
from quipu.core.file_system_storage import FileSystemHistoryReader, FileSystemHistoryWriter

@pytest.fixture
def engine_setup(tmp_path):
    """
    创建一个包含 Git 仓库、Engine 实例和模拟历史目录的测试环境。
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    
    history_dir = repo_path / ".quipu" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    reader = FileSystemHistoryReader(history_dir)
    writer = FileSystemHistoryWriter(history_dir)
    engine = Engine(repo_path, reader=reader, writer=writer)
    
    return engine, repo_path

def test_align_clean_state(engine_setup):
    """
    测试场景：当工作区状态与最新的历史节点完全匹配时，
    引擎应能正确识别为 "CLEAN" 状态。
    """
    engine, repo_path = engine_setup
    
    (repo_path / "main.py").write_text("print('hello')", "utf-8")
    clean_hash = engine.git_db.get_tree_hash()
    
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    genesis_input = "_" * 40
    history_filename = f"{genesis_input}_{clean_hash}_{ts}.md"
    history_file = engine.history_dir / history_filename
    history_file.write_text(f"""---
type: "plan"
---
# A plan
""", "utf-8")

    status = engine.align()
    
    assert status == "CLEAN"
    assert engine.current_node is not None
    assert engine.current_node.output_tree == clean_hash
    assert engine.current_node.filename == history_file

def test_align_dirty_state(engine_setup):
    """
    测试场景：当工作区被修改，与任何历史节点都不匹配时，
    引擎应能正确识别为 "DIRTY" 状态。
    """
    engine, repo_path = engine_setup
    
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    past_hash = "a" * 40
    history_filename = f'{"_"*40}_{past_hash}_{ts}.md'
    (engine.history_dir / history_filename).write_text("---\ntype: plan\n---", "utf-8")
    
    (repo_path / "main.py").write_text("print('dirty state')", "utf-8")
    
    status = engine.align()
    
    assert status == "DIRTY"
    assert engine.current_node is None

def test_align_orphan_state(engine_setup):
    """
    测试场景：在一个没有 .quipu/history 目录或目录为空的项目中运行时，
    引擎应能正确识别为 "ORPHAN" 状态。
    """
    engine, repo_path = engine_setup
    
    (repo_path / "main.py").write_text("print('new project')", "utf-8")
    
    status = engine.align()
    
    assert status == "ORPHAN"
    assert engine.current_node is None

def test_capture_drift(engine_setup):
    """
    测试场景：当工作区处于 DIRTY 状态时，引擎应能成功捕获变化，
    创建一个新的 Capture 节点，并更新 Git 引用。
    """
    engine, repo_path = engine_setup
    
    (repo_path / "main.py").write_text("version = 1", "utf-8")
    initial_hash = engine.git_db.get_tree_hash()
    
    engine.writer.create_node("plan", "_" * 40, initial_hash, "Initial content")
    
    initial_commit = engine.git_db.create_anchor_commit(initial_hash, "Initial")
    engine.git_db.update_ref("refs/quipu/history", initial_commit)
    
    # 重新对齐以加载我们刚刚手动创建的节点
    engine.align()
    
    (repo_path / "main.py").write_text("version = 2", "utf-8")
    dirty_hash = engine.git_db.get_tree_hash()
    assert initial_hash != dirty_hash
    
    capture_node = engine.capture_drift(dirty_hash)
    
    assert len(engine.history_graph) == 2, "历史图谱中应有两个节点"
    assert engine.current_node is not None
    assert engine.current_node.output_tree == dirty_hash
    assert capture_node.node_type == "capture"
    assert capture_node.input_tree == initial_hash
    
    assert capture_node.filename.exists(), "捕获节点的 Markdown 文件应已创建"
    content = capture_node.filename.read_text("utf-8")
    assert "type: capture" in content
    assert "main.py" in content and "+-" in content, "捕获内容应包含 diff 摘要"

    latest_ref_commit = subprocess.check_output(
        ["git", "rev-parse", "refs/quipu/history"], cwd=repo_path
    ).decode().strip()
    assert latest_ref_commit != initial_commit, "Git 引用必须更新到新的锚点"
    
    parent_of_latest = subprocess.check_output(
        ["git", "rev-parse", f"{latest_ref_commit}^"], cwd=repo_path
    ).decode().strip()
    assert parent_of_latest == initial_commit

class TestPersistentIgnores:
    def test_sync_creates_file_if_not_exists(self, engine_setup):
        """测试：如果 exclude 文件不存在，应能根据默认配置创建它。"""
        engine, repo_path = engine_setup
        
        (repo_path / ".quipu").mkdir(exist_ok=True)
        
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, reader=engine.reader, writer=engine.writer)
        
        exclude_file = repo_path / ".git" / "info" / "exclude"
        assert exclude_file.exists()
        content = exclude_file.read_text("utf-8")
        
        assert "# --- Managed by Quipu ---" in content
        assert ".envs" in content

    def test_sync_appends_to_existing_file(self, engine_setup):
        """测试：如果 exclude 文件已存在，应追加 Quipu 块而不是覆盖。"""
        engine, repo_path = engine_setup
        
        exclude_file = repo_path / ".git" / "info" / "exclude"
        exclude_file.parent.mkdir(exist_ok=True)
        user_content = "# My personal ignores\n*.log\n"
        exclude_file.write_text(user_content)
        
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, reader=engine.reader, writer=engine.writer)
        
        content = exclude_file.read_text("utf-8")
        assert user_content in content
        assert "# --- Managed by Quipu ---" in content
        assert "o.md" in content

    def test_sync_updates_existing_block(self, engine_setup):
        """测试：如果 Quipu 块已存在，应更新其内容。"""
        engine, repo_path = engine_setup
        
        exclude_file = repo_path / ".git" / "info" / "exclude"
        exclude_file.parent.mkdir(exist_ok=True)
        
        old_block = (
            "# --- Managed by Quipu ---\n"
            "old_rule/\n"
            "# --- End Managed by Quipu ---"
        )
        user_content = f"# My ignores\n{old_block}\n# More ignores"
        exclude_file.write_text(user_content)
        
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, reader=engine.reader, writer=engine.writer)
        
        content = exclude_file.read_text("utf-8")
        assert "old_rule/" not in content
        assert ".vscode" in content
        assert "# My ignores" in content
        assert "# More ignores" in content

    def test_sync_uses_user_config(self, engine_setup):
        """测试：应优先使用 .quipu/config.yml 中的用户配置。"""
        import yaml
        engine, repo_path = engine_setup
        
        config_dir = repo_path / ".quipu"
        config_dir.mkdir(exist_ok=True)
        config_file = config_dir / "config.yml"
        
        user_ignores = {
            "sync": {
                "persistent_ignores": ["custom_dir/", "*.tmp"]
            }
        }
        config_file.write_text(yaml.dump(user_ignores), "utf-8")
        
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, reader=engine.reader, writer=engine.writer)
        
        exclude_file = repo_path / ".git" / "info" / "exclude"
        content = exclude_file.read_text("utf-8")
        
        assert "custom_dir/" in content
        assert "*.tmp" in content
        assert ".envs" not in content
~~~~~

~~~~~act
write_file
~~~~~

~~~~~path
tests/test_graph_loader.py
~~~~~

~~~~~python
import pytest
from pathlib import Path
from datetime import datetime
from typing import Dict
from quipu.core.history import load_all_history_nodes
from quipu.core.models import QuipuNode

@pytest.fixture
def graph_history_dir(tmp_path: Path) -> Path:
    """
    创建一个模拟的历史目录，包含一个分叉的图结构：
    A -> B
      -> C (C 比 B 新)
    """
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    
    hash_a = "a" * 40
    hash_b = "b" * 40
    hash_c = "c" * 40
    genesis = "_" * 40

    # 节点 A (根)
    (history_dir / f"{genesis}_{hash_a}_20230101000000.md").write_text("---\ntype: plan\n---")
    # 节点 B (A 的子节点)
    (history_dir / f"{hash_a}_{hash_b}_20230101010000.md").write_text("---\ntype: plan\n---")
    # 节点 C (A 的子节点, C is newer than B)
    (history_dir / f"{hash_a}_{hash_c}_20230101020000.md").write_text("---\ntype: plan\n---")
    
    return history_dir


class TestGraphLoader:

    def test_graph_loading_and_linking(self, graph_history_dir: Path):
        # `load_all_history_nodes` is now the main function for loading and linking
        all_nodes = load_all_history_nodes(graph_history_dir)
        
        # Rebuild the graph map for easy lookup, similar to how Engine does it.
        graph: Dict[str, QuipuNode] = {}
        for node in all_nodes:
            if node.output_tree not in graph or node.timestamp > graph[node.output_tree].timestamp:
                graph[node.output_tree] = node

        assert len(graph) == 3
        
        hash_a = "a" * 40
        hash_b = "b" * 40
        hash_c = "c" * 40
        
        node_a = graph[hash_a]
        node_b = graph[hash_b]
        node_c = graph[hash_c]
        
        # 1. 验证父子关系
        assert node_a.parent is None
        assert node_b.parent == node_a
        assert node_c.parent == node_a
        
        # 2. 验证子节点列表
        assert len(node_a.children) == 2
        # 验证子节点已按时间戳排序
        assert node_a.children == [node_b, node_c]
        assert len(node_b.children) == 0
        assert len(node_c.children) == 0
        
        # 3. 验证兄弟关系
        assert node_b.siblings == [node_b, node_c]
        assert node_c.siblings == [node_b, node_c]
        # 根节点没有兄弟
        assert node_a.siblings == [node_a]
~~~~~

### Acts 3: 插入缺失的 `storage.py` 导入

在重构 `main.py` 时，我意识到它也需要导入 `file_system_storage`。同时，`interfaces` 包中还没有 `storage.py` 文件，我需要添加它。

> 备注：此处的第一个操作在之前的计划中已定义，但为了确保原子性和可执行性，在此处重新显式声明。

~~~~~act
write_file
~~~~~

~~~~~path
packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~

~~~~~python
from abc import ABC, abstractmethod
from typing import List, Any
from .models import QuipuNode


class HistoryReader(ABC):
    """
    一个抽象接口，用于从存储后端读取历史图谱。
    """

    @abstractmethod
    def load_all_nodes(self) -> List[QuipuNode]:
        """
        从存储中加载所有历史事件，构建完整的父子关系图，
        并返回所有节点的列表。
        """
        pass


class HistoryWriter(ABC):
    """
    一个抽象接口，用于向历史存储后端写入一个新节点。
    """

    @abstractmethod
    def create_node(
        self,
        node_type: str,
        input_tree: str,
        output_tree: str,
        content: str,
        **kwargs: Any,
    ) -> QuipuNode:
        """
        在存储后端创建并持久化一个新的历史节点。

        Args:
            node_type: 节点的类型，例如 'plan' 或 'capture'。
            input_tree: 输入状态树的哈希。
            output_tree: 输出状态树的哈希。
            content: 节点的主要内容 (例如，Markdown 格式的计划) 。
            **kwargs: 针对特定节点类型的附加元数据，
                      例如 'capture' 节点的 'message'。

        Returns:
            新创建的 QuipuNode 实例。
        """
        pass
~~~~~