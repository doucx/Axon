== 📜 公共计划内容=========

好的，分析收到了。测试套件的失败是由于我们向 `HistoryReader` 接口添加了新的抽象方法 (`get_descendant_output_trees` 和 `get_node_position`)，但没有在测试使用的模拟实现（`MockHistoryReader` 和 `InMemoryHistoryManager`）中提供这些方法的实现，导致 `TypeError`。

我将一次性修复所有相关的测试文件，确保测试套件恢复健康。

### fix(tests): 实现新的 HistoryReader 接口方法并修复测试

### 错误分析
-   **接口不匹配**: 测试中使用的 `MockHistoryReader` (位于 `tests/cli/test_view_model.py`) 和 `InMemoryHistoryManager` (位于 `tests/helpers.py`) 都没有实现 `HistoryReader` 接口新增的 `get_descendant_output_trees` 和 `get_node_position` 方法，导致在实例化时抛出 `TypeError`。
-   **测试逻辑过时**: `tests/cli/test_view_model.py` 中的部分测试仍然基于旧的、仅包含祖先的可达性逻辑 (`ancestor_set`)，需要更新以反映新的 `reachable_set` (祖先 + 后代) 逻辑。

### 用户需求
修复所有测试失败，使 `pytest` 能够成功运行。

### 评论
这是一个典型的因接口变更引起的连锁测试失败。修复工作是直接且必要的，同时这也是一个机会，可以增强我们的测试用例以覆盖新的双向可达性逻辑。

### 目标
1.  在 `tests/helpers.py` 中为 `InMemoryHistoryManager` 实现所有必需的抽象方法。
2.  在 `tests/cli/test_view_model.py` 中为 `MockHistoryReader` 实现所有必需的抽象方法。
3.  更新 `tests/cli/test_view_model.py` 和 `tests/cli/test_tui_reachability.py` 中的测试用例，使其与新的可达性模型保持一致。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script


#### Acts 2: 修复 `tests/cli/test_view_model.py`

我们更新 `MockHistoryReader` 并修正依赖它的测试用例。

~~~~~act
patch_file
tests/cli/test_view_model.py
~~~~~
~~~~~python
class MockHistoryReader(HistoryReader):
    """一个用于测试的、可配置的 HistoryReader 模拟实现。"""

    def __init__(
        self,
        nodes: List[QuipuNode],
        ancestors: Set[str] = None,
        private_data: dict[str, str] = None,
    ):
        self._nodes = sorted(nodes, key=lambda n: n.timestamp, reverse=True)
        self._ancestors = ancestors or set()
        self._private_data = private_data or {}

    def get_node_count(self) -> int:
        return len(self._nodes)

    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        return self._nodes[offset : offset + limit]

    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        return self._ancestors
~~~~~
~~~~~python
class MockHistoryReader(HistoryReader):
    """一个用于测试的、可配置的 HistoryReader 模拟实现。"""

    def __init__(
        self,
        nodes: List[QuipuNode],
        ancestors: Set[str] = None,
        descendants: Set[str] = None,
        private_data: dict[str, str] = None,
    ):
        self._nodes = sorted(nodes, key=lambda n: n.timestamp, reverse=True)
        self._ancestors = ancestors or set()
        self._descendants = descendants or set()
        self._private_data = private_data or {}

    def get_node_count(self) -> int:
        return len(self._nodes)

    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        return self._nodes[offset : offset + limit]

    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        return self._ancestors

    def get_descendant_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        return self._descendants

    def get_node_position(self, output_tree_hash: str) -> int:
        for i, node in enumerate(self._nodes):
            if node.output_tree == output_tree_hash:
                return i
        return -1
~~~~~
~~~~~act
patch_file
tests/cli/test_view_model.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
class TestGraphViewModel:
    def test_initialization_and_reachability(self, sample_nodes):
        """测试 ViewModel 初始化是否正确计算可达性集合。"""
        ancestors = {"h2", "h1"}
        descendants = {"h4", "h5"}
        current_hash = "h3"
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors, descendants=descendants)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)

        vm.initialize()

        assert vm.total_nodes == 10
        expected_reachable = {"h1", "h2", "h3", "h4", "h5"}
        assert vm.reachable_set == expected_reachable
        assert vm.current_page == 0
~~~~~
~~~~~act
patch_file
tests/cli/test_view_model.py
~~~~~
~~~~~python
    def test_is_reachable(self, sample_nodes):
        """测试可达性检查逻辑。"""
        ancestors = {"h9", "h8"}  # current is h9, parent is h8
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_output_tree_hash="h9")
        vm.initialize()

        assert vm.is_reachable("h9") is True  # Self
        assert vm.is_reachable("h8") is True  # Ancestor
        assert vm.is_reachable("h1") is False  # Unreachable
~~~~~
~~~~~python
    def test_is_reachable(self, sample_nodes):
        """测试可达性检查逻辑。"""
        ancestors = {"h8"}
        descendants = {"h10"}
        current_hash = "h9"
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors, descendants=descendants)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)
        vm.initialize()

        assert vm.is_reachable("h9") is True  # Self
        assert vm.is_reachable("h8") is True  # Ancestor
        assert vm.is_reachable("h10") is True  # Descendant
        assert vm.is_reachable("h1") is False  # Unreachable
~~~~~

#### Acts 3: 修复 `tests/cli/test_tui_reachability.py`

最后，我们更新 TUI 的可达性测试，使其也包含对后代的检查。

~~~~~act
patch_file
tests/cli/test_tui_reachability.py
~~~~~
~~~~~python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)
        vm.initialize()
        return vm
~~~~~
~~~~~python
@pytest.fixture
def view_model_factory():
    """A factory to create a GraphViewModel instance with mock data for tests."""

    def _factory(nodes, current_hash=None, ancestors=None, descendants=None, private_data=None):
        reader = MockHistoryReader(nodes, ancestors=ancestors, descendants=descendants, private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=current_hash)
        vm.initialize()
        return vm
~~~~~
~~~~~act
patch_file
tests/cli/test_tui_reachability.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    def test_ui_uses_view_model_for_reachability(self, view_model_factory):
        """
        Tests that the UI correctly queries the ViewModel to check reachability.
        """
        node_root = QuipuNode("c_root", "root", "null", datetime(2023, 1, 1), Path("f_root"), "plan", summary="Root")
        node_a = QuipuNode("c_a", "a", "root", datetime(2023, 1, 2), Path("f_a"), "plan", summary="A")
        node_b = QuipuNode("c_b", "b", "root", datetime(2023, 1, 3), Path("f_b"), "plan", summary="B") # Unrelated branch
        node_curr = QuipuNode("c_curr", "curr", "a", datetime(2023, 1, 4), Path("f_curr"), "plan", summary="Current")
        node_child = QuipuNode("c_child", "child", "curr", datetime(2023, 1, 5), Path("f_child"), "plan", summary="Child")

        ancestors = {"a", "root"}
        descendants = {"child"}
        view_model = view_model_factory(
            [node_root, node_a, node_b, node_curr, node_child],
            current_hash="curr",
            ancestors=ancestors,
            descendants=descendants,
        )
        app = QuipuUiApp(work_dir=Path("."))
        app.view_model = view_model

        assert app.view_model.is_reachable("curr") is True  # Self
        assert app.view_model.is_reachable("a") is True  # Ancestor
        assert app.view_model.is_reachable("root") is True  # Ancestor
        assert app.view_model.is_reachable("child") is True  # Descendant
        assert app.view_model.is_reachable("b") is False  # Unreachable
~~~~~


---


== 🧠 开发者意图===========

*此节点无私有数据或来自协作者*
