好的，这些测试错误是预料之中的，它们精确地指出了所有受到 API 契约变更影响的地方。我们现在将执行计划的第三阶段，自上而下地修复测试代码和上层逻辑，使整个系统恢复一致性。

### fix: 适配上层逻辑与测试用例以遵循新 API 契约

#### 错误分析
上次提交重构了数据模型和数据访问层接口，但并未更新依赖这些接口的测试代码。主要错误分为三类：
1.  `TypeError`: 测试中 `QuipuNode` 的实例化代码未提供新的 `commit_hash` 字段，导致参数错位。
2.  `TypeError`: 测试中的模拟  `HistoryReader` (`MockHistoryReader`, `InMemoryHistoryManager`) 未实现新的抽象方法 `get_ancestor_output_trees`。
3.  `AttributeError`/`AssertionError`: 具体的测试用例仍在调用已被重命名的旧方法 (`get_ancestor_hashes`) 或断言已被修改的旧版错误消息。

#### 用户需求
修复所有因 API 契约变更而失败的测试，确保整个代码库与新的、无歧义的标识符系统保持一致。

#### 评论
这是重构的收尾关键步骤。通过修复测试，我们不仅能验证重构的正确性，还能将新的 API 契约固化为可执行的规范，防止未来的代码再次引入模糊性。

#### 目标
-   更新所有测试中的 `QuipuNode` 实例化，使其符合新的构造函数签名。
-   更新所有模拟 `HistoryReader` 的实现，使其符合新的接口。
-   修正所有调用旧数据访问方法的测试代码。
-   修正断言过时错误消息的集成测试。

#### 基本原理
我们将逐一处理测试报告中的错误。首先修复最基础的实例化问题和模拟类实现，这将解决大部分 `TypeError`。然后，我们将深入到具体的测试用例中，调整它们的调用逻辑和断言，以完成整个适配过程。

#### 标签
#intent/fix #intent/tooling #flow/ready #priority/high
#comp/tests #comp/cli #comp/engine #scope/core
#ai/instruct
#task/domain/storage #task/object/api-contract #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 修复测试辅助模块 (`helpers.py` 和 `test_view_model.py`)

我们首先修复 `MockHistoryReader` 和 `InMemoryHistoryManager`，并更新核心的 `sample_nodes` 测试数据生成器。

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        return self._ancestors

    def get_private_data(self, commit_hash: str) -> Optional[str]:
        return self._private_data.get(commit_hash)
`````
`````python
    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        return self._ancestors

    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        return self._private_data.get(node_commit_hash)
`````

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
@pytest.fixture
def sample_nodes():
    """生成一组用于测试的节点。"""
    return [
        QuipuNode("h0", f"h{i}", datetime(2023, 1, i + 1), Path(f"f{i}"), "plan", summary=f"Public {i}")
        for i in range(10)
    ]


class TestGraphViewModel:
    def test_initialization(self, sample_nodes):
        """测试 ViewModel 初始化是否正确获取总数和可达性集合。"""
        ancestors = {"h3", "h2", "h1"}
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_hash="h3")

        vm.initialize()

        assert vm.total_nodes == 10
        assert vm.ancestor_set == {"h3", "h2", "h1"}
        assert vm.current_page == 0
`````
`````python
@pytest.fixture
def sample_nodes():
    """生成一组用于测试的节点。"""
    return [
        QuipuNode(f"c{i}", f"h{i}", "h0", datetime(2023, 1, i + 1), Path(f"f{i}"), "plan", summary=f"Public {i}")
        for i in range(10)
    ]


class TestGraphViewModel:
    def test_initialization(self, sample_nodes):
        """测试 ViewModel 初始化是否正确获取总数和可达性集合。"""
        ancestors = {"h3", "h2", "h1"}
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_output_tree_hash="h3")

        vm.initialize()

        assert vm.total_nodes == 10
        assert vm.ancestor_set == {"h3", "h2", "h1"}
        assert vm.current_page == 0
`````

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
    def test_pagination_flow(self, sample_nodes):
        """测试分页加载逻辑是否正确。"""
        reader = MockHistoryReader(sample_nodes)
        # 10 nodes, page_size=4 -> 3 pages
        vm = GraphViewModel(reader, current_hash=None, page_size=4)
        vm.initialize()
