# feat: Implement SQLite write-path and infrastructure

## 用户需求
执行开发路线图的第二步：实现 SQLite 存储后端。此阶段将专注于建立 SQLite 基础设施和改造写入路径，以实现对 Git 和 SQLite 的“双写”。

## 评论
这是向混合存储模型迈出的实质性一步。通过实现双写，我们可以在不影响现有读取逻辑（仍然从 Git 读取）的情况下，安全地在后台开始填充 SQLite 数据库。这种增量方法将风险降至最低，并为下一阶段（切换读取路径和实现补水机制）奠定了坚实的基础。

## 目标
1.  建立管理 `.quipu/history.sqlite` 数据库的基础设施，包括连接和 Schema 初始化。
2.  创建一个新的 `SQLiteHistoryWriter`，它能够首先将历史节点写入 Git，然后将元数据和图关系写入 SQLite。
3.  更新系统的工厂函数，使其能够根据配置选择性地启用新的写入器。
4.  确保在启用新后端后，现有的创建节点流程（如 `quipu run`）能够正确地在两个存储层中创建数据。

## 基本原理
我们遵循“接口先行，增量实现”的策略。
1.  **配置驱动**：在 `.quipu/config.yml` 中引入 `storage.type` 选项，允许用户显式选择 `sqlite` 后端。默认值仍为 `git_object` 以保证向后兼容。
2.  **组合优于继承**：新的 `SQLiteHistoryWriter` 将组合（contain）一个 `GitObjectHistoryWriter` 实例。它首先委托 `GitObjectHistoryWriter` 完成向 Git 写入的所有工作，成功后再执行向 SQLite 写入的逻辑。这最大限度地重用了现有且经过测试的代码。
3.  **读写分离**：在此阶段，我们只替换**写入器**。读取器 (`HistoryReader`) 仍然使用 `GitObjectHistoryReader`。这意味着系统的查询和读取行为暂时保持不变，但所有新的写入操作都会开始填充 SQLite 数据库。

## 标签
#intent/build #flow/ready #priority/high
#comp/engine #comp/cli #concept/state #concept/history #scope/core
#ai/instruct
#task/domain/storage #task/object/sqlite-backend #task/action/integration
#task/state/continue #task/status/active

---

## Script

### Acts 1: 配置与工厂改造

首先，我们将更新配置系统以识别新的存储类型，并改造工厂函数 `create_engine` 以根据配置选择不同的写入器。

~~~~~act
replace packages/quipu-engine/src/quipu/core/config.py
~~~~~
~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "storage": {
        "type": "git_object",
    },
    "sync": {
        "remote_name": "origin",
        "persistent_ignores": [".idea", ".vscode", ".envs", "__pycache__", "node_modules", "o.md"],
    },
    "list_files": {"ignore_patterns": [".git", "__pycache__", ".idea", ".vscode", "node_modules", ".quipu"]},
}
~~~~~
~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "storage": {
        "type": "git_object",  # 可选: "git_object", "sqlite"
    },
    "sync": {
        "remote_name": "origin",
        "persistent_ignores": [".idea", ".vscode", ".envs", "__pycache__", "node_modules", "o.md"],
    },
    "list_files": {"ignore_patterns": [".git", "__pycache__", ".idea", ".vscode", "node_modules", ".quipu"]},
}
~~~~~

~~~~~act
replace packages/quipu-cli/src/quipu/cli/factory.py
~~~~~
~~~~~python
import logging
from pathlib import Path
from typing import Optional

from quipu.core.state_machine import Engine
from quipu.core.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.core.git_db import GitDB
from quipu.core.config import ConfigManager
from .utils import find_git_repository_root

logger = logging.getLogger(__name__)


