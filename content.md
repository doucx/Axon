# fix: 修正测试夹具中因操作顺序错误导致的外键约束失败

## 用户需求
在为 SQLite 存储层添加分页和私有数据读取测试后，所有依赖 `populated_db` 夹具的新测试都失败了，并报告了 `sqlite3.IntegrityError: FOREIGN KEY constraint failed` 错误。这是因为测试夹具在填充 `nodes` 表之前就试图向 `private_data` 表写入数据，违反了数据库的外键约束。需要修正这个夹具的逻辑，确保数据填充的正确顺序。

## 评论
这是一个典型的测试环境设置 (setup) 错误。修复这个问题对于确保数据层测试的正确性和稳定性至关重要，也是后续 UI 功能开发得以顺利进行的前提。

## 目标
1.  调整 `tests/test_sqlite_reader.py` 中 `populated_db` 夹具的内部操作顺序。
2.  确保 `hydrator.sync()` 在 `db_manager.execute_write("INSERT INTO private_data ...")` 之前被调用。
3.  使所有 `TestSQLiteReaderPaginated` 类中的测试用例都能成功通过。

## 基本原理
数据库的外键约束（FOREIGN KEY constraint）保证了数据的引用完整性。要向子表（`private_data`）插入一条记录，该记录所引用的父表（`nodes`）中的主键必须已经存在。当前的测试夹具违反了这一原则。通过将 `hydrator.sync()` 提前，我们首先填充了父表 `nodes`，满足了外键约束的前提条件，从而解决了这个问题。

## 标签
#intent/fix
#flow/ready
#priority/critical
#comp/tests
#concept/history
#scope/dx
#ai/instruct
#task/domain/testing
#task/object/storage-layer
#task/action/bug-fix
#task/state/continue
#task/status/active

---

## Script

### Acts 1: 修正 `populated_db` 测试夹具的执行顺序

我们将 `db_manager.execute_write` 调用移动到 `hydrator.sync()` 之后。

~~~~~act
replace tests/test_sqlite_reader.py
~~~~~
~~~~~python
@pytest.fixture
def populated_db(sqlite_reader_setup):
    """一个预填充了15个节点和一些私有数据的数据库环境。"""
    reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup
    
    parent_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    commit_hashes = []
    
    for i in range(15):
        (repo / f"file_{i}.txt").write_text(f"v{i}")
        time.sleep(0.01) # Ensure unique timestamps
        output_hash = git_db.get_tree_hash()
        node = git_writer.create_node("plan", parent_hash, output_hash, f"Node {i}")
        commit_hashes.append(node.filename.name)
        parent_hash = output_hash

    # Add private data to Node 3
    db_manager.execute_write(
        "INSERT INTO private_data (node_hash, intent_md) VALUES (?, ?)",
        (commit_hashes[3], "This is a secret intent.")
    )

    hydrator.sync()
    return reader, db_manager, commit_hashes
~~~~~
~~~~~python
@pytest.fixture
def populated_db(sqlite_reader_setup):
    """一个预填充了15个节点和一些私有数据的数据库环境。"""
    reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup
    
    parent_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    commit_hashes = []
    
    for i in range(15):
        (repo / f"file_{i}.txt").write_text(f"v{i}")
        time.sleep(0.01) # Ensure unique timestamps
        output_hash = git_db.get_tree_hash()
        node = git_writer.create_node("plan", parent_hash, output_hash, f"Node {i}")
        commit_hashes.append(node.filename.name)
        parent_hash = output_hash

    # First, hydrate the nodes table from git objects
    hydrator.sync()

    # Now, with nodes in the DB, we can add private data referencing them
    db_manager.execute_write(
        "INSERT OR IGNORE INTO private_data (node_hash, intent_md) VALUES (?, ?)",
        (commit_hashes[3], "This is a secret intent.")
    )
    
    return reader, db_manager, commit_hashes
~~~~~
