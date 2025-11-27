好的，测试失败是由于 `tests/test_view_model.py` 没有同步更新以匹配我们刚刚重构的 `GraphViewModel`。我将修复这些测试。

## fix(tests): 修复 view_model 测试用例以匹配分页 API

### 错误分析
1.  **`test_initialization` 失败**: 测试代码仍在访问旧的 `total_count` 属性，而新实现已将其重命名为 `total_nodes`。
2.  **`test_pagination_flow` 失败**: 测试代码仍在调用已被移除的 `has_more_data` 和 `load_next_page` 方法。测试逻辑需要完全重写，以验证新的基于页码的 `load_page(page_number)` 方法。

### 用户需求
修复 `tests/test_view_model.py` 中的测试用例，使其与 `GraphViewModel` 的新分页 API 保持一致。

### 评论
这是一个预料之中的修复。测试是代码质量的保障，同步更新测试用例是重构流程中必不可少的一环。

### 目标
-   更新 `test_initialization` 以使用正确的属性 `total_nodes`。
-   重写 `test_pagination_flow` 以测试 `load_page` 方法的正确性，包括加载不同页面和处理边界情况。

### 基本原理
测试用例必须与它们所测试的代码单元的公共 API 保持同步。当 API 发生变化时（例如，从无限滚动模型变为分页模型），测试也必须相应地调整，以验证新 API 的行为是否符合预期。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high
#comp/tests #concept/ui #scope/dx
#ai/instruct
#task/state/continue #task-status/active

---

### Script

#### Acts 1: 修复 ViewModel 测试

我将重写 `tests/test_view_model.py` 文件，使其适应新的分页模型。

~~~~~act
write_file
~~~~~
~~~~~path
tests/test_view_model.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set, Any

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader
from quipu.cli.view_model import GraphViewModel


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

    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        return self._ancestors

    def get_private_data(self, commit_hash: str) -> Optional[str]:
        return self._private_data.get(commit_hash)

    def get_node_content(self, node: QuipuNode) -> str:
        # For simplicity, mock content is stored in the node's summary
        return node.summary

    # --- Unused abstract methods ---
    def load_all_nodes(self) -> List[QuipuNode]:
        return self._nodes

    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        return []


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

    def test_pagination_flow(self, sample_nodes):
        """测试分页加载逻辑是否正确。"""
        reader = MockHistoryReader(sample_nodes)
        # 10 nodes, page_size=4 -> 3 pages
        vm = GraphViewModel(reader, current_hash=None, page_size=4)
        vm.initialize()

        assert vm.total_pages == 3

        # 加载第一页
        page1 = vm.load_page(1)
        assert len(page1) == 4
        assert page1.output_tree == "h9"  # Newest
        assert vm.current_page == 1

        # 加载第二页
        page2 = vm.load_page(2)
        assert len(page2) == 4
        assert page2.output_tree == "h5"
        assert vm.current_page == 2

        # 加载最后一页 (不完整)
        page3 = vm.load_page(3)
        assert len(page3) == 2
        assert page3.output_tree == "h1"
        assert vm.current_page == 3

        # 尝试加载越界页面
        page4 = vm.load_page(4)
        assert len(page4) == 0

    def test_is_reachable(self, sample_nodes):
        """测试可达性检查逻辑。"""
        ancestors = {"h9", "h8"}  # current is h9, parent is h8
        reader = MockHistoryReader(sample_nodes, ancestors=ancestors)
        vm = GraphViewModel(reader, current_hash="h9")
        vm.initialize()

        assert vm.is_reachable("h9") is True  # Self
        assert vm.is_reachable("h8") is True  # Ancestor
        assert vm.is_reachable("h1") is False  # Unreachable

    def test_is_reachable_no_current_hash(self, sample_nodes):
        """测试在没有当前哈希时，所有节点都应被视为可达。"""
        reader = MockHistoryReader(sample_nodes, ancestors=set())
        vm = GraphViewModel(reader, current_hash=None)
        vm.initialize()

        assert vm.is_reachable("h9") is True
        assert vm.is_reachable("h1") is True

    def test_get_content_bundle(self):
        """测试公共和私有内容的格式化逻辑。"""
        # The key change is constructing a realistic filename where .name is the hash.
        node_both = QuipuNode("a", "h_both", datetime.now(), Path("mock/h_both"), "plan", summary="Public Content")
        node_public = QuipuNode("b", "h_public", datetime.now(), Path("mock/h_public"), "plan", summary="Public Only")
        node_private = QuipuNode("c", "h_private", datetime.now(), Path("mock/h_private"), "plan", summary="") # No public
        node_none = QuipuNode("d", "h_none", datetime.now(), Path("mock/h_none"), "plan", summary="")

        private_data = {"h_both": "Private Intent", "h_private": "Private Only"}
        reader = MockHistoryReader([], private_data=private_data)
        vm = GraphViewModel(reader, current_hash=None)

        # Case 1: Both public and private
        bundle1 = vm.get_content_bundle(node_both)
        assert "📜 公共计划内容" in bundle1
        assert "Public Content" in bundle1
        assert "🧠 开发者意图" in bundle1
        assert "Private Intent" in bundle1

        # Case 2: Public only
        bundle2 = vm.get_content_bundle(node_public)
        assert "📜 公共计划内容" in bundle2
        assert "Public Only" in bundle2
        assert "🧠 开发者意图" in bundle2
        assert "*此节点无私有数据或来自协作者*" in bundle2

        # Case 3: Private only
        bundle3 = vm.get_content_bundle(node_private)
        assert "📜 公共计划内容" not in bundle3
        assert "🧠 开发者意图" in bundle3
        assert "Private Only" in bundle3

        # Case 4: Neither
        bundle4 = vm.get_content_bundle(node_none)
        assert bundle4 == "*此节点无详细内容*"
~~~~~

### 下一步建议
测试已修复。现在 `ViewModel` 层已经稳固，我们可以继续执行**阶段三：前端 UI 适配**，开始修改 `tui.py` 文件。
