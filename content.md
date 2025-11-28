Excellent. Phase 1 is complete, and all `TypeError` issues related to the `Hydrator` are resolved.

We now move to Phase 2 of the repair plan: adapting the test suite to the new Git reference architecture. The failures in this phase are due to tests asserting the existence or modification of the now-obsolete `refs/quipu/history` single reference point.

We will begin with **Task 2.1**, fixing `tests/engine/sqlite/test_writer.py`.

## fix: 更新测试以适应新的多头 Git 引用模型 (阶段 2.1)

### 错误分析
测试用例 `test_dual_write_on_run_and_link` 依赖 `git rev-parse refs/quipu/history` 来获取最新 Quipu 节点的 commit hash。在 v1.1 架构中，系统不再维护这个单一的引用。取而代之的是为每个节点在 `refs/quipu/local/heads/` 目录下创建一个独立的 head 引用。因此，旧的 `git rev-parse` 命令会失败，导致测试崩溃。

### 用户需求
修改 `test_dual_write_on_run_and_link` 测试，使其不再依赖 `refs/quipu/history`，而是通过查询 `refs/quipu/local/heads/` 目录来正确获取最新创建的节点 commit hash。

### 评论
这是对测试进行架构对齐的关键一步。通过使用更健壮的引用查询方式，我们使测试能够正确验证新架构下的写操作，确保节点被正确地持久化为独立的 Git head。

### 目标
用 `git for-each-ref --sort=-creatordate` 命令替换 `test_dual_write_on_run_and_link` 中过时的 `git rev-parse` 调用，以准确地找到最新创建的 Quipu commit hash。

### 基本原理
新的 Git 引用模型是多头的 (multi-head)。为了在测试中找到“最新”的节点，我们不能再依赖一个固定的引用名。`git for-each-ref --sort=-creatordate` 命令可以按创建日期对指定路径下的所有引用进行排序，并返回最新的一个。这是一种可靠的方式，可以找到 `quipu run` 命令刚刚创建的那个节点所对应的 commit hash。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/history #scope/api #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新 `test_writer.py` 的 commit hash 获取逻辑

我们将重写 `test_dual_write_on_run_and_link` 方法，用新的 `git for-each-ref` 命令来获取 `commit_hash_a` 和 `commit_hash_b`。

~~~~~act
patch_file
tests/engine/sqlite/test_writer.py
~~~~~
~~~~~python
class TestSQLiteWriterIntegration:
    def test_dual_write_on_run_and_link(self, sqlite_workspace):
        """
        验证 `quipu run` 在 SQLite 模式下是否能正确地双写到 Git 和 DB，并建立父子关系。
        """
        # --- Action 1: Create first node ---
        result_a = run_quipu(PLAN_A, work_dir=sqlite_workspace, yolo=True)
        assert result_a.success, f"run_quipu failed on Plan A: {result_a.message}"

        # Get its commit hash using the stable ref
        commit_hash_a = subprocess.check_output(
            ["git", "rev-parse", "refs/quipu/history"], cwd=sqlite_workspace, text=True
        ).strip()
        assert len(commit_hash_a) == 40

        # --- Action 2: Create second node, which should be a child of the first ---
        result_b = run_quipu(PLAN_B, work_dir=sqlite_workspace, yolo=True)
        assert result_b.success, f"run_quipu failed on Plan B: {result_b.message}"

        # Get the new commit hash from the updated ref
        commit_hash_b = subprocess.check_output(
            ["git", "rev-parse", "refs/quipu/history"], cwd=sqlite_workspace, text=True
        ).strip()
        assert len(commit_hash_b) == 40
        assert commit_hash_a != commit_hash_b, "History ref was not updated after second run"

        # --- Verification ---
        db_path = sqlite_workspace / ".quipu" / "history.sqlite"
        assert db_path.exists()
        db = DatabaseManager(sqlite_workspace)
        conn = db._get_conn()

        # 1. Verify node B exists
        cursor_node = conn.execute("SELECT * FROM nodes WHERE commit_hash = ?", (commit_hash_b,))
        node_row = cursor_node.fetchone()
        assert node_row is not None
        assert node_row["summary"] == "Write: b.txt"
        assert node_row["plan_md_cache"] is not None  # Should be hot-cached

        # 2. Verify the edge exists and points to node A
        cursor_edge = conn.execute("SELECT * FROM edges WHERE child_hash = ?", (commit_hash_b,))
        edge_row = cursor_edge.fetchone()
        assert edge_row is not None, "Edge for the second node was not created in the database."
        assert edge_row["parent_hash"] == commit_hash_a, "The parent hash in the edge is incorrect."

        db.close()
~~~~~
~~~~~python
class TestSQLiteWriterIntegration:
    def test_dual_write_on_run_and_link(self, sqlite_workspace):
        """
        验证 `quipu run` 在 SQLite 模式下是否能正确地双写到 Git 和 DB，并建立父子关系。
        """
        # --- Action 1: Create first node ---
        result_a = run_quipu(PLAN_A, work_dir=sqlite_workspace, yolo=True)
        assert result_a.success, f"run_quipu failed on Plan A: {result_a.message}"

        # Get its commit hash by finding the most recently created head
        get_latest_cmd = [
            "git", "for-each-ref", "--sort=-creatordate", "--format=%(objectname)", "refs/quipu/local/heads/", "--count=1"
        ]
        commit_hash_a = subprocess.check_output(get_latest_cmd, cwd=sqlite_workspace, text=True).strip()
        assert len(commit_hash_a) == 40

        # --- Action 2: Create second node, which should be a child of the first ---
        result_b = run_quipu(PLAN_B, work_dir=sqlite_workspace, yolo=True)
        assert result_b.success, f"run_quipu failed on Plan B: {result_b.message}"

        # Get the new latest commit hash
        commit_hash_b = subprocess.check_output(get_latest_cmd, cwd=sqlite_workspace, text=True).strip()
        assert len(commit_hash_b) == 40
        assert commit_hash_a != commit_hash_b, "A new history head was not created after the second run"

        # --- Verification ---
        db_path = sqlite_workspace / ".quipu" / "history.sqlite"
        assert db_path.exists()
        db = DatabaseManager(sqlite_workspace)
        conn = db._get_conn()

        # 1. Verify node B exists
        cursor_node = conn.execute("SELECT * FROM nodes WHERE commit_hash = ?", (commit_hash_b,))
        node_row = cursor_node.fetchone()
        assert node_row is not None
        assert node_row["summary"] == "Write: b.txt"
        assert node_row["plan_md_cache"] is not None  # Should be hot-cached

        # 2. Verify the edge exists and points to node A
        cursor_edge = conn.execute("SELECT * FROM edges WHERE child_hash = ?", (commit_hash_b,))
        edge_row = cursor_edge.fetchone()
        assert edge_row is not None, "Edge for the second node was not created in the database."
        assert edge_row["parent_hash"] == commit_hash_a, "The parent hash in the edge is incorrect."

        db.close()
~~~~~

### 下一步建议
请执行此计划。成功后，我们将继续修复 `tests/engine/test_git_writer.py`，完成 **Task 2.2**。
