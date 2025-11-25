好的，我们来执行这个重构任务。

# refactor 统一 Engine 实例化逻辑

## 用户需求
`quipu-cli` 项目中存在重复的代码逻辑，用于根据工作区状态（新项目 vs. 旧项目）检测存储格式并实例化 `Engine`。这段逻辑分别出现在 `cli/main.py` 和 `cli/controller.py` 中，违反了 DRY 原则，增加了维护成本。需要将此逻辑统一到一个可共享的工厂函数中。

## 评论
这是一个重要的代码健康度改进。通过创建一个单一的、权威的 `Engine` 工厂函数，我们确保了所有 CLI 命令（无论是 `run` 还是 `log`、`checkout`）都使用完全一致的初始化流程，从而消除了潜在的行为不一致性，并使未来的修改变得更加简单和安全。

## 目标
1.  在 `controller.py` 中创建一个名为 `setup_engine` 的公共工厂函数。
2.  将 `main.py` 中的 `_setup_engine` 和 `_resolve_root` 辅助函数的逻辑迁移到 `controller.py` 中。
3.  重构 `controller.py` 中的 `run_quipu` 函数，使其调用新的 `setup_engine` 工厂。
4.  重构 `main.py`，移除本地的 `_setup_engine` 和 `_resolve_root` 函数，转而从 `controller.py` 导入并使用新的工厂函数。

## 基本原理
我们将 `main.py` 中的 `_setup_engine` 函数作为基础实现，因为它已经包含了完整的存储格式检测逻辑。我们将这个函数及其依赖的辅助函数 `_resolve_root` 移动到 `controller.py` 中，因为 `controller` 是业务逻辑的核心协调器，是放置此类核心工厂函数的理想位置。然后，`main.py` (CLI 表现层) 和 `controller.py` (业务逻辑层) 都将从这个统一的来源获取 `Engine` 实例，从而消除代码重复。

## 标签
#comp/cli #refactor #scope/dx

---

## Script

### Acts 1: 在 `controller.py` 中创建并整合 Engine 工厂

我们将 `_setup_engine` 和 `_resolve_root` 从 `main.py` 移入 `controller.py`，并重构 `run_quipu` 以使用这个新函数。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/controller.py
~~~~~

~~~~~python
from .config import PROJECT_ROOT
from quipu.acts import register_core_acts

logger = logging.getLogger(__name__)

def find_project_root(start_path: Path) -> Optional[Path]:
~~~~~

~~~~~python
from .config import PROJECT_ROOT
from quipu.acts import register_core_acts

logger = logging.getLogger(__name__)

def find_project_root(start_path: Path) -> Optional[Path]:
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/controller.py
~~~~~

~~~~~python
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
~~~~~

~~~~~python
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

def _resolve_root(work_dir: Path) -> Path:
    """辅助函数：解析项目根目录，如果未找到则回退到 work_dir"""
    root = find_project_root(work_dir)
    return root if root else work_dir