def create_engine(work_dir: Path) -> Engine:
    """
    实例化完整的 Engine 堆栈。

    会自动向上查找项目根目录 (Git Root) 来初始化 Engine。
    如果找不到 Git Root，则回退到 work_dir。
    此工厂现在由配置驱动，以决定使用何种存储后端。
    """
    # 1. 尝试查找真正的项目根目录 (包含 .git 的目录)
    project_root = find_git_repository_root(work_dir)
    if not project_root:
        project_root = work_dir

    # 2. 加载配置
    config = ConfigManager(project_root)
    storage_type = config.get("storage.type", "git_object")

    # 3. 创建 GitDB 实例，这是多种存储格式可能共用的基础
    git_db = GitDB(project_root)

    # 4. 根据配置选择存储后端
    if storage_type == "git_object":
        logger.debug("Using Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)
    else:
        # 未来可以扩展其他类型，例如 file_system, sqlite
        raise NotImplementedError(f"Storage type '{storage_type}' is not supported.")

    # 5. 注入依赖并实例化 Engine
    engine = Engine(project_root, db=git_db, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱

    return engine
~~~~~
~~~~~python
import logging
from pathlib import Path
from typing import Optional

from quipu.core.state_machine import Engine
from quipu.core.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.core.git_db import GitDB
from quipu.core.config import ConfigManager
from .utils import find_git_repository_root

# 迟延导入以避免循环依赖
try:
    from quipu.core.sqlite_db import DatabaseManager
    from quipu.core.sqlite_storage import SQLiteHistoryWriter
except ImportError:
    DatabaseManager = None
    SQLiteHistoryWriter = None


logger = logging.getLogger(__name__)


def create_engine(work_dir: Path) -> Engine:
    """
    实例化完整的 Engine 堆栈。

    会自动向上查找项目根目录 (Git Root) 来初始化 Engine。
    此工厂由配置驱动，以决定使用何种存储后端。
    """
    project_root = find_git_repository_root(work_dir) or work_dir
    config = ConfigManager(project_root)
    storage_type = config.get("storage.type", "git_object")
    git_db = GitDB(project_root)

    # 默认和备用后端
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)

    if storage_type == "sqlite":
        if not DatabaseManager or not SQLiteHistoryWriter:
            raise ImportError("SQLite dependencies could not be loaded. Please check your installation.")

        logger.debug("Using SQLite storage format for writes.")
        db_manager = DatabaseManager(project_root)
        db_manager.init_schema()

        # **关键**: 写入路径被替换，读取路径保持不变
        # 这允许我们在后台安全地填充数据库，而不影响现有功能
        writer = SQLiteHistoryWriter(git_writer=writer, db_manager=db_manager)

    elif storage_type != "git_object":
        raise NotImplementedError(f"Storage type '{storage_type}' is not supported.")

    engine = Engine(project_root, db=git_db, reader=reader, writer=writer)
    engine.align()

    return engine
~~~~~

### Acts 2: 数据库基础设施

接下来，我们创建 `sqlite_db.py`，它将负责所有底层的数据库交互，包括连接管理和 Schema 创建，严格遵循 QLDS v1.0 规范。

~~~~~act
write_file packages/quipu-engine/src/quipu/core/sqlite_db.py
~~~~~
~~~~~python
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    管理 SQLite 数据库连接和 Schema。
    """

    def __init__(self, work_dir: Path):
        self.db_path = work_dir / ".quipu" / "history.sqlite"
        self.db_path.parent.mkdir(exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接，如果不存在则创建。"""
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                # 开启外键约束
                self._conn.execute("PRAGMA foreign_keys = ON;")
                logger.debug(f"🗃️  成功连接到数据库: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"❌ 数据库连接失败: {e}")
                raise
        return self._conn

    def close(self):
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("🗃️  数据库连接已关闭。")

    def init_schema(self):
        """
        初始化数据库 Schema，如果表不存在则创建。
        符合 QLDS v1.0 规范。
        """
        conn = self._get_conn()
        try:
            with conn:
                # nodes 表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nodes (
                        commit_hash TEXT(40) PRIMARY KEY,
                        output_tree TEXT(40) NOT NULL,
                        node_type TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        summary TEXT NOT NULL,
                        generator_id TEXT,
                        meta_json TEXT NOT NULL,
                        plan_md_cache TEXT
                    );
                    """
                )
                # 索引
                conn.execute("CREATE INDEX IF NOT EXISTS IDX_nodes_timestamp ON nodes(timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS IDX_nodes_output_tree ON nodes(output_tree);")

                # edges 表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS edges (
                        child_hash TEXT(40) NOT NULL,
                        parent_hash TEXT(40) NOT NULL,
                        PRIMARY KEY (child_hash, parent_hash),
                        FOREIGN KEY (child_hash) REFERENCES nodes(commit_hash) ON DELETE CASCADE,
                        FOREIGN KEY (parent_hash) REFERENCES nodes(commit_hash) ON DELETE CASCADE
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS IDX_edges_parent ON edges(parent_hash);")

                # private_data 表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS private_data (
                        node_hash TEXT(40) PRIMARY KEY,
                        intent_md TEXT,
                        ai_context TEXT,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        FOREIGN KEY (node_hash) REFERENCES nodes(commit_hash) ON DELETE CASCADE
                    );
                    """
                )
            logger.debug("✅ 数据库 Schema 已初始化/验证。")
        except sqlite3.Error as e:
            logger.error(f"❌ 初始化 Schema 失败: {e}")
            raise

    def execute_write(self, sql: str, params: tuple = ()):
        """执行写操作的通用方法。"""
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(sql, params)
        except sqlite3.Error as e:
            logger.error(f"❌ 数据库写入失败: {e} | SQL: {sql}")
            raise
