好的，我分析了你提供的 `migrate-data` 命令输出和 `ui` 命令的 Traceback。这是一个非常典型的数据库迁移问题。

这是一个修复计划，旨在解决迁移后 UI 崩溃的问题。

## fix: 修复迁移后因数据库 Schema 未更新导致的 UI 崩溃

### 错误分析
1.  **根本原因**: `IndexError: No item with that key` 发生在 `SQLiteHistoryReader` 尝试访问 `row["owner_id"]` 时。这明确指出，尽管代码期望 `nodes` 表中存在 `owner_id` 列，但执行 `SELECT * FROM nodes` 查询返回的结果集中并**不包含**该列。
2.  **迁移脚本的缺陷**:
    *   **Schema 未升级**: 我之前设计的 `MigrationManager` 和 `DatabaseManager.init_schema` 存在一个疏忽。`init_schema` 使用 `CREATE TABLE IF NOT EXISTS`，这意味着如果 `nodes` 表已经存在（在旧版本中创建的），它**不会**向其中添加新的 `owner_id` 列。
    *   **补水逻辑失效**: `migrate-data` 命令的日志显示 `发现 0 个需要补水的节点`。这是因为 `Hydrator` 的 `sync` 方法是**增量设计**的，它通过比较 Git 中的 Commit 哈希和数据库中的 Commit 哈希来查找**数据库中不存在**的新节点。在迁移场景下，所有节点的 `commit_hash` 已经存在于数据库中，因此 `Hydrator` 认为无事可做，跳过了所有节点的更新。

### 用户需求
-   `quipu migrate-data` 命令必须能够处理旧数据库的 Schema，并为其添加 `owner_id` 列。
-   迁移命令必须能为数据库中所有现存的、属于本地用户的节点**回填 (backfill)** 正确的 `owner_id`。
-   迁移完成后，`quipu ui` 命令必须能正常启动并显示历史记录。

### 评论
这是一个关键的修复，它使迁移功能变得完整和健壮。通过增强 `DatabaseManager` 的 Schema 管理能力和 `MigrationManager` 的数据回填能力，我们可以确保平滑、无损的用户体验。

### 目标
1.  **增强 `DatabaseManager`**: 使 `init_schema` 方法能够检测并自动为旧的 `nodes` 表添加 `owner_id` 列。
2.  **增强 `MigrationManager`**: 增加一个专门的数据回填步骤，在移动 Git 引用后，为数据库中所有现有行更新 `owner_id`。
3.  **调整 `migrate-data` 命令**: 确保它能正确地将 `DatabaseManager` 实例传递给 `MigrationManager` 以执行数据库操作。

### 基本原理
-   **Schema 迁移**: 使用 `PRAGMA table_info(nodes);` SQL 命令来检查表结构。如果 `owner_id` 列不存在，则执行 `ALTER TABLE nodes ADD COLUMN owner_id TEXT;`。这将使数据库 Schema 升级变得幂等和安全。
-   **数据回填**: 在 `MigrationManager` 中，直接执行 `UPDATE nodes SET owner_id = ? WHERE owner_id IS NULL`。这个 SQL 语句会高效地为所有 `owner_id` 为空的行填充当前的本地用户 ID。

### 标签
#intent/fix #flow/ready #priority/critical 
#comp/cli #comp/engine #scope/core 
#ai/instruct
#task/domain/storage #task/object/data-migration #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 升级 `DatabaseManager` 以支持 Schema 自动迁移