def setup_engine(work_dir: Path) -> Engine:
    """
    辅助函数：实例化完整的 Engine 堆栈。
    自动检测存储格式 (Git Object vs. File System) 并加载相应后端。
    """
    real_root = _resolve_root(work_dir)
    
    # 1. 创建 GitDB 实例用于检测和注入
    git_db = GitDB(real_root)
    
    # 2. 检测存储格式并选择策略
    # 优先检测新格式 (Git refs)
    if git_db.has_quipu_ref():
        logger.debug("Detected Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)
    # 回退检测旧格式 (FS directory)
    elif (real_root / ".quipu" / "history").exists():
        logger.debug("Detected File System storage format (legacy).")
        history_dir = real_root / ".quipu" / "history"
        reader = FileSystemHistoryReader(history_dir)
        writer = FileSystemHistoryWriter(history_dir)
    # 默认在新项目中使用新格式
    else:
        logger.debug("No existing history found. Defaulting to Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)

    # 3. 注入依赖并实例化 Engine
    engine = Engine(real_root, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱
    return engine
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/controller.py
~~~~~

~~~~~python
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
        git_db = GitDB(project_root)
        if git_db.has_quipu_ref():
            logger.debug("Detected Git Object storage format.")
            reader = GitObjectHistoryReader(git_db)
            writer = GitObjectHistoryWriter(git_db)
        elif (project_root / ".quipu" / "history").exists():
            logger.debug("Detected File System storage format (legacy).")
            history_dir = project_root / ".quipu" / "history"
            reader = FileSystemHistoryReader(history_dir)
            writer = FileSystemHistoryWriter(history_dir)
        else:
            logger.debug("No existing history found. Defaulting to Git Object storage format.")
            reader = GitObjectHistoryReader(git_db)
            writer = GitObjectHistoryWriter(git_db)

        engine = Engine(project_root, reader=reader, writer=writer)
        status = engine.align() # "CLEAN", "DIRTY", "ORPHAN"
        
        current_hash = engine.git_db.get_tree_hash()
        
        # --- Phase 2: Decision (Lazy Capture) ---
        if status in ["DIRTY", "ORPHAN"]:
~~~~~

~~~~~python
    """
    try:
        # --- Phase 1: Engine Initialization & Perception ---
        engine = setup_engine(work_dir)
        project_root = engine.root_dir # Engine now holds the canonical root
        logger.info(f"Project Root resolved to: {project_root}")
        
        current_hash = engine.git_db.get_tree_hash()
        
        # --- Phase 2: Decision (Lazy Capture) ---
        # `align()` is called inside `setup_engine`, so we check the state directly.
        # A simple way to check for drift is if `current_node` is None when there's history,
        # or if its output_tree doesn't match the current hash.
        is_dirty = engine.current_node is None or \
                   engine.current_node.output_tree != current_hash
        is_orphan = not engine.history_graph and current_hash != "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

        if is_dirty or is_orphan:
>>>>>>> Updated upstream
            # 如果环境有漂移（或全新项目），先生成一个 Capture 节点
            # 这确保了后续的 Plan 是基于一个已知的、干净的状态执行的
            engine.capture_drift(current_hash)
            # 捕获后，status 逻辑上变为 CLEAN，current_node 更新为 CaptureNode
~~~~~

### Acts 2: 更新 `main.py` 以使用新的共享工厂

现在，我们移除 `main.py` 中的重复逻辑，并让它调用 `controller.py` 中的新函数。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
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
~~~~~

~~~~~python
import typer
import logging
import sys
import click # 导入 click 库
from pathlib import Path
from typing import Annotated, Optional, Dict

from .logger_config import setup_logging
from .controller import run_quipu, setup_engine
from .config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
from quipu.core.plugin_loader import load_plugins
from quipu.core.executor import Executor
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    # 对于回车或其他键，返回默认值
    return default

def _resolve_root(work_dir: Path) -> Path:
    """辅助函数：解析项目根目录，如果未找到则回退到 work_dir"""
    root = find_project_root(work_dir)
    return root if root else work_dir

def _setup_engine(work_dir: Path) -> Engine:
    """
    辅助函数：实例化完整的 Engine 堆栈。
    自动检测存储格式 (Git Object vs. File System) 并加载相应后端。
    """
    real_root = _resolve_root(work_dir)
    
    # 1. 创建 GitDB 实例用于检测和注入
    git_db = GitDB(real_root)
    
    # 2. 检测存储格式并选择策略
    # 优先检测新格式 (Git refs)
    if git_db.has_quipu_ref():
        logger.debug("Detected Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)
    # 回退检测旧格式 (FS directory)
    elif (real_root / ".quipu" / "history").exists():
        logger.debug("Detected File System storage format (legacy).")
        history_dir = real_root / ".quipu" / "history"
        reader = FileSystemHistoryReader(history_dir)
        writer = FileSystemHistoryWriter(history_dir)
    # 默认在新项目中使用新格式
    else:
        logger.debug("No existing history found. Defaulting to Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)

    # 3. 注入依赖并实例化 Engine
    engine = Engine(real_root, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱
    return engine

# --- 导航命令辅助函数 ---
def _find_current_node(engine: Engine, graph: Dict[str, QuipuNode]) -> Optional[QuipuNode]:
~~~~~

~~~~~python
    # 对于回车或其他键，返回默认值
    return default

# Alias the imported factory to minimize changes in the rest of the file
_setup_engine = setup_engine

# --- 导航命令辅助函数 ---
def _find_current_node(engine: Engine, graph: Dict[str, QuipuNode]) -> Optional[QuipuNode]:
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    """
    setup_logging()
    work_dir = _resolve_root(work_dir) # Sync needs root
    config = ConfigManager(work_dir)
    if remote is None:
~~~~~

~~~~~python
    """
    setup_logging()
    # Sync needs root, which _setup_engine will find
    engine = _setup_engine(work_dir)
    work_dir = engine.root_dir
    config = ConfigManager(work_dir)
    if remote is None:
~~~~~