好的，收到了测试失败的反馈。

这个失败暴露了一个比预期更微妙的问题。我的上一个修复方案方向是正确的（从检查单一 ref 转向检查多头 ref），但实现方式不够健壮，在高速运行的测试环境中会失败。

### 错误分析
失败的原因是 `assert commit_hash_a != commit_hash_b`。这说明在第二次 `run_quipu` 调用后，我们获取到的“最新” commit hash 仍然是第一次的那个。

**根本原因**:
1.  **多头架构**: 新架构的核心是**不删除父节点的 head 引用**。在第二次 `run` 之后，Git 中同时存在 `refs/quipu/local/heads/{commit_hash_a}` 和 `refs/quipu/local/heads/{commit_hash_b}` 两个引用。
2.  **时间戳问题**: 测试执行得非常快（亚秒级）。`git for-each-ref --sort=-creatordate` 依赖于 reflog 中记录的创建时间戳。如果两次 `run` 操作间隔太短，这两个引用的时间戳可能完全相同。当时间戳相同时，`--sort` 的顺序是**不确定的**，`--count=1` 可能会在两次调用中返回同一个 commit hash (`commit_hash_a`)，导致断言失败。

之前的修复方案过于依赖时间戳排序，不够稳定。我们需要一个更确定的方法来验证“一个新节点被创建了”。

### 用户需求
修复 `test_dual_write_on_run_and_link` 测试，使其能够稳定、可靠地验证在连续执行 `run` 命令后，新的 Quipu 节点和对应的 Git head 引用被正确创建。

### 评论
这是一个很好的例子，说明了测试不仅要验证功能，还要能抵抗环境因素（如执行速度）的干扰。正确的测试方法应该是比较操作前后的状态集合，而不是依赖于不稳定的排序。

### 目标
重写 `test_dual_write_on_run_and_link` 的 Git 状态验证逻辑。我们将通过比较第二次 `run` 操作**前后**的 `local/heads` 引用集合，来确定性地找出新创建的 commit hash。

### 基本原理
我们将采用集合比较的策略：
1.  在第一次 `run` 之后，获取 `commit_hash_a`，并记录下当前所有的 `local/heads` 引用集合，记为 `heads_before`。
2.  执行第二次 `run`。
3.  再次获取所有的 `local/heads` 引用集合，记为 `heads_after`。
4.  通过计算 `heads_after - heads_before` 的差集，我们可以精确地找到那个唯一新增的 commit hash，它就是 `commit_hash_b`。
这个方法完全不依赖时间戳，因此是稳定和可靠的。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/history #scope/api #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重写 `test_dual_write_on_run_and_link` 以使用集合比较

我们将用更稳健的集合比较逻辑替换之前依赖排序的逻辑。

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
~~~~~python
class TestSQLiteWriterIntegration:
    def test_dual_write_on_run_and_link(self, sqlite_workspace):
        """
        验证 `quipu run` 在 SQLite 模式下是否能正确地双写到 Git 和 DB，并建立父子关系。
        """
        # Command to get all local head commit hashes
        get_all_heads_cmd = ["git", "for-each-ref", "--format=%(objectname)", "refs/quipu/local/heads/"]

        # --- Action 1: Create first node ---
        result_a = run_quipu(PLAN_A, work_dir=sqlite_workspace, yolo=True)
        assert result_a.success, f"run_quipu failed on Plan A: {result_a.message}"

        # Get the state after the first run
        heads_after_a = set(subprocess.check_output(get_all_heads_cmd, cwd=sqlite_workspace, text=True).strip().splitlines())
        assert len(heads_after_a) == 1
        commit_hash_a = heads_after_a.pop()

        # --- Action 2: Create second node, which should be a child of the first ---
        result_b = run_quipu(PLAN_B, work_dir=sqlite_workspace, yolo=True)
        assert result_b.success, f"run_quipu failed on Plan B: {result_b.message}"

        # Get the state after the second run and find the new commit
        heads_before_b = {commit_hash_a} # The set of heads before this action
        heads_after_b = set(subprocess.check_output(get_all_heads_cmd, cwd=sqlite_workspace, text=True).strip().splitlines())
        
        new_heads = heads_after_b - heads_before_b
        assert len(new_heads) == 1, "Expected exactly one new head to be created"
        commit_hash_b = new_heads.pop()
        assert commit_hash_a != commit_hash_b

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
请执行此计划。这个更稳健的实现应该能够解决 `AssertionError`。成功后，我们将继续修复 `tests/engine/test_git_writer.py`，完成 **Task 2.2**。
