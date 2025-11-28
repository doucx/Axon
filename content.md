Excellent. With the reader tests now passing, we've successfully aligned the core `quipu-engine` test suite with the new architecture.

We are now on the final task of Phase 2: **Task 2.4**. This involves fixing the integration tests in `tests/integration/test_storage_selection.py`, which are the last remaining tests that explicitly depend on the old `refs/quipu/history` ref.

## fix: 更新集成测试以适应新的多头 Git 引用模型 (阶段 2.4)

### 错误分析
The integration tests in `TestStorageSelection` are designed to verify that Quipu correctly chooses the `GitObject` storage backend in a new or existing project. The verification logic in these tests, however, is entirely based on checking for the existence and update of the single `refs/quipu/history` ref.

*   `test_defaults_to_git_object_storage_on_new_project`: Fails because it asserts that the `history` ref must be created.
*   `test_continues_using_git_object_storage`: Fails because it tries to parse the `history` ref before and after an operation to check for updates and parent relationships.

Both tests fail because the production code no longer creates or interacts with this ref.

### 用户需求
Update the verification logic in `test_storage_selection.py` to correctly test the behavior of the `GitObject` storage backend using the new multi-head reference model.

### 评论
This is the final and crucial step in aligning our test suite's foundational assumptions with the new architecture. By fixing these integration tests, we ensure that our high-level workflows are validated against the correct system behavior, preventing future regressions.

### 目标
1.  In `test_defaults_to_git_object_storage_on_new_project`, modify the assertion to check that at least one head ref is created in the `refs/quipu/local/heads/` directory.
2.  In `test_continues_using_git_object_storage`, rewrite the logic to use a collection-based comparison of head refs before and after the second operation, and verify the parent-child link by inspecting the new Git commit object directly.

### 基本原理
We will apply the same robust, collection-based comparison strategy that we successfully used to fix `test_writer.py`. This method is deterministic and correctly models the multi-head nature of the new storage system. By getting the set of all head refs before and after an action, we can precisely identify the newly created node and verify its properties (like its parent commit) without relying on unstable sorting or obsolete ref names.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/history #scope/api #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Refactor the `TestStorageSelection` class

We will replace the entire `TestStorageSelection` class with an updated version that uses the correct verification logic for the multi-head architecture.

~~~~~act
patch_file
tests/integration/test_storage_selection.py
~~~~~
~~~~~python
class TestStorageSelection:
    """Tests the automatic detection and selection of storage backends."""

    def test_defaults_to_git_object_storage_on_new_project(self, runner, git_workspace):
        """
        SCENARIO: A user starts a new project.
        EXPECTATION: The system should use the new Git Object storage by default.
        """
        # Action: Run a plan in the new workspace
        result = runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_A)

        assert result.exit_code == 0, result.stderr

        # Verification
        assert (git_workspace / "a.txt").exists()

        # 1. New ref should exist
        ref_hash = git_rev_parse("refs/quipu/history", git_workspace)
        assert len(ref_hash) == 40, "A git ref for quipu history should have been created."

        # 2. Old directory should NOT exist
        legacy_history_dir = git_workspace / ".quipu" / "history"
        assert not legacy_history_dir.exists(), "Legacy file system history should not be used."

    def test_continues_using_git_object_storage(self, runner, git_workspace):
        """
        SCENARIO: A user runs quipu in a project already using the new format.
        EXPECTATION: The system should continue using the Git Object storage.
        """
        # Setup: Run one command to establish the new format
        runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_A)
        hash_after_a = git_rev_parse("refs/quipu/history", git_workspace)
        assert hash_after_a

        # Action: Run a second command
        result = runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_B)

        assert result.exit_code == 0, result.stderr

        # Verification
        # 1. The ref should be updated to a new commit
        hash_after_b = git_rev_parse("refs/quipu/history", git_workspace)
        assert hash_after_b != hash_after_a, "The history ref should point to a new commit."

        # 2. The parent of the new commit should be the old one
        parent_hash = git_rev_parse(f"{hash_after_b}^", git_workspace)
        assert parent_hash == hash_after_a, "The new commit should be parented to the previous one."

        # 3. No legacy files should be created
        assert not (git_workspace / ".quipu" / "history").exists()
~~~~~
~~~~~python
class TestStorageSelection:
    """Tests the automatic detection and selection of storage backends."""

    def test_defaults_to_git_object_storage_on_new_project(self, runner, git_workspace):
        """
        SCENARIO: A user starts a new project.
        EXPECTATION: The system should use the new Git Object storage by default.
        """
        # Action: Run a plan in the new workspace
        result = runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_A)

        assert result.exit_code == 0, result.stderr

        # Verification
        assert (git_workspace / "a.txt").exists()

        # 1. A new head ref should exist in the correct namespace
        get_heads_cmd = ["git", "for-each-ref", "--format=%(objectname)", "refs/quipu/local/heads/"]
        heads = subprocess.check_output(get_heads_cmd, cwd=git_workspace, text=True).strip().splitlines()
        assert len(heads) >= 1, "A git ref for quipu history should have been created."

        # 2. Old directory should NOT exist
        legacy_history_dir = git_workspace / ".quipu" / "history"
        assert not legacy_history_dir.exists(), "Legacy file system history should not be used."

    def test_continues_using_git_object_storage(self, runner, git_workspace):
        """
        SCENARIO: A user runs quipu in a project already using the new format.
        EXPECTATION: The system should continue using the Git Object storage.
        """
        get_all_heads_cmd = ["git", "for-each-ref", "--format=%(objectname)", "refs/quipu/local/heads/"]

        # Setup: Run one command to establish the new format
        runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_A)
        heads_after_a = set(subprocess.check_output(get_all_heads_cmd, cwd=git_workspace, text=True).strip().splitlines())
        assert len(heads_after_a) == 1
        commit_hash_a = heads_after_a.pop()

        # Action: Run a second command
        result = runner.invoke(app, ["run", "-y", "-w", str(git_workspace)], input=PLAN_B)
        assert result.exit_code == 0, result.stderr

        # Verification
        heads_after_b = set(subprocess.check_output(get_all_heads_cmd, cwd=git_workspace, text=True).strip().splitlines())
        new_heads = heads_after_b - {commit_hash_a}
        
        # 1. A new head should be created
        assert len(new_heads) == 1, "A new history head was not created after the second run"
        commit_hash_b = new_heads.pop()

        # 2. The parent of the new commit should be the old one
        commit_data = subprocess.check_output(["git", "cat-file", "-p", commit_hash_b], cwd=git_workspace, text=True)
        parent_line = [line for line in commit_data.splitlines() if line.startswith("parent ")]
        assert len(parent_line) == 1, "New commit should have exactly one parent"
        parent_hash = parent_line[0].split(" ")[1]
        assert parent_hash == commit_hash_a, "The new commit should be parented to the previous one."

        # 3. No legacy files should be created
        assert not (git_workspace / ".quipu" / "history").exists()
~~~~~

### 下一步建议
请执行此计划。这将完成我们修复计划的第二阶段。成功后，请重新运行完整的测试套件。我们预期所有与 `Hydrator` 接口和 Git 引用模型相关的错误都已解决。届时，我们将进入第三阶段，评估并修复剩余的连锁反应失败，主要是 `test_sync_workflow.py` 中的问题。