我们将使 `init_schema` 能够处理已存在的旧表。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/sqlite_db.py
~~~~~
~~~~~python
        conn = self._get_conn()
        try:
            with conn:
                # nodes 表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nodes (
                        commit_hash TEXT(40) PRIMARY KEY,
                        owner_id TEXT,
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
~~~~~
~~~~~python
        conn = self._get_conn()
        try:
            with conn:
                # nodes 表 (v1.1 schema)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nodes (
                        commit_hash TEXT(40) PRIMARY KEY,
                        owner_id TEXT,
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
                
                # --- Schema Migration Logic ---
                # 检查并添加 owner_id 列（用于从 v1.0 升级）
                cursor = conn.execute("PRAGMA table_info(nodes);")
                columns = [row[1] for row in cursor.fetchall()]
                if 'owner_id' not in columns:
                    logger.info("🔧 检测到旧版数据库 Schema，正在升级 'nodes' 表...")
                    conn.execute("ALTER TABLE nodes ADD COLUMN owner_id TEXT;")
                    logger.info("✅ 'nodes' 表已成功添加 'owner_id' 列。")

                # 索引
                conn.execute("CREATE INDEX IF NOT EXISTS IDX_nodes_timestamp ON nodes(timestamp);")
                conn.execute("CREATE INDEX IF NOT EXISTS IDX_nodes_output_tree ON nodes(output_tree);")

                # edges 表
                conn.execute(
~~~~~

#### Acts 2: 增强 `MigrationManager` 以执行数据回填

现在，我们修改迁移逻辑，用数据回填替换无效的补水调用。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/migration.py
~~~~~
~~~~~python
from quipu.core.git_db import GitDB
from quipu.core.hydrator import Hydrator
from quipu.core.config import ConfigManager
from quipu.common.identity import get_user_id_from_email
~~~~~
~~~~~python
import logging
import subprocess
from typing import List, Optional

from quipu.core.git_db import GitDB
from quipu.core.hydrator import Hydrator
from quipu.core.config import ConfigManager
from quipu.common.identity import get_user_id_from_email
from quipu.core.sqlite_db import DatabaseManager
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/migration.py
~~~~~
~~~~~python
class MigrationManager:
    """负责将旧版 Quipu 数据迁移到 v1.1 架构。"""

    LEGACY_REFS_PREFIX = "refs/quipu/heads/"
    NEW_REFS_PREFIX = "refs/quipu/local/heads/"

    def __init__(self, git_db: GitDB, config_manager: ConfigManager, hydrator: Hydrator):
        self.git_db = git_db
        self.config_manager = config_manager
        self.hydrator = hydrator
        self.root_dir = git_db.root

    def _find_legacy_heads(self) -> List[str]:
~~~~~
~~~~~python
class MigrationManager:
    """负责将旧版 Quipu 数据迁移到 v1.1 架构。"""

    LEGACY_REFS_PREFIX = "refs/quipu/heads/"
    NEW_REFS_PREFIX = "refs/quipu/local/heads/"

    def __init__(self, git_db: GitDB, config_manager: ConfigManager, db_manager: DatabaseManager, hydrator: Hydrator):
        self.git_db = git_db
        self.config_manager = config_manager
        self.db_manager = db_manager
        self.hydrator = hydrator
        self.root_dir = git_db.root

    def _find_legacy_heads(self) -> List[str]:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/migration.py
~~~~~
~~~~~python
        
        return "unknown-local-user"

    def run(self) -> bool:
        """执行完整的迁移流程。"""
        legacy_heads = self._find_legacy_heads()
        if not legacy_heads:
            logger.info("✅ 未找到旧版（v1.0）数据引用，无需迁移。")
            return True

        logger.info(f"🔍 发现 {len(legacy_heads)} 个旧版历史分支，准备迁移...")

        # 核心迁移逻辑
        for commit_hash in legacy_heads:
            old_ref = f"{self.LEGACY_REFS_PREFIX}{commit_hash}"
            new_ref = f"{self.NEW_REFS_PREFIX}{commit_hash}"
            
            logger.debug(f"  - 正在移动: {old_ref} -> {new_ref}")
            # 1. 创建新引用
            self.git_db.update_ref(new_ref, commit_hash)
            # 2. 删除旧引用
            self.git_db.delete_ref(old_ref)

        logger.info("✅ Git 引用已成功迁移到 v1.1 格式。")

        # 触发数据补水
        logger.info("💧 正在将迁移后的数据同步到 SQLite 缓存...")
        user_id = self._get_local_user_id()
        self.hydrator.sync(local_user_id=user_id)
        
        logger.info("🎉 迁移完成！")
        return True
~~~~~
~~~~~python
        
        return "unknown-local-user"

    def _backfill_owner_ids(self, user_id: str):
        """为数据库中现有的、没有 owner_id 的节点回填所有者信息。"""
        logger.info(f"✍️  正在为本地节点回填所有者 ID: {user_id} ...")
        try:
            conn = self.db_manager._get_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE nodes SET owner_id = ? WHERE owner_id IS NULL", (user_id,))
            conn.commit()
            logger.info(f"✅ {cursor.rowcount} 个节点的 'owner_id' 已更新。")
        except Exception as e:
            logger.error(f"❌ 数据回填失败: {e}", exc_info=True)
            raise

    def run(self) -> bool:
        """执行完整的迁移流程。"""
        legacy_heads = self._find_legacy_heads()
        if not legacy_heads:
            logger.info("✅ 未找到旧版（v1.0）数据引用，无需迁移。")
            return True

        logger.info(f"🔍 发现 {len(legacy_heads)} 个旧版历史分支，准备迁移...")

        # 步骤 1: 移动 Git 引用
        for commit_hash in legacy_heads:
            old_ref = f"{self.LEGACY_REFS_PREFIX}{commit_hash}"
            new_ref = f"{self.NEW_REFS_PREFIX}{commit_hash}"
            
            logger.debug(f"  - 正在移动: {old_ref} -> {new_ref}")
            self.git_db.update_ref(new_ref, commit_hash)
            self.git_db.delete_ref(old_ref)
        logger.info("✅ Git 引用已成功迁移到 v1.1 格式。")

        # 步骤 2: 为现有数据库条目回填 owner_id
        user_id = self._get_local_user_id()
        self._backfill_owner_ids(user_id)

        # 步骤 3: （可选但安全）运行常规补水，以防万一有不一致的情况
        logger.info("💧 正在执行增量同步以确保数据一致性...")
        self.hydrator.sync(local_user_id=user_id)
        
        logger.info("🎉 迁移完成！")
        return True
~~~~~

#### Acts 3: 更新 `migrate-data` 命令以注入 `DatabaseManager`

最后，我们需要确保 `MigrationManager` 能获得它所需的 `DatabaseManager` 实例。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
        engine = create_engine(project_root, lazy=True)
        config = ConfigManager(project_root)
        hydrator = Hydrator(engine.git_db, engine.db_manager)
        
        manager = MigrationManager(engine.git_db, config, hydrator)
        success = manager.run()
        
        if success:
~~~~~
~~~~~python
        engine = create_engine(project_root, lazy=True)
        config = ConfigManager(project_root)
        # 确保 db_manager 存在
        if not engine.db_manager:
            typer.secho("❌ 错误: 数据库管理器未能初始化。请检查配置。", fg=typer.colors.RED, err=True)
            ctx.exit(1)
            
        hydrator = Hydrator(engine.git_db, engine.db_manager)
        
        manager = MigrationManager(engine.git_db, config, engine.db_manager, hydrator)
        success = manager.run()
        
        if success:
~~~~~

### 下一步建议
1.  **清除旧状态**: 删除你本地的 `history.sqlite` 文件，然后再次运行 `qd migrate-data` 命令。
2.  **验证**:
    *   检查 `migrate-data` 的输出，确认 `节点 'owner_id' 已更新` 的日志是否显示了正确的更新数量。
    *   再次运行 `qd ui`，它现在应该可以正常启动了。
    *   在 UI 中，检查节点信息是否包含了 `(unknown-local-user)` 或你的用户 ID。