`````
`````python
    def test_pagination_flow(self, sample_nodes):
        """测试分页加载逻辑是否正确。"""
        reader = MockHistoryReader(sample_nodes)
        # 10 nodes, page_size=4 -> 3 pages
        vm = GraphViewModel(reader, current_output_tree_hash=None, page_size=4)
        vm.initialize()
`````

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
    def test_is_reachable(self, sample_nodes):
        """测试可达性检查逻辑。"""
        ancestors = {"h9", "h8"}  # current is h9, parent is h8
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_hash="h9")
        vm.initialize()

        assert vm.is_reachable("h9") is True  # Self
`````
`````python
    def test_is_reachable(self, sample_nodes):
        """测试可达性检查逻辑。"""
        ancestors = {"h9", "h8"}  # current is h9, parent is h8
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_output_tree_hash="h9")
        vm.initialize()

        assert vm.is_reachable("h9") is True  # Self
`````

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
    def test_is_reachable_no_current_hash(self, sample_nodes):
        """测试在没有当前哈希时，所有节点都应被视为可达。"""
        reader = MockHistoryReader(sample_nodes, ancestors=set())
        vm = GraphViewModel(reader, current_hash=None)
        vm.initialize()

        assert vm.is_reachable("h9") is True
`````
`````python
    def test_is_reachable_no_current_hash(self, sample_nodes):
        """测试在没有当前哈希时，所有节点都应被视为可达。"""
        reader = MockHistoryReader(sample_nodes, ancestors=set())
        vm = GraphViewModel(reader, current_output_tree_hash=None)
        vm.initialize()

        assert vm.is_reachable("h9") is True
`````

`````act
patch_file
`````
`````path
tests/cli/test_view_model.py
`````
`````python
    def test_get_content_bundle(self):
        """测试公共和私有内容的格式化逻辑。"""
        # The key change is constructing a realistic filename where .name is the hash.
        node_both = QuipuNode("a", "h_both", datetime.now(), Path("mock/h_both"), "plan", summary="Public Content")
        node_public = QuipuNode("b", "h_public", datetime.now(), Path("mock/h_public"), "plan", summary="Public Only")
        node_private = QuipuNode(
            "c", "h_private", datetime.now(), Path("mock/h_private"), "plan", summary=""
        )  # No public
        node_none = QuipuNode("d", "h_none", datetime.now(), Path("mock/h_none"), "plan", summary="")

        private_data = {"h_both": "Private Intent", "h_private": "Private Only"}
        reader = MockHistoryReader([], private_data=private_data)
        vm = GraphViewModel(reader, current_hash=None)
`````
`````python
    def test_get_content_bundle(self):
        """测试公共和私有内容的格式化逻辑。"""
        node_both = QuipuNode("c_both", "h_both", "a", datetime.now(), Path("mock/h_both"), "plan", summary="Public Content")
        node_public = QuipuNode("c_public", "h_public", "b", datetime.now(), Path("mock/h_public"), "plan", summary="Public Only")
        node_private = QuipuNode(
            "c_private", "h_private", "c", datetime.now(), Path("mock/h_private"), "plan", summary=""
        )  # No public
        node_none = QuipuNode("c_none", "h_none", "d", datetime.now(), Path("mock/h_none"), "plan", summary="")

        private_data = {"c_both": "Private Intent", "c_private": "Private Only"}
        reader = MockHistoryReader([], private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=None)
`````

---

#### Acts 2: 修复 TUI 相关测试

现在修复依赖 `MockHistoryReader` 和 `QuipuNode` 的 TUI 测试。

`````act
patch_file
`````
`````path
tests/cli/test_tui_logic.py
`````
`````python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, private_data=private_data)
        vm = GraphViewModel(reader, current_hash=current_hash)
        vm.initialize()
        return vm

    return _factory


