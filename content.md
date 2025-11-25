# feat: 实现时序性导航 (Back/Forward)

## 用户需求
用户需要一种能够撤销 `checkout` 操作的机制。现有的 `undo` 是基于图谱结构的向上移动，而用户希望像浏览器一样，能够按照操作时间顺序在访问过的历史状态间 `back` (后退) 和 `forward` (前进)。

## 评论
这是一个提升用户体验的关键功能，特别是当用户在复杂的历史图谱中跳转时，很容易迷失方向或误操作。引入浏览器式的导航历史管理是非常直观的解决方案。

## 目标
1.  在 `quipu-engine` 中实现访问历史记录管理（Log 和 Pointer）。
2.  在 `quipu-cli` 中新增 `back` 和 `forward` 命令。
3.  确保所有改变状态的操作 (`checkout`, `run`, `save` 等) 都能正确更新访问历史。

## 基本原理
在 `.quipu` 目录下维护 `nav_log` (访问过的 tree hash 列表) 和 `nav_ptr` (当前在列表中的索引)。
*   **Visit (新访问)**: 截断指针之后的历史，追加新状态，指针移到末尾。
*   **Back/Forward**: 仅移动指针并检出对应状态，不破坏历史记录。
*   **Integration**: 将此逻辑集成到 `Engine` 类中，并在 CLI 层替换直接的 `checkout` 调用。

## 标签
#feat #engine #cli #navigation

---

## Script

### Acts 1: Engine 增加 Navigation 支持

在 `Engine` 类中实现访问历史的存储、读取、追加和移动逻辑。并提供 `visit`, `back`, `forward` 高级接口。

~~~~~act
write_file packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~

~~~~~python
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import yaml
import re
from datetime import datetime

from .git_db import GitDB
from .history import load_history_graph
from .config import ConfigManager
from quipu.core.models import QuipuNode

logger = logging.getLogger(__name__)

