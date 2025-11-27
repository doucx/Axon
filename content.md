是的，**非常有必要**。

之前的 `test_sqlite_reader_integrity.py` 是**防御性**测试（测试“如果数据坏了，读取器怎么办”），而我们需要一个**预防性**测试（测试“确保写入器不会把数据写坏”）。

幂等操作导致父节点指向自己的问题是一个典型的**逻辑设计缺陷**，如果缺乏测试保护，未来很容易因为“代码清理”或“优化”而再次引入（例如，有人可能会觉得传递 `parent` 对象太麻烦，又改回 `get_commit_by_output_tree`）。

## test(engine): 验证 SQLite 写入器在幂等操作下的父子关系正确性

### 错误分析
在修复前，当连续创建两个具有相同 `output_tree` 的节点时，第二个节点在 SQLite 中的父节点会被错误地记录为它自己。
我们需要验证修复后的逻辑：即使 `output_tree` 相同，第二个节点也应正确指向第一个节点。

### 用户需求
创建一个测试，模拟连续两次写入相同内容（幂等操作），并验证 SQLite `edges` 表中的父子关系是线性的（A -> B），而不是自引用的（B -> B）。

### 评论
这个测试将直接验证 `GitObjectHistoryWriter` 和 `SQLiteHistoryWriter` 之间的 `parent` 传递机制是否工作正常。

### 目标
创建 `tests/test_sqlite_writer_idempotency.py`。

### 基本原理
1.  初始化环境。
2.  创建节点 1 (Commit A, Tree T)。
3.  创建节点 2 (Commit B, Tree T)。
4.  查询 SQLite `edges` 表，断言 Commit B 的 parent 是 Commit A。

### 标签
#intent/tooling #flow/ready #priority/medium
#comp/tests #comp/engine #scope/core
#ai/instruct
#task/domain/storage
#task/object/sqlite-backend
#task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 创建幂等性写入测试

~~~~~act
write_file
~~~~~
~~~~~path
tests/test_sqlite_writer_idempotency.py
~~~~~
~~~~~python
import pytest
import time
import subprocess
from pathlib import Path
from typing import Tuple

from quipu.core.sqlite_storage import SQLiteHistoryWriter
from quipu.core.git_object_storage import GitObjectHistoryWriter
from quipu.core.sqlite_db import DatabaseManager
from quipu.core.git_db import GitDB


@pytest.fixture
def repo_with_sqlite_db(tmp_path):
    """
    创建一个包含初始化 Git 仓库和 SQLite 数据库的临时环境。
    (从 test_sqlite_reader_integrity.py 复制并简化)
    """
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    git_db = GitDB(tmp_path)
    db_manager = DatabaseManager(tmp_path)
    db_manager.init_schema()

    yield db_manager, git_db

    db_manager.close()


def test_writer_handles_idempotent_operations_correctly(repo_with_sqlite_db):
    """
    ## test: Verify parent-child linkage during idempotent operations.

    When two consecutive nodes produce the exact same Output Tree Hash (idempotent operation),
    the SQLite writer must ensure that the second node points to the first node as its parent,
    rather than pointing to itself (self-loop) or getting confused by the identical tree hash.
    """
    db_manager, git_db = repo_with_sqlite_db
    
    # 1. Initialize the stack
    git_writer = GitObjectHistoryWriter(git_db)
    sqlite_writer = SQLiteHistoryWriter(git_writer, db_manager)

    # 2. Get initial state (Genesis)
    genesis_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    
    # 3. Create Node 1 (State A)
    # Since we are not actually changing files in the workdir, we manually specify input/output trees.
    # We simulate a "change" by creating a tree manually.
    
    # Create a dummy file blob
    blob_hash = git_db.hash_object(b"some content")
    # Create a tree containing that blob
    tree_hash_a = git_db.mktree(f"100644 blob {blob_hash}\tfile.txt")
    
    node_1 = sqlite_writer.create_node(
        node_type="plan",
        input_tree=genesis_tree,
        output_tree=tree_hash_a,
        content="Plan 1",
        summary_override="First Operation"
    )
    commit_1 = node_1.filename.name
    
    # 4. Create Node 2 (State A -> State A) - Idempotent!
    # Input tree is Node 1's output. Output tree is STILL Node 1's output.
    node_2 = sqlite_writer.create_node(
        node_type="plan",
        input_tree=tree_hash_a,
        output_tree=tree_hash_a, # Same tree!
        content="Plan 2 (Idempotent)",
        summary_override="Second Operation (Idempotent)"
    )
    commit_2 = node_2.filename.name

    assert commit_1 != commit_2, "Two distinct commits should be created even if trees are identical"

    # 5. Verify edges in SQLite
    conn = db_manager._get_conn()
    cursor = conn.execute("SELECT parent_hash FROM edges WHERE child_hash = ?", (commit_2,))
    row = cursor.fetchone()
    
    assert row is not None, "Edge for Node 2 should exist"
    parent_hash_in_db = row[0]
    
    # 6. Assertions
    assert parent_hash_in_db != commit_2, "CRITICAL: Node 2 should NOT be its own parent (Self-Loop detected!)"
    assert parent_hash_in_db == commit_1, "Node 2 should point to Node 1 as parent"
    
    print(f"\nVerified: {commit_2[:7]} (parent: {parent_hash_in_db[:7]}) -> {commit_1[:7]}")
~~~~~

### 下一步建议

执行测试：`pytest tests/test_sqlite_writer_idempotency.py`

如果测试通过，我们就可以放心地提交这个重构了。