class TestUiLogic:
    def test_graph_renderer_simple_linear(self, view_model_factory):
        """Smoke test for simple linear history rendering."""
        node_a = QuipuNode("root", "a", datetime(2023, 1, 1), Path("f1"), "plan")
        node_b = QuipuNode("a", "b", datetime(2023, 1, 2), Path("f2"), "plan")
        node_c = QuipuNode("b", "c", datetime(2023, 1, 3), Path("f3"), "plan")

        view_model = view_model_factory([node_a, node_b, node_c])
        app = QuipuUiApp(view_model=view_model)

        # This is a smoke test to ensure that instantiation and basic data processing
        # do not crash. With the new architecture, detailed rendering logic is harder
        # to assert without running the full Textual app.
        assert app.view_model.total_nodes == 3

    def test_graph_renderer_branching(self, view_model_factory):
        """Smoke test for branching history rendering."""
        node_a = QuipuNode("root", "a", datetime(2023, 1, 1), Path("f1"), "plan")
        node_b = QuipuNode("a", "b", datetime(2023, 1, 2), Path("f2"), "plan")
        node_c = QuipuNode("a", "c", datetime(2023, 1, 3), Path("f3"), "plan")

        view_model = view_model_factory([node_a, node_b, node_c])
        app = QuipuUiApp(view_model=view_model)

        # Smoke test
        assert app.view_model.total_nodes == 3

    def test_get_node_summary(self, view_model_factory):
        """
        Tests if the TUI correctly uses the pre-loaded summary field.
        """
        view_model = view_model_factory([])
        app = QuipuUiApp(view_model=view_model)

        # Case 1: Node with a pre-set summary
        node_with_summary = QuipuNode(
            "a", "b", datetime.now(), Path("f1"), "plan", summary="This is a pre-calculated summary."
        )
        assert app._get_node_summary(node_with_summary) == "This is a pre-calculated summary."

        # Case 2: Node with an empty summary
        node_without_summary = QuipuNode(
            "c",
            "d",
            datetime.now(),
            Path("f2"),
            "capture",
            summary="",  # Explicitly empty
        )
        assert app._get_node_summary(node_without_summary) == "No description"
`````
`````python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)
        vm.initialize()
        return vm

    return _factory


class TestUiLogic:
    def test_graph_renderer_simple_linear(self, view_model_factory):
        """Smoke test for simple linear history rendering."""
        node_a = QuipuNode("c1", "a", "root", datetime(2023, 1, 1), Path("f1"), "plan", summary="A")
        node_b = QuipuNode("c2", "b", "a", datetime(2023, 1, 2), Path("f2"), "plan", summary="B")
        node_c = QuipuNode("c3", "c", "b", datetime(2023, 1, 3), Path("f3"), "plan", summary="C")

        view_model = view_model_factory([node_a, node_b, node_c])
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model

        assert app.view_model.total_nodes == 3

    def test_graph_renderer_branching(self, view_model_factory):
        """Smoke test for branching history rendering."""
        node_a = QuipuNode("c1", "a", "root", datetime(2023, 1, 1), Path("f1"), "plan", summary="A")
        node_b = QuipuNode("c2", "b", "a", datetime(2023, 1, 2), Path("f2"), "plan", summary="B")
        node_c = QuipuNode("c3", "c", "a", datetime(2023, 1, 3), Path("f3"), "plan", summary="C")

        view_model = view_model_factory([node_a, node_b, node_c])
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model

        assert app.view_model.total_nodes == 3

    def test_get_node_summary(self, view_model_factory):
        """
        Tests if the TUI correctly uses the pre-loaded summary field.
        """
        view_model = view_model_factory([])
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model


        # Case 1: Node with a pre-set summary
        node_with_summary = QuipuNode(
            "c1", "b", "a", datetime.now(), Path("f1"), "plan", summary="This is a pre-calculated summary."
        )
        assert app._get_node_summary(node_with_summary) == "This is a pre-calculated summary."

        # Case 2: Node with an empty summary
        node_without_summary = QuipuNode(
            "c2",
            "d",
            "c",
            datetime.now(),
            Path("f2"),
            "capture",
            summary="",  # Explicitly empty
        )
        assert app._get_node_summary(node_without_summary) == "No description"
`````

`````act
patch_file
`````
`````path
tests/cli/test_tui_reachability.py
`````
`````python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, private_data=private_data)
        vm = GraphViewModel(reader, current_hash=current_hash)
        vm.initialize()
        return vm

    return _factory


