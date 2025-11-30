分析正确。由于 `create_node` 现在使用 `git mktree` 建立指向 `output_tree` 的强引用，Git 要求这个 `output_tree` 必须是对象数据库中真实存在的对象。

测试 `test_parent_linking_with_gap` 之前使用 `"a" * 40` 这种伪造的哈希值作为 `output_tree`。在旧逻辑中（仅写入文本 Trailer），这是允许的；但在新逻辑中（写入 Tree Entry），这会导致 `fatal: entry 'snapshot' object ... is unavailable` 错误。

既然你决定放弃旧数据的迁移，我们现在的首要任务就是修复这个测试，使其符合新的架构约束。

## [WIP] fix: 修正测试用例以使用有效的 Git Tree 对象

### 错误分析
测试 `tests/engine/test_git_reader.py::TestGitObjectHistoryReader::test_parent_linking_with_gap` 失败。
原因：测试代码向 `create_node` 传递了不存在的伪造哈希值 (`"a" * 40`)。
新引入的强引用机制 (`snapshot` 子树) 依赖 `git mktree`，该命令会校验子对象是否存在于 Git 对象库中。

### 用户需求
修复测试用例，在调用 `create_node` 前先创建真实有效的 Tree 对象，确保 `git mktree` 能够成功执行。

### 目标
修改 `test_parent_linking_with_gap`：
1.  使用 `hash_object` 和 `mktree` 预先创建有效的 Tree 对象。
2.  将这些有效 Tree 的哈希传递给 `create_node`。

### 基本原理
通过构建真实的 Git 对象来满足 `GitObjectHistoryWriter` 的严从性检查，保持测试逻辑不变（验证图谱断裂后的重连行为），但修正其输入数据。

### 标签
#intent/fix #flow/ready #priority/medium #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/git-backend #task/action/structural-linking #task/state/end #task/status/completed

---

### Script

#### Acts 1: 修正测试用例

我们将修改 `tests/engine/test_git_reader.py`，为 `node_a` 和 `node_c` 生成真实的 Tree 对象。

~~~~~act
patch_file
tests/engine/test_git_reader.py
~~~~~
~~~~~python
    def test_parent_linking_with_gap(self, reader_setup):
        """测试：如果父 Commit 是损坏的节点，子节点应断开链接并视为新的根"""
        reader, writer, git_db, _ = reader_setup

        h0 = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

        # 1. Create a valid node A
        node_a = writer.create_node("plan", h0, "a" * 40, "A", start_time=1000)

        # 2. Manually create a corrupted commit B, parented to A
~~~~~
~~~~~python
    def test_parent_linking_with_gap(self, reader_setup):
        """测试：如果父 Commit 是损坏的节点，子节点应断开链接并视为新的根"""
        reader, writer, git_db, _ = reader_setup

        h0 = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

        # Helper to create a valid tree object in the ODB
        def make_valid_tree(content: bytes) -> str:
            blob = git_db.hash_object(content)
            return git_db.mktree(f"100644 blob {blob}\tfile")

        tree_a = make_valid_tree(b"state_a")
        tree_c = make_valid_tree(b"state_c")

        # 1. Create a valid node A
        node_a = writer.create_node("plan", h0, tree_a, "A", start_time=1000)

        # 2. Manually create a corrupted commit B, parented to A
~~~~~

~~~~~act
patch_file
tests/engine/test_git_reader.py
~~~~~
~~~~~python
        # 3. Create a valid node C, whose logical parent (by input_tree) is A,
        # but whose topological parent in Git is the bad commit B.
        # The writer will link C to A based on input_tree. The reader must correctly
        # parse this graph despite the corrupted intermediary.
        writer.create_node("plan", node_a.output_tree, "c" * 40, "C", start_time=3000)

        nodes = reader.load_all_nodes()
~~~~~
~~~~~python
        # 3. Create a valid node C, whose logical parent (by input_tree) is A,
        # but whose topological parent in Git is the bad commit B.
        # The writer will link C to A based on input_tree. The reader must correctly
        # parse this graph despite the corrupted intermediary.
        writer.create_node("plan", node_a.output_tree, tree_c, "C", start_time=3000)

        nodes = reader.load_all_nodes()
~~~~~

### 下一步建议
测试修复后，建议运行 `pytest tests/engine/test_git_reader.py` 确认通过。
至此，关于**强引用连接**的核心修复与测试调整已全部完成。你可以放心地继续使用 Quipu，哪怕在多设备同步的场景下，状态快照也将是安全且完整的。
