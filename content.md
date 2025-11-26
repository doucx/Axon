# test 为 `GraphViewModel` 创建测试

是的，为 `GraphViewModel` 创建测试是必要且关键的一步。

## 错误分析
直接进入阶段三 (UI 适配) 而不为 `GraphViewModel` 编写单元测试存在较高风险。`GraphViewModel` 封装了所有的数据分页、状态管理和可达性缓存逻辑。如果在集成到 TUI 后才发现这些逻辑中的错误，调试过程将会非常困难，因为需要区分是 ViewModel 的逻辑错误还是 TUI 的渲染或事件处理错误。

## 用户需求
在将 `GraphViewModel` 集成到 TUI 之前，为其创建一个独立的单元测试文件，以确保其所有功能的正确性和健壮性。

## 评论
这是一个遵循最佳实践的决策。`GraphViewModel` 是一个逻辑上独立的、可测试的单元。通过为其编写单元测试，我们可以使用一个模拟的 `HistoryReader` 来精确控制输入，并验证其内部状态和输出是否符合预期。这能保证在进入复杂的 TUI 集成阶段时，我们依赖的逻辑层是完全可靠的。

## 目标
1.  在 `tests/` 目录下创建一个新的测试文件 `test_view_model.py`。
2.  实现一个 `MockHistoryReader` 类，用于在测试中模拟数据源。
3.  编写针对 `GraphViewModel` 的单元测试，覆盖以下核心功能：
    *   初始化 (`initialize`)。
    *   分页加载 (`load_next_page`, `has_more_data`)。
    *   可达性检查 (`is_reachable`)。
    *   内容整合 (`get_content_bundle`)。

## 基本原理
测试将通过依赖注入的方式进行。我们会创建一个 `MockHistoryReader`，它实现了 `HistoryReader` 接口，但返回的是预设的、固定的测试数据。然后，我们将这个 mock reader 注入到 `GraphViewModel` 的实例中。通过这种方式，我们可以完全隔离 `GraphViewModel`，仅测试其自身的逻辑，而不受真实数据库或 Git 的影响。

## 标签
#intent/tooling #flow/ready #priority/high
#comp/cli #comp/tests #scope/dx
#ai/instruct
#task/domain/ui #task/object/performance #task/action/refactor
#task/state/continue #task/status/active

---

## Script

### Acts 1: 创建 ViewModel 的测试文件

此操作将创建 `tests/test_view_model.py` 并为其填充完整的测试用例，包括一个用于隔离测试的 `MockHistoryReader`。

~~~~~act
write_file tests/test_view_model.py
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

        assert vm.total_count == 10
        assert vm.ancestor_set == {"h3", "h2", "h1"}
        assert vm.offset == 0

    def test_pagination_flow(self, sample_nodes):
        """测试分页加载逻辑是否正确。"""
        reader = MockHistoryReader(sample_nodes)
        vm = GraphViewModel(reader, current_hash=None)
        vm.initialize()

        # 初始状态
        assert vm.has_more_data() is True
        assert vm.offset == 0

        # 加载第一页
        page1 = vm.load_next_page(size=4)
        assert len(page1) == 4
        assert page1[0].output_tree == "h9"  # Newest
        assert vm.offset == 4
        assert vm.has_more_data() is True

        # 加载第二页
        page2 = vm.load_next_page(size=4)
        assert len(page2) == 4
        assert page2[0].output_tree == "h5"
        assert vm.offset == 8
        assert vm.has_more_data() is True

        # 加载最后一页 (不完整)
        page3 = vm.load_next_page(size=4)
        assert len(page3) == 2
        assert page3[0].output_tree == "h1"
        assert vm.offset == 10
        assert vm.has_more_data() is False

        # 尝试再次加载
        page4 = vm.load_next_page(size=4)
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
        node_both = QuipuNode("a", "h_both", datetime.now(), Path("f_both"), "plan", summary="Public Content")
        node_public = QuipuNode("b", "h_public", datetime.now(), Path("f_public"), "plan", summary="Public Only")
        node_private = QuipuNode("c", "h_private", datetime.now(), Path("f_private"), "plan", summary="") # No public
        node_none = QuipuNode("d", "h_none", datetime.now(), Path("f_none"), "plan", summary="")

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
