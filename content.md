## 这些测试失败是上次“标识符模糊性”重构的典型遗留问题。核心问题在于，部分测试代码仍然依赖旧的 API 签名（如 `get_ancestor_hashes`）和旧的命令行输出格式，而没有与已经更新的代码库保持同步。

我将逐一修复这些测试，使其与当前的代码实现保持一致。

### 计划

1.  **修复 `test_engine_memory.py`**: 为测试辅助类 `InMemoryHistoryManager` 实现新的 `get_ancestor_output_trees` 抽象方法，以匹配 `HistoryReader` 接口的变更。
2.  **修复 `tests/engine/sqlite/test_reader.py`**: 更新 `test_get_ancestors_with_cte` 测试用例，使其调用新的 `get_ancestor_output_trees` 方法，并验证返回的数据类型（`output_tree` 哈希集合）是否正确。
3.  **修复 `tests/integration/test_cli_workflow.py`**: 调整 `test_cli_checkout_not_found` 中断言的错误消息，以匹配 `checkout` 命令更新后的输出。
4.  **修复 `tests/cli/test_navigation_commands.py`**: `back`/`forward` 的导航逻辑依赖于一个稳定的 `Engine` 状态。在之前的重构中引入的 `get_ancestor_output_trees` 方法未在内存测试后端 (`InMemoryHistoryManager`) 中实现，这导致 `Engine` 在初始化 (`align` 期间) 时就可能失败，从而引发了 `checkout` 或 `back`/`forward` 等命令的连锁失败。通过修复第一点，这个问题也将得到解决。
5.  **修复 `tests/integration/test_storage_selection.py`**: 此处的 `checkout` 失败与第三点的问题同源。修复 `Engine` 的稳定性问题后，此处的集成测试应该也能通过。

以下是具体的代码修改。

### Script

#### Acts 1: 修复测试辅助类与测试用例

我将首先修复 `tests/helpers.py` 中的 `InMemoryHistoryManager`，使其符合 `HistoryReader` 接口。然后，我将更新使用这个接口的 SQLite 读取器测试。

`````````act
patch_file
`````````
`````````python
tests/helpers.py
`````````
`````````python
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        # In memory DB uses output_tree as key
        ancestors = set()
        if commit_hash in self.db.nodes:
            curr = self.db.nodes[commit_hash]
            while curr.parent:
                ancestors.add(curr.parent.output_tree)
                curr = curr.parent
        return ancestors
`````````
`````````python
    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]: 
        """ 
        符合新接口的内存实现。 
        从指定的 output_tree 哈希开始，向上遍历父节点，收集所有祖先的 output_tree 哈希。 
        """ 
        ancestors = set() 
        # 内存数据库使用 output_tree 作为节点的键
        if start_output_tree_hash in self.db.nodes: 
            curr = self.db.nodes[start_output_tree_hash] 
            while curr.parent: 
                ancestors.add(curr.parent.output_tree) 
                # 向上移动到父节点
                if curr.parent.output_tree in self.db.nodes: 
                    curr = self.db.nodes[curr.parent.output_tree] 
                else: 
                    # 如果父节点由于某种原因不在图中（在内存测试中不应该发生），则停止
                    break
        return ancestors
`````````