class TestUiReachability:
    def test_ui_uses_view_model_for_reachability(self, view_model_factory):
        """
        Tests that the UI correctly queries the ViewModel to check reachability.
        """
        # We define a simple graph where only 'a' and 'curr' are ancestors.
        # The ViewModel will be initialized with this information.
        node_root = QuipuNode("null", "root", datetime(2023, 1, 1), Path("f_root"), "plan")
        node_a = QuipuNode("root", "a", datetime(2023, 1, 2), Path("f_a"), "plan")
        node_b = QuipuNode("root", "b", datetime(2023, 1, 3), Path("f_b"), "plan")
        node_curr = QuipuNode("a", "curr", datetime(2023, 1, 4), Path("f_curr"), "plan")

        ancestors = {"curr", "a", "root"}
        view_model = view_model_factory(
            [node_root, node_a, node_b, node_curr], current_hash="curr", ancestors=ancestors
        )
        app = QuipuUiApp(view_model=view_model)

        # The app should now use the view_model's ancestor set to determine reachability.
        # Directly check the results from the ViewModel's method that the UI uses.
        assert app.view_model.is_reachable("curr") is True
        assert app.view_model.is_reachable("a") is True
        assert app.view_model.is_reachable("root") is True
        assert app.view_model.is_reachable("b") is False

    def test_filter_unreachable_nodes_in_populate(self, view_model_factory):
        """
        Tests the filtering logic within the _populate_table method.
        """
        # Graph: root -> a, root -> b (unreachable)
        node_root = QuipuNode("null", "root", datetime(2023, 1, 1), Path("f_root"), "plan")
        node_a = QuipuNode("root", "a", datetime(2023, 1, 2), Path("f_a"), "plan")
        node_b = QuipuNode("root", "b", datetime(2023, 1, 3), Path("f_b"), "plan")

        # 'b' is not in the ancestor set, so it's unreachable.
        ancestors = {"a", "root"}
        view_model = view_model_factory([node_root, node_a, node_b], current_hash="a", ancestors=ancestors)
        app = QuipuUiApp(view_model=view_model)
        app.show_unreachable = False  # Set to hide unreachable nodes

        # Simulate the loop from _populate_table to see which nodes would be rendered
        nodes_on_page = view_model.load_page(1)
        rendered_nodes = [
            node for node in nodes_on_page if app.show_unreachable or app.view_model.is_reachable(node.output_tree)
        ]

        # The nodes are sorted by timestamp desc, so page 1 is [b, a, root]
        assert node_b not in rendered_nodes
        assert node_a in rendered_nodes
        assert node_root in rendered_nodes
`````
`````python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)
        vm.initialize()
        return vm

    return _factory


class TestUiReachability:
    def test_ui_uses_view_model_for_reachability(self, view_model_factory):
        """
        Tests that the UI correctly queries the ViewModel to check reachability.
        """
        node_root = QuipuNode("c_root", "root", "null", datetime(2023, 1, 1), Path("f_root"), "plan", summary="Root")
        node_a = QuipuNode("c_a", "a", "root", datetime(2023, 1, 2), Path("f_a"), "plan", summary="A")
        node_b = QuipuNode("c_b", "b", "root", datetime(2023, 1, 3), Path("f_b"), "plan", summary="B")
        node_curr = QuipuNode("c_curr", "curr", "a", datetime(2023, 1, 4), Path("f_curr"), "plan", summary="Current")

        ancestors = {"curr", "a", "root"}
        view_model = view_model_factory(
            [node_root, node_a, node_b, node_curr], current_hash="curr", ancestors=ancestors
        )
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model


        assert app.view_model.is_reachable("curr") is True
        assert app.view_model.is_reachable("a") is True
        assert app.view_model.is_reachable("root") is True
        assert app.view_model.is_reachable("b") is False

    def test_filter_unreachable_nodes_in_populate(self, view_model_factory):
        """
        Tests the filtering logic within the _populate_table method.
        """
        node_root = QuipuNode("c_root", "root", "null", datetime(2023, 1, 1), Path("f_root"), "plan", summary="Root")
        node_a = QuipuNode("c_a", "a", "root", datetime(2023, 1, 2), Path("f_a"), "plan", summary="A")
        node_b = QuipuNode("c_b", "b", "root", datetime(2023, 1, 3), Path("f_b"), "plan", summary="B")

        ancestors = {"a", "root"}
        view_model = view_model_factory([node_root, node_a, node_b], current_hash="a", ancestors=ancestors)
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model
        app.show_unreachable = False

        nodes_on_page = view_model.load_page(1)
        rendered_nodes = [
            node for node in nodes_on_page if app.show_unreachable or app.view_model.is_reachable(node.output_tree)
        ]

        assert node_b not in rendered_nodes
        assert node_a in rendered_nodes
        assert node_root in rendered_nodes
`````
