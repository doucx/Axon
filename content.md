好的，我们开始执行修复计划的第一步。

这个计划将解决所有因 `Hydrator.sync()` 缺少 `local_user_id` 参数而导致的 `TypeError`，这是当前最核心的阻塞性问题。我们将首先处理 `tests/engine/sqlite/test_hydrator.py` 文件。

## fix: 修复 Hydrator 接口变更导致的测试失败 (阶段 1.1)

### 错误分析
`sync` 功能的实现向 `Hydrator.sync()` 方法添加了一个必需的 `local_user_id` 参数。`test_hydrator.py` 中的测试用例在调用 `hydrator.sync()` 时没有提供这个参数，导致了 `TypeError`，从而使所有依赖数据补水的测试失败。

### 用户需求
修复 `tests/engine/sqlite/test_hydrator.py` 文件中的所有 `TypeError`，使其能够成功执行。

### 评论
这是修复整个测试套件的第一步。通过为测试中的 `sync` 调用提供一个固定的 `user_id` ("test-user")，我们可以快速解决这个接口不匹配问题，为后续修复铺平道路。

### 目标
修改 `test_hydrator.py` 文件中 `TestHydration` 类下的所有测试方法，将所有对 `hydrator.sync()` 的调用更新为 `hydrator.sync("test-user")`。

### 基本原理
直接在测试代码中为 `sync` 方法提供所需的参数，以满足新的方法签名，使测试逻辑能够继续执行。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/sync #scope/api #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新 `test_hydrator.py` 中的 `sync` 调用

对 `TestHydration` 类中的所有 `hydrator.sync()` 调用进行修改，添加 `"test-user"` 作为参数。

~~~~~act
patch_file
tests/engine/sqlite/test_hydrator.py
~~~~~
~~~~~python
class TestHydration:
    def test_full_hydration_from_scratch(self, hydrator_setup):
        """测试从一个空的数据库开始，完整补水一个已有的 Git 历史。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        # 1. 在 Git 中创建两个节点
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")

        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        writer.create_node("plan", hash_a, hash_b, "Node B")

        # 2. 初始状态下 DB 为空
        assert len(db_manager.get_all_node_hashes()) == 0

        # 3. 执行补水
        hydrator.sync()

        # 4. 验证
        db_hashes = db_manager.get_all_node_hashes()
        assert len(db_hashes) == 2

        conn = db_manager._get_conn()
        # 验证 Node B 的内容
        node_b_row = conn.execute("SELECT * FROM nodes WHERE summary = ?", ("Node B",)).fetchone()
        assert node_b_row is not None
        assert node_b_row["plan_md_cache"] is None  # 必须是冷数据

        # 验证边关系
        edge_row = conn.execute("SELECT * FROM edges WHERE child_hash = ?", (node_b_row["commit_hash"],)).fetchone()
        assert edge_row is not None

    def test_incremental_hydration(self, hydrator_setup):
        """测试只补水增量部分。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        # 1. 创建节点 A 并立即补水
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")
        hydrator.sync()
        assert len(db_manager.get_all_node_hashes()) == 1

        # 2. 创建节点 B
        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        writer.create_node("plan", hash_a, hash_b, "Node B")

        # 3. 再次补水
        hydrator.sync()

        # 4. 验证，总数应为 2
        assert len(db_manager.get_all_node_hashes()) == 2

        conn = db_manager._get_conn()
        node_b_row = conn.execute("SELECT * FROM nodes WHERE summary = ?", ("Node B",)).fetchone()
        assert node_b_row is not None

    def test_hydration_idempotency(self, hydrator_setup):
        """测试重复运行补水不会产生副作用。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")

        # 运行两次
        hydrator.sync()
        hydrator.sync()

        assert len(db_manager.get_all_node_hashes()) == 1
~~~~~
~~~~~python
class TestHydration:
    def test_full_hydration_from_scratch(self, hydrator_setup):
        """测试从一个空的数据库开始，完整补水一个已有的 Git 历史。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        # 1. 在 Git 中创建两个节点
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")

        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        writer.create_node("plan", hash_a, hash_b, "Node B")

        # 2. 初始状态下 DB 为空
        assert len(db_manager.get_all_node_hashes()) == 0

        # 3. 执行补水
        hydrator.sync("test-user")

        # 4. 验证
        db_hashes = db_manager.get_all_node_hashes()
        assert len(db_hashes) == 2

        conn = db_manager._get_conn()
        # 验证 Node B 的内容
        node_b_row = conn.execute("SELECT * FROM nodes WHERE summary = ?", ("Node B",)).fetchone()
        assert node_b_row is not None
        assert node_b_row["plan_md_cache"] is None  # 必须是冷数据

        # 验证边关系
        edge_row = conn.execute("SELECT * FROM edges WHERE child_hash = ?", (node_b_row["commit_hash"],)).fetchone()
        assert edge_row is not None

    def test_incremental_hydration(self, hydrator_setup):
        """测试只补水增量部分。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        # 1. 创建节点 A 并立即补水
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")
        hydrator.sync("test-user")
        assert len(db_manager.get_all_node_hashes()) == 1

        # 2. 创建节点 B
        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        writer.create_node("plan", hash_a, hash_b, "Node B")

        # 3. 再次补水
        hydrator.sync("test-user")

        # 4. 验证，总数应为 2
        assert len(db_manager.get_all_node_hashes()) == 2

        conn = db_manager._get_conn()
        node_b_row = conn.execute("SELECT * FROM nodes WHERE summary = ?", ("Node B",)).fetchone()
        assert node_b_row is not None

    def test_hydration_idempotency(self, hydrator_setup):
        """测试重复运行补水不会产生副作用。"""
        hydrator, writer, git_db, db_manager, repo = hydrator_setup

        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        writer.create_node("plan", "genesis", hash_a, "Node A")

        # 运行两次
        hydrator.sync("test-user")
        hydrator.sync("test-user")

        assert len(db_manager.get_all_node_hashes()) == 1
~~~~~

### 下一步建议
请执行此计划。完成后，我们将继续处理 `tests/engine/sqlite/test_reader.py` 中的 `TypeError` 问题，完成阶段一的修复。