~~~~~

### Acts 3: 实现 SQLite 写入器

现在我们创建 `sqlite_storage.py`，实现 `SQLiteHistoryWriter`。它将封装双写逻辑。

~~~~~act
write_file packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
import json
import logging
from typing import Any

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader, HistoryWriter
from quipu.core.git_object_storage import GitObjectHistoryWriter
from .sqlite_db import DatabaseManager

logger = logging.getLogger(__name__)


class SQLiteHistoryWriter(HistoryWriter):
    """
    一个实现“双写”的历史写入器。
    1. 委托 GitObjectHistoryWriter 将节点写入 Git。
    2. 将元数据和关系写入 SQLite。
    """

    def __init__(self, git_writer: GitObjectHistoryWriter, db_manager: DatabaseManager):
        self.git_writer = git_writer
        self.db_manager = db_manager

    def create_node(
        self,
        node_type: str,
        input_tree: str,
        output_tree: str,
        content: str,
        **kwargs: Any,
    ) -> QuipuNode:
        # 步骤 1: 调用底层 Git 写入器创建 Git Commit
        # 它会返回一个包含所有必要信息的 QuipuNode 实例
        git_node = self.git_writer.create_node(
            node_type, input_tree, output_tree, content, **kwargs
        )
        commit_hash = git_node.filename.name

        # 步骤 2: 将元数据写入 SQLite
        try:
            # 2.1 提取元数据 (从 Git 写入器内部逻辑中获取)
            # 这部分有些重复，未来可以优化 writer 的返回值
            start_time = kwargs.get("start_time", git_node.timestamp.timestamp())
            summary = self.git_writer._generate_summary(
                node_type, content, input_tree, output_tree, **kwargs
            )
            metadata = {
                "meta_version": "1.0",
                "summary": summary,
                "type": node_type,
                "generator": self.git_writer._get_generator_info(),
                "env": self.git_writer._get_env_info(),
                "exec": {"start": start_time, "duration_ms": 0}, # 持续时间暂时无法精确计算
            }
            meta_json_str = json.dumps(metadata)

            # 2.2 写入 'nodes' 表
            self.db_manager.execute_write(
                """
                INSERT OR REPLACE INTO nodes 
                (commit_hash, output_tree, node_type, timestamp, summary, generator_id, meta_json, plan_md_cache)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_hash,
                    output_tree,
                    node_type,
                    start_time,
                    summary,
                    metadata["generator"]["id"],
                    meta_json_str,
                    content,  # 热缓存: 新创建的节点内容直接写入缓存
                ),
            )

            # 2.3 写入 'edges' 表
            parent_commit = self.git_writer.git_db.get_commit_by_output_tree(input_tree)
            if parent_commit:
                self.db_manager.execute_write(
                    "INSERT OR IGNORE INTO edges (child_hash, parent_hash) VALUES (?, ?)",
                    (commit_hash, parent_commit),
                )
            
            # 2.4 (未来) 写入 'private_data' 表
            # intent = kwargs.get("intent_md")
            # if intent: ...

            logger.debug(f"✅ 节点元数据 {commit_hash[:7]} 已写入 SQLite。")

        except Exception as e:
            # 关键：如果数据库写入失败，我们不能回滚 Git 提交，
            # 但必须记录一个严重警告，提示需要进行数据补水。
            logger.error(f"⚠️  严重: Git 节点 {commit_hash[:7]} 已创建，但写入 SQLite 失败: {e}")
            logger.warning("   -> 下次启动或 `sync` 时将通过补水机制修复。")

        # 无论数据库写入是否成功，都返回从 Git 创建的节点
        return git_node
~~~~~

### Acts 4: 添加测试

最后，我们添加一个新的测试文件来验证新的 SQLite 写入路径是否按预期工作。

~~~~~act
write_file tests/test_sqlite_writer.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path

from quipu.cli.controller import run_quipu
from quipu.core.sqlite_db import DatabaseManager

PLAN_A = """
```act
write_file a.txt
```
```content
File A content
```
"""

@pytest.fixture
def sqlite_workspace(tmp_path: Path) -> Path:
    """创建一个配置为使用 SQLite 后端的 Git 工作区。"""
    ws = tmp_path / "ws_sqlite"
    ws.mkdir()
    
    # Init Git
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=ws, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=ws, check=True)

    # Init Quipu config for SQLite
    quipu_dir = ws / ".quipu"
    quipu_dir.mkdir()
    (quipu_dir / "config.yml").write_text("storage:\n  type: sqlite\n")
    
    return ws

class TestSQLiteWriterIntegration:
    def test_dual_write_on_run(self, sqlite_workspace):
        """
        验证 `quipu run` 在 SQLite 模式下是否能正确地双写到 Git 和 DB。
        """
        # --- Action ---
        result = run_quipu(PLAN_A, work_dir=sqlite_workspace, yolo=True)
        assert result.success, f"run_quipu failed: {result.message}"

        # --- Verification ---
        
        # 1. Verify Git Commit was created
        git_log = subprocess.check_output(
            ["git", "log", "--all", "--format=%H"], cwd=sqlite_workspace, text=True
        ).strip()
        assert len(git_log) > 0, "Git log should not be empty"
        commit_hash = git_log.splitlines()[0]

        # 2. Verify SQLite DB was created and populated
        db_path = sqlite_workspace / ".quipu" / "history.sqlite"
        assert db_path.exists()

        db = DatabaseManager(sqlite_workspace)
        conn = db._get_conn()
        
        # Check nodes table
        cursor = conn.execute("SELECT * FROM nodes WHERE commit_hash = ?", (commit_hash,))
        node_row = cursor.fetchone()
        assert node_row is not None
        assert node_row["summary"] == "Write: a.txt"
        assert node_row["node_type"] == "plan"
        assert node_row["plan_md_cache"] is not None # Should be hot-cached

        # Check edges table (for the second commit)
        (sqlite_workspace / "b.txt").touch()
        run_quipu("```act\nend\n```", work_dir=sqlite_workspace, yolo=True)
        
        git_log_2 = subprocess.check_output(
            ["git", "log", "--all", "--format=%H"], cwd=sqlite_workspace, text=True
        ).strip()
        commit_hash_2 = git_log_2.splitlines()[0]
        
        cursor_edge = conn.execute("SELECT * FROM edges WHERE child_hash = ?", (commit_hash_2,))
        edge_row = cursor_edge.fetchone()
        assert edge_row is not None
        assert edge_row["parent_hash"] == commit_hash
        
        db.close()
~~~~~
