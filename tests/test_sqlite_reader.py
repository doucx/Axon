import pytest
import subprocess
from pathlib import Path

from quipu.core.git_db import GitDB
from quipu.core.sqlite_db import DatabaseManager
from quipu.core.hydrator import Hydrator
from quipu.core.git_object_storage import GitObjectHistoryWriter
from quipu.core.sqlite_storage import SQLiteHistoryReader


@pytest.fixture
def sqlite_reader_setup(tmp_path: Path):
    """
    创建一个包含 Git 仓库、DB 管理器、Writer 和 Reader 的测试环境。
    """
    repo_path = tmp_path / "sql_read_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)

    git_db = GitDB(repo_path)
    db_manager = DatabaseManager(repo_path)
    db_manager.init_schema()
    
    # Git-only writer to create commits
    git_writer = GitObjectHistoryWriter(git_db)
    # The reader we want to test
    reader = SQLiteHistoryReader(db_manager, git_db)
    # Hydrator to populate the DB from Git commits
    hydrator = Hydrator(git_db, db_manager)

    return reader, git_writer, hydrator, db_manager, repo_path, git_db


class TestSQLiteHistoryReader:
    def test_load_linear_history_from_db(self, sqlite_reader_setup):
        """测试从 DB 加载一个简单的线性历史。"""
        reader, git_writer, hydrator, _, repo, git_db = sqlite_reader_setup

        # 1. 在 Git 中创建两个节点
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        node_a_git = git_writer.create_node("plan", "genesis", hash_a, "Content A")
        
        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        node_b_git = git_writer.create_node("plan", hash_a, hash_b, "Content B")

        # 2. 补水到数据库
        hydrator.sync()
        
        # 3. 使用 SQLite Reader 读取
        nodes = reader.load_all_nodes()
        
        # 4. 验证
        assert len(nodes) == 2
        nodes_by_summary = {n.summary: n for n in nodes}
        node_a = nodes_by_summary["Content A"]
        node_b = nodes_by_summary["Content B"]
        
        assert node_b.parent == node_a
        assert node_a.children == [node_b]
        assert node_b.input_tree == node_a.output_tree

    def test_read_through_cache(self, sqlite_reader_setup):
        """测试通读缓存是否能正确工作（从未缓存到已缓存）。"""
        reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup

        # 1. 在 Git 中创建节点
        (repo / "c.txt").touch()
        hash_c = git_db.get_tree_hash()
        node_c_git = git_writer.create_node("plan", "genesis", hash_c, "Cache Test Content")
        commit_hash_c = node_c_git.filename.name

        # 2. 补水 (这将创建一个 plan_md_cache 为 NULL 的记录)
        hydrator.sync()

        # 3. 验证初始状态：缓存为 NULL
        conn = db_manager._get_conn()
        cursor = conn.execute("SELECT plan_md_cache FROM nodes WHERE commit_hash = ?", (commit_hash_c,))
        row = cursor.fetchone()
        assert row["plan_md_cache"] is None, "Cache should be NULL for cold data."

        # 4. 使用 Reader 加载节点并触发 get_node_content
        nodes = reader.load_all_nodes()
        node_c = [n for n in nodes if n.filename.name == commit_hash_c][0]
        
        # 首次读取前，内存中的 content 应该是空的
        assert node_c.content == ""
        
        # 触发读取
        content = reader.get_node_content(node_c)
        assert content == "Cache Test Content"
        
        # 5. 再次验证数据库：缓存应该已被回填
        cursor_after = conn.execute("SELECT plan_md_cache FROM nodes WHERE commit_hash = ?", (commit_hash_c,))
        row_after = cursor_after.fetchone()
        assert row_after["plan_md_cache"] == "Cache Test Content", "Cache was not written back to DB."