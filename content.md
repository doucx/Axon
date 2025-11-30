好的，我将为你添加一个回归测试，以确保这个 Bug 不会再次出现。

这个测试将精确地模拟你描述的场景：连续执行两次 `quipu save`，并验证第二次操作是否正确地将第一次操作的状态作为其父节点。

## [WIP] test: 添加针对连续 save 操作的 HEAD 指针回归测试

### 用户需求
需要为 `tests/engine/test_head_tracking.py` 添加一个新的测试用例，该用例专门验证 `quipu save`（通过 `engine.capture_drift` 模拟）在连续执行时，能够正确地通过 `.quipu/HEAD` 文件追踪父节点，从而保证历史图谱的拓扑结构正确。

### 评论
添加这个回归测试至关重要。它将 `capture_drift` 方法的父节点查找逻辑锁定为正确行为，防止未来任何重构意外地重新引入这个“丢失 HEAD 指针”的 Bug。

### 目标
1.  在 `TestHeadTracking` 类中添加一个名为 `test_consecutive_saves_maintain_parentage` 的新测试方法。
2.  该测试将模拟两次连续的 `save` 操作。
3.  断言第二次 `save` 操作创建的节点的 `input_tree` 属性，与第一次 `save` 操作创建的节点的 `output_tree` 属性完全相等。

### 基本原理
测试将使用 `engine_with_repo` fixture 来获得一个干净的、初始化的 `Engine` 实例。
1.  首先，创建文件变更并调用 `engine.capture_drift` 来模拟第一次 `save`，记录下其 `output_tree`。
2.  然后，再次修改文件并调用 `engine.capture_drift` 来模拟第二次 `save`。
3.  最后，通过断言第二次操作的 `input_tree` 是否等于第一次的 `output_tree`，来验证修复是否有效。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #concept/state #concept/history #scope/core #ai/instruct #task/domain/storage #task/object/head-pointer #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 向 `test_head_tracking.py` 添加回归测试

我们将使用 `patch_file` 在 `TestHeadTracking` 类的末尾追加新的测试方法。

~~~~~act
patch_file
tests/engine/test_head_tracking.py
~~~~~
~~~~~python
        # 5. Assert Logical State (HEAD)
        assert engine._read_head() == hash_a
~~~~~
~~~~~python
        # 5. Assert Logical State (HEAD)
        assert engine._read_head() == hash_a

    def test_consecutive_saves_maintain_parentage(self, engine_with_repo):
        """
        Regression test: Ensures that a second 'save' correctly uses the first
        'save's state as its parent via the HEAD pointer, fixing a regression.
        """
        engine = engine_with_repo
        engine.align()

        # --- First Save ---
        (engine.root_dir / "data.txt").write_text("first version")
        hash1 = engine.git_db.get_tree_hash()
        node1 = engine.capture_drift(hash1, message="First save")

        # Verify state after first save
        assert engine._read_head() == hash1
        assert node1.output_tree == hash1
        engine.align()  # Align should now be clean

        # --- Second Save ---
        (engine.root_dir / "data.txt").write_text("second version")
        hash2 = engine.git_db.get_tree_hash()
        node2 = engine.capture_drift(hash2, message="Second save")

        # --- Assertion ---
        # Crucial check: the input for the second node MUST be the output from the first.
        # This confirms the HEAD pointer was correctly read and used.
        assert node2.input_tree == node1.output_tree

        # Verify state after second save
        assert node2.output_tree == hash2
        assert engine._read_head() == hash2
~~~~~