class Engine:
    """
    Axon 状态引擎。
    负责协调 Git 物理状态和 Axon 逻辑图谱。
    """

    def _sync_persistent_ignores(self):
        """将 config.yml 中的持久化忽略规则同步到 .git/info/exclude。"""
        try:
            config = ConfigManager(self.root_dir)
            patterns = config.get("sync.persistent_ignores", [])
            if not patterns:
                return

            exclude_file = self.root_dir / ".git" / "info" / "exclude"
            exclude_file.parent.mkdir(exist_ok=True)

            header = "# --- Managed by Quipu ---"
            footer = "# --- End Managed by Quipu ---"
            
            content = ""
            if exclude_file.exists():
                content = exclude_file.read_text("utf-8")

            # 使用 re.DOTALL (s) 标志来匹配包括换行符在内的任何字符
            managed_block_pattern = re.compile(rf"{re.escape(header)}.*{re.escape(footer)}", re.DOTALL)
            
            new_block = f"{header}\n" + "\n".join(patterns) + f"\n{footer}"

            new_content, count = managed_block_pattern.subn(new_block, content)
            if count == 0:
                # 如果没有找到匹配项，则在末尾追加
                if content and not content.endswith("\n"):
                    content += "\n"
                new_content = content + "\n" + new_block + "\n"
            
            if new_content != content:
                exclude_file.write_text(new_content, "utf-8")
                logger.debug("✅ .git/info/exclude 已更新。")

        except Exception as e:
            logger.warning(f"⚠️  无法同步持久化忽略规则: {e}")

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.quipu_dir = self.root_dir / ".quipu"
        self.history_dir = self.quipu_dir / "history"
        self.head_file = self.quipu_dir / "HEAD"
        
        # Navigation History Files
        self.nav_log_file = self.quipu_dir / "nav_log"
        self.nav_ptr_file = self.quipu_dir / "nav_ptr"
        
        # 确保目录结构存在
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心：确保 .quipu 目录被 Git 忽略
        quipu_gitignore = self.quipu_dir / ".gitignore"
        if not quipu_gitignore.exists():
            try:
                quipu_gitignore.write_text("*\n", encoding="utf-8")
            except Exception as e:
                logger.warning(f"无法创建隔离文件 {quipu_gitignore}: {e}")
        
        self.git_db = GitDB(self.root_dir)
        self.history_graph: Dict[str, QuipuNode] = {}
        self.current_node: Optional[QuipuNode] = None

        # 自动同步本地配置，如持久化忽略规则
        self._sync_persistent_ignores()

    def _read_head(self) -> Optional[str]:
        """读取 .quipu/HEAD 文件中的 Hash"""
        if self.head_file.exists():
            return self.head_file.read_text(encoding="utf-8").strip()
        return None

    def _write_head(self, tree_hash: str):
        """更新 .quipu/HEAD"""
        try:
            self.head_file.write_text(tree_hash, encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️  无法更新 HEAD 指针: {e}")

    # --- Navigation History Logic ---

    def _read_nav(self) -> Tuple[List[str], int]:
        """读取导航日志和指针。如果文件不存在则返回空列表和-1。"""
        log = []
        ptr = -1
        
        if self.nav_log_file.exists():
            try:
                content = self.nav_log_file.read_text(encoding="utf-8").strip()
                if content:
                    log = content.splitlines()
            except Exception: pass
            
        if self.nav_ptr_file.exists():
            try:
                ptr = int(self.nav_ptr_file.read_text(encoding="utf-8").strip())
            except Exception: pass
            
        # 简单的完整性检查
        if not log:
            ptr = -1
        elif ptr < 0:
            ptr = 0
        elif ptr >= len(log):
            ptr = len(log) - 1
            
        return log, ptr

    def _write_nav(self, log: List[str], ptr: int):
        """写入导航日志和指针。"""
        try:
            self.nav_log_file.write_text("\n".join(log), encoding="utf-8")
            self.nav_ptr_file.write_text(str(ptr), encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️  无法更新导航历史: {e}")

    def _append_nav(self, tree_hash: str):
        """
        核心逻辑：访问新状态。
        1. 如果是全新的历史（空 log），且当前有 HEAD，先将当前 HEAD 记入（作为起点）。
        2. 截断当前指针之后的所有记录（类似浏览器访问新页面）。
        3. 追加新记录。
        4. 移动指针到末尾。
        """
        log, ptr = self._read_nav()
        
        # 处理初始化：如果 log 为空，但我们已经在某个状态了（比如 HEAD），应该把起点也记下来
        if not log:
            current_head = self._read_head()
            # 只有当 current_head 存在且不等于我们要去的新 hash 时才记录起点
            # 如果等于，说明是原地踏步或者初始化同步，直接记一个就行
            if current_head and current_head != tree_hash:
                log.append(current_head)
                ptr = 0
        
        # 截断历史
        if ptr < len(log) - 1:
            log = log[:ptr+1]
        
        # 避免连续重复记录 (Idempotency)
        if log and log[-1] == tree_hash:
            # 已经在目标状态，且是在末尾，不需要重复记录，但要确保指针正确
            ptr = len(log) - 1
            self._write_nav(log, ptr)
            return

        log.append(tree_hash)
        ptr = len(log) - 1
        
        # 可选：限制日志长度（例如保留最近 100 条）
        MAX_LOG_SIZE = 100
        if len(log) > MAX_LOG_SIZE:
            log = log[-MAX_LOG_SIZE:]
            ptr = len(log) - 1
            
        self._write_nav(log, ptr)

    # --- Public Navigation API ---

    def visit(self, target_hash: str):
        """
        高级导航：切换到目标状态，并将其记入访问历史。
        用于 checkout, undo, redo 等用户显式操作。
        """
        # 1. 先执行物理切换 (可能会失败)
        self.checkout(target_hash)
        # 2. 成功后记录历史
        self._append_nav(target_hash)

    def back(self) -> Optional[str]:
        """
        时序后退：移动指针到上一个记录，并切换状态。
        """
        log, ptr = self._read_nav()
        if ptr > 0:
            new_ptr = ptr - 1
            target_hash = log[new_ptr]
            
            logger.info(f"🔙 Back to: {target_hash[:7]} (History: {new_ptr + 1}/{len(log)})")
            self.checkout(target_hash)
            
            # 只有 checkout 成功才更新指针
            self._write_nav(log, new_ptr)
            return target_hash
        return None

    def forward(self) -> Optional[str]:
        """
        时序前进：移动指针到下一个记录，并切换状态。
        """
        log, ptr = self._read_nav()
        if ptr < len(log) - 1:
            new_ptr = ptr + 1
            target_hash = log[new_ptr]
            
            logger.info(f"🔜 Forward to: {target_hash[:7]} (History: {new_ptr + 1}/{len(log)})")
            self.checkout(target_hash)
            
            # 只有 checkout 成功才更新指针
            self._write_nav(log, new_ptr)
            return target_hash
        return None

    # --- Existing Methods ---

    def align(self) -> str:
        """
        核心对齐方法：确定 "我现在在哪"。
        返回状态: "CLEAN", "DIRTY", "ORPHAN"
        """
        # 1. 加载或重新加载历史
        self.history_graph = load_history_graph(self.history_dir)
        
        # 2. 获取当前物理状态
        current_hash = self.git_db.get_tree_hash()

        # 3. 特殊情况：处理创世状态 (空仓库)
        EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        if current_hash == EMPTY_TREE_HASH and not self.history_graph:
            logger.info("✅ 状态对齐：检测到创世状态 (空仓库)。")
            self.current_node = None
            # 创世状态不写入 HEAD，或者写入空？暂不写入。
            return "CLEAN"
        
        # 4. 在逻辑图谱中定位
        if current_hash in self.history_graph:
            self.current_node = self.history_graph[current_hash]
            logger.info(f"✅ 状态对齐：当前工作区匹配节点 {self.current_node.short_hash}")
            # 对齐成功，更新 HEAD
            self._write_head(current_hash)
            return "CLEAN"
        
        # 未找到匹配节点，进入漂移检测
        logger.warning(f"⚠️  状态漂移：当前 Tree Hash {current_hash[:7]} 未在历史中找到。")
        
        if not self.history_graph:
            return "ORPHAN" # 历史为空，但工作区非空
        
        return "DIRTY"

    def capture_drift(self, current_hash: str, message: Optional[str] = None) -> QuipuNode:
        """
        捕获当前工作区的漂移，生成一个新的 CaptureNode。
        """
        log_message = f"📸 正在捕获工作区漂移 (Message: {message})" if message else f"📸 正在捕获工作区漂移"
        logger.info(f"{log_message}，新状态 Hash: {current_hash[:7]}")

        # 1. 确定父节点 (input_tree)
        # 优先使用 HEAD 指针，其次尝试从历史中推断，最后回退到创世 Hash
        genesis_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        input_hash = genesis_hash
        
        head_hash = self._read_head()
        if head_hash and head_hash in self.history_graph:
            input_hash = head_hash
        elif self.history_graph:
            # Fallback: 使用时间戳最新的节点（风险：可能导致跳线，但在无 HEAD 时是唯一选择）
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            logger.warning(f"⚠️  丢失 HEAD 指针，自动回退到最新历史节点: {input_hash[:7]}")
        
        # 获取父 Commit 用于 Git 锚定
        last_commit_hash = None
        res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
        if res.returncode == 0:
            last_commit_hash = res.stdout.strip()

        # 2. 生成差异摘要
        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
        
        # 3. 构建节点内容和元数据
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_hash}_{current_hash}_{ts_str}.md"
        
        meta = {"type": "capture", "input_tree": input_hash, "output_tree": current_hash}
        
        user_message_section = f"### 💬 备注:\n{message}\n\n" if message else ""
        body = (
            f"# 📸 Snapshot Capture\n\n"
            f"{user_message_section}"
            f"检测到工作区发生变更。\n\n"
            f"### 📝 变更文件摘要:\n```\n{diff_summary}\n```"
        )
        
        # 4. 写入文件
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        filename.write_text(frontmatter + body, "utf-8")
        
        # 5. 创建锚点 Commit
        commit_msg = f"Axon Save: {message}" if message else f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else []
        new_commit_hash = self.git_db.create_anchor_commit(current_hash, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)

        # 6. 更新内存状态
        new_node = QuipuNode(
            input_tree=input_hash,
            output_tree=current_hash,
            timestamp=timestamp,
            filename=filename,
            node_type="capture",
            content=body
        )
        
        self.history_graph[current_hash] = new_node
        self.current_node = new_node
        
        # 7. 关键：更新 HEAD 指向新的捕获节点
        self._write_head(current_hash)
        
        # 8. 导航日志更新
        self._append_nav(current_hash)
        
        logger.info(f"✅ 捕获完成，新节点已创建: {filename.name}")
        return new_node

    def create_plan_node(self, input_tree: str, output_tree: str, plan_content: str) -> QuipuNode:
        """
        将一次成功的 Plan 执行固化为历史节点。
        """
        if input_tree == output_tree:
            logger.info(f"📝 记录幂等操作节点 (Idempotent Node): {output_tree[:7]}")
        else:
            logger.info(f"📝 正在记录 Plan 节点: {input_tree[:7]} -> {output_tree[:7]}")
        
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_tree}_{output_tree}_{ts_str}.md"
        
        meta = {
            "type": "plan",
            "input_tree": input_tree,
            "output_tree": output_tree
        }
        
        body = f"{plan_content.strip()}\n"
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        
        filename.write_text(frontmatter + body, "utf-8")
        
        # Git 锚定逻辑...
        parent_commit = None
        try:
            res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
            if res.returncode == 0:
                parent_commit = res.stdout.strip()
        except Exception: pass
            
        commit_msg = f"Axon Plan: {output_tree[:7]}"
        parents = [parent_commit] if parent_commit else []
        
        new_commit_hash = self.git_db.create_anchor_commit(output_tree, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)
        
        new_node = QuipuNode(
            input_tree=input_tree,
            output_tree=output_tree,
            timestamp=timestamp,
            filename=filename,
            node_type="plan",
            content=body
        )
        
        self.history_graph[output_tree] = new_node
        self.current_node = new_node
        
        # 关键：更新 HEAD
        self._write_head(output_tree)

        # 导航日志更新
        self._append_nav(output_tree)
        
        logger.info(f"✅ Plan 已归档: {filename.name}")
        return new_node

    def checkout(self, target_hash: str):
        """
        将工作区重置到指定状态，并更新 HEAD 指针。
        注意：此方法不负责更新导航日志，它是底层操作。
        """
        # 1. 执行物理检出
        self.git_db.checkout_tree(target_hash)
        
        # 2. 更新 HEAD 指针
        self._write_head(target_hash)
        
        # 3. 尝试更新内存中的当前节点状态
        if target_hash in self.history_graph:
            self.current_node = self.history_graph[target_hash]
        
        logger.info(f"🔄 状态已切换至: {target_hash[:7]}")