`````````act
patch_file
`````````
`````````python
tests/engine/sqlite/test_reader.py
`````````
`````````python
@pytest.fixture
def populated_db(sqlite_reader_setup):
    """一个预填充了15个节点和一些私有数据的数据库环境。"""
    reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup

    parent_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    commit_hashes = []

    for i in range(15):
        (repo / f"file_{i}.txt").write_text(f"v{i}")
        time.sleep(0.01)  # Ensure unique timestamps
        output_hash = git_db.get_tree_hash()
        node = git_writer.create_node("plan", parent_hash, output_hash, f"Node {i}")
        commit_hashes.append(node.filename.name)
        parent_hash = output_hash

    # First, hydrate the nodes table from git objects
    hydrator.sync()

    # Now, with nodes in the DB, we can add private data referencing them
    db_manager.execute_write(
        "INSERT OR IGNORE INTO private_data (node_hash, intent_md) VALUES (?, ?)",
        (commit_hashes[3], "This is a secret intent."),
    )

    return reader, db_manager, commit_hashes
`````````
`````````python
@pytest.fixture
def populated_db(sqlite_reader_setup): 
    """一个预填充了15个节点和一些私有数据的数据库环境。""" 
    reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup

    parent_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904" 
    commit_hashes = [] 
    output_tree_hashes = [] 

    for i in range(15): 
        (repo / f"file_{i}.txt").write_text(f"v{i}") 
        time.sleep(0.01)  # Ensure unique timestamps
        output_hash = git_db.get_tree_hash() 
        node = git_writer.create_node("plan", parent_hash, output_hash, f"Node {i}") 
        commit_hashes.append(node.commit_hash) 
        output_tree_hashes.append(node.output_tree) 
        parent_hash = output_hash

    # First, hydrate the nodes table from git objects
    hydrator.sync() 

    # Now, with nodes in the DB, we can add private data referencing them
    db_manager.execute_write( 
        "INSERT OR IGNORE INTO private_data (node_hash, intent_md) VALUES (?, ?)", 
        (commit_hashes[3], "This is a secret intent."), 
    ) 

    return reader, db_manager, commit_hashes, output_tree_hashes
`````````

`````````act
patch_file
`````````
`````````python
tests/engine/sqlite/test_reader.py
`````````
`````````python
    def test_get_ancestors_with_cte(self, populated_db):
        reader, db_manager, commit_hashes = populated_db
        # We want ancestors of the last created node (Node 14, which is commit_hashes[14])
        ancestors = reader.get_ancestor_hashes(commit_hashes[14])

        # It should contain all previous 14 commit hashes
        assert len(ancestors) == 14
        assert commit_hashes[0] in ancestors
        assert commit_hashes[13] in ancestors
        assert commit_hashes[14] not in ancestors  # Should not contain itself
`````````
`````````python
    def test_get_ancestors_with_cte(self, populated_db): 
        reader, db_manager, commit_hashes, output_tree_hashes = populated_db
        # We want ancestors of the last created node (Node 14) 
        # The input is the output_tree_hash of the last node.
        ancestor_output_trees = reader.get_ancestor_output_trees(output_tree_hashes[14]) 

        # It should contain all previous 14 output_tree hashes
        assert len(ancestor_output_trees) == 14
        assert output_tree_hashes[0] in ancestor_output_trees
        assert output_tree_hashes[13] in ancestor_output_trees
        assert output_tree_hashes[14] not in ancestor_output_trees  # Should not contain itself
`````````

#### Acts 2: 修复集成测试

现在，核心的 `Engine` 稳定性已经通过修复 `InMemoryHistoryManager` 得到保障。我将继续修复依赖此 `Engine` 的 CLI 集成测试，主要是更新 `checkout` 命令的错误消息断言。

`````````act
patch_file
`````````
`````````python
tests/integration/test_cli_workflow.py
`````````
`````````python
    def test_cli_checkout_not_found(self, populated_workspace):
        """Test checkout with a non-existent hash."""
        workspace, _, _ = populated_workspace

        result = runner.invoke(app, ["checkout", "deadbeef", "--work-dir", str(workspace), "--force"])

        assert result.exit_code == 1
        assert "❌ 错误: 未找到哈希前缀" in result.stderr
`````````
`````````python
    def test_cli_checkout_not_found(self, populated_workspace): 
        """Test checkout with a non-existent hash.""" 
        workspace, _, _ = populated_workspace

        result = runner.invoke(app, ["checkout", "deadbeef", "--work-dir", str(workspace), "--force"]) 

        assert result.exit_code == 1
        assert "❌ 错误: 未找到 output_tree 哈希前缀为" in result.stderr
`````````

这些修复覆盖了所有报告的错误和失败。`test_navigation_commands.py` 和其他依赖 `checkout` 的测试用例的失败是由于 `Engine` 未能成功初始化（由于缺少抽象方法的实现），现在这个问题已经解决，它们应该会恢复正常。
