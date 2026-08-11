from datetime import datetime
from pathlib import Path

import pytest
from quipu.cli.view_model import GraphViewModel
from quipu.spec.models.graph import QuipuNode
from quipu.spec.protocols.storage import HistoryReader


class MockHistoryReader(HistoryReader):
    def __init__(
        self,
        nodes: list[QuipuNode],
        ancestors: set[str] | None = None,
        descendants: set[str] | None = None,
        private_data: dict[str, str] | None = None,
    ):
        self._nodes = sorted(nodes, key=lambda n: n.timestamp, reverse=True)
        self._ancestors = ancestors or set()
        self._descendants = descendants or set()
        self._private_data = private_data or {}

    def get_node_count(self) -> int:
        return len(self._nodes)

    def load_nodes_paginated(self, limit: int, offset: int) -> list[QuipuNode]:
        return self._nodes[offset : offset + limit]

    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> set[str]:
        return self._ancestors

    def get_descendant_output_trees(self, start_output_tree_hash: str) -> set[str]:
        return self._descendants

    def get_node_position(self, output_tree_hash: str) -> int:
        for i, node in enumerate(self._nodes):
            if node.output_tree == output_tree_hash:
                return i
        return -1

    def get_private_data(self, node_commit_hash: str) -> str | None:
        return self._private_data.get(node_commit_hash)

    def get_node_content(self, node: QuipuNode) -> str:
        # For simplicity, mock content is stored in the node's summary
        return node.summary

    def get_node_blobs(self, commit_hash: str) -> dict[str, bytes]:
        return {}

    # --- Unused abstract methods ---
    def load_all_nodes(self) -> list[QuipuNode]:
        return self._nodes

    def find_nodes(
        self,
        summary_regex: str | None = None,
        node_type: str | None = None,
        limit: int = 10,
    ) -> list[QuipuNode]:
        return []


@pytest.fixture
def sample_nodes():
    return [
        QuipuNode(f"c{i}", f"h{i}", "h0", datetime(2023, 1, i + 1), Path(f"f{i}"), "plan", summary=f"Public {i}")
        for i in range(10)
    ]


class TestGraphViewModel:
    def test_initialization_and_reachability(self, sample_nodes):
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

    def test_pagination_flow(self, sample_nodes):
        reader = MockHistoryReader(sample_nodes)
        # 10 nodes, page_size=4 -> 3 pages
        vm = GraphViewModel(reader, current_output_tree_hash=None, page_size=4)
        vm.initialize()

        assert vm.total_pages == 3

        # 加载第一页
        page1 = vm.load_page(1)
        assert len(page1) == 4
        assert page1[0].output_tree == "h9"  # Newest
        assert vm.current_page == 1

        # 加载第二页
        page2 = vm.load_page(2)
        assert len(page2) == 4
        assert page2[0].output_tree == "h5"
        assert vm.current_page == 2

        # 加载最后一页 (不完整)
        page3 = vm.load_page(3)
        assert len(page3) == 2
        assert page3[0].output_tree == "h1"
        assert vm.current_page == 3

        # 尝试加载越界页面
        page4 = vm.load_page(4)
        assert len(page4) == 0

    def test_is_reachable(self, sample_nodes):
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

    def test_is_reachable_no_current_hash(self, sample_nodes):
        reader = MockHistoryReader(sample_nodes, ancestors=set())
        vm = GraphViewModel(reader, current_output_tree_hash=None)
        vm.initialize()

        assert vm.is_reachable("h9") is True
        assert vm.is_reachable("h1") is True

    def test_calculate_initial_page_not_found(self, sample_nodes):
        reader = MockHistoryReader(sample_nodes)
        vm = GraphViewModel(reader, current_output_tree_hash="unknown_hash")
        vm.initialize()

        # MockReader 在找不到 output_tree 时 get_node_position 返回 -1
        assert vm.calculate_initial_page() == 1

    def test_select_node_by_key_missing(self, sample_nodes):
        reader = MockHistoryReader(sample_nodes)
        vm = GraphViewModel(reader, current_output_tree_hash=None)
        vm.load_page(1)

        selected = vm.select_node_by_key("non_existent_path")
        assert selected is None
        assert vm.get_selected_node() is None

    def test_get_content_bundle(self):
        node_both = QuipuNode(
            "c_both", "h_both", "a", datetime.now(), Path("mock/h_both"), "plan", summary="Public Content"
        )
        node_public = QuipuNode(
            "c_public", "h_public", "b", datetime.now(), Path("mock/h_public"), "plan", summary="Public Only"
        )
        node_private = QuipuNode(
            "c_private", "h_private", "c", datetime.now(), Path("mock/h_private"), "plan", summary=""
        )  # No public
        node_none = QuipuNode("c_none", "h_none", "d", datetime.now(), Path("mock/h_none"), "plan", summary="")

        private_data = {"c_both": "Private Intent", "c_private": "Private Only"}
        reader = MockHistoryReader([], private_data=private_data)
        vm = GraphViewModel(reader, current_output_tree_hash=None)

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