~~~~~

### Acts 2: CLI 增加 Back/Forward 命令并修改现有命令

在 `main.py` 中：
1.  新增 `back` 和 `forward` 命令。
2.  将 `checkout`, `discard`, `undo`, `redo`, `prev`, `next` 中调用 `engine.checkout` 的地方替换为 `engine.visit`。

~~~~~act
write_file packages/quipu-cli/src/quipu/cli/main.py
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
from quipu.core.history import load_history_graph
from quipu.core.models import QuipuNode
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
    
    from quipu.core.history import load_all_history_nodes, load_history_graph
    
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    all_nodes = load_all_history_nodes(engine.history_dir)
    
    if not all_nodes:
        typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
        ctx.exit(0)
        
    graph = load_history_graph(engine.history_dir)
    current_hash = engine.git_db.get_tree_hash()
    
    app_instance = QuipuUiApp(all_nodes, current_hash=current_hash)
    selected_hash = app_instance.run()

    if selected_hash:
        if selected_hash in graph:
            typer.secho(f"\n> TUI 请求检出到: {selected_hash[:7]}", err=True)
            # 使用 visit 替代子进程调用，更高效且能复用 Engine
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    status = engine.align()
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    history_dir = engine.history_dir
    graph = load_history_graph(history_dir)
    if not graph:
        typer.secho("❌ 错误: 找不到任何历史记录，无法确定要恢复到哪个状态。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    
    # 逻辑上，discard 应该是恢复到 HEAD 指向的 clean state，而不是时间上最新的。
    # 但如果 HEAD 丢失，回退到 max timestamp 也是一种策略。
    # 为了保持行为一致性，我们尝试读 HEAD
    target_tree_hash = engine._read_head()
    if not target_tree_hash or target_tree_hash not in graph:
        # Fallback
        latest_node = max(graph.values(), key=lambda n: n.timestamp)
        target_tree_hash = latest_node.output_tree
        typer.secho(f"⚠️  HEAD 指针丢失或无效，将恢复到最新历史节点: {latest_node.short_hash}", fg=typer.colors.YELLOW, err=True)
    else:
        latest_node = graph[target_tree_hash]

    current_hash = engine.git_db.get_tree_hash()
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已经是干净状态 ({latest_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)

    # 显示将要被丢弃的变更
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
        # 这里使用 visit 还是 checkout? 
        # Discard 也是一种状态重置，为了让 back 能撤销 discard，应该用 visit。
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    history_dir = engine.history_dir
    
    graph = load_history_graph(history_dir)
    matches = [node for sha, node in graph.items() if sha.startswith(hash_prefix)]
    if not matches:
        typer.secho(f"❌ 错误: 未找到哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    if len(matches) > 1:
        typer.secho(f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    target_node = matches[0]
    target_tree_hash = target_node.output_tree
    
    status = engine.align()
    current_hash = engine.git_db.get_tree_hash()
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已处于目标状态 ({target_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)
    if status in ["DIRTY", "ORPHAN"]:
        typer.secho("⚠️  检测到当前工作区存在未记录的变更，将自动创建捕获节点...", fg=typer.colors.YELLOW, err=True)
        engine.capture_drift(current_hash)
        typer.secho("✅ 变更已捕获。", fg=typer.colors.GREEN, err=True)
        # 捕获后，当前 hash 已更新，重新获取以确保 diff 准确
        current_hash = engine.git_db.get_tree_hash()

    # 显示将要发生的变更
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

    # 使用 visit 代替 checkout，记录访问历史
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    graph = load_history_graph(engine.history_dir)
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    graph = load_history_graph(engine.history_dir)
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    graph = load_history_graph(engine.history_dir)
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    graph = load_history_graph(engine.history_dir)
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    
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
    real_root = _resolve_root(work_dir)
    engine = Engine(real_root)
    
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
    real_root = _resolve_root(work_dir)
    history_dir = real_root / ".quipu" / "history"
    if not history_dir.exists():
        typer.secho(f"❌ 在 '{work_dir}' 中未找到 Axon 历史记录 (.quipu/history)。", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    graph = load_history_graph(history_dir)
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