import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, work_dir: Path):
        self.db_path = work_dir / ".quipu" / "history.sqlite"
        self.db_path.parent.mkdir(exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
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
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("🗃️  数据库连接已关闭。")

    def __del__(self):
        self.close()

    def init_schema(self):
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
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(sql, params)
        except sqlite3.Error as e:
            logger.error(f"❌ 数据库写入失败: {e} | SQL: {sql}")
            raise

    def get_all_node_hashes(self) -> set[str]:
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT commit_hash FROM nodes;")
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"❌ 查询节点哈希失败: {e}")
            return set()

    def batch_insert_nodes(self, nodes: list[tuple]):
        conn = self._get_conn()
        sql = """
            INSERT OR IGNORE INTO nodes 
            (commit_hash, owner_id, output_tree, node_type, timestamp, summary, generator_id, meta_json, plan_md_cache)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with conn:
                conn.executemany(sql, nodes)
        except sqlite3.Error as e:
            logger.error(f"❌ 批量插入节点失败: {e}")
            raise

    def batch_insert_edges(self, edges: list[tuple]):
        conn = self._get_conn()
        sql = "INSERT OR IGNORE INTO edges (child_hash, parent_hash) VALUES (?, ?)"
        try:
            with conn:
                conn.executemany(sql, edges)
        except sqlite3.Error as e:
            logger.error(f"❌ 批量插入边失败: {e}")
            raise
