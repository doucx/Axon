是的，我们可以开始 ## 阶段二：逻辑层预重构 (ViewModel Layer)。

前置的数据层接口 (`HistoryReader`) 已经准备就绪，现在是引入 `GraphViewModel` 以解耦 TUI 和数据加载逻辑的最佳时机。

这将是实现 UI 性能优化和功能增强的关键一步，它将 UI 组件从复杂的状态管理和数据获取逻辑中解放出来，使其只专注于渲染。

# refactor: 引入 GraphViewModel 以解耦 UI 与数据层

## 用户需求
根据 `Quipu UI 性能优化与功能增强执行方案`，执行阶段二，创建一个名为 `GraphViewModel` 的中间逻辑层。

## 评论
这是一个关键的重构步骤，遵循了 MVVM (Model-View-ViewModel) 的设计思想。通过引入 ViewModel，我们可以将 TUI 的状态管理、数据分页加载、可达性计算等复杂逻辑从视图 (`tui.py`) 中剥离出来，使代码结构更清晰，更易于维护和测试。

## 目标
1.  在 `quipu-cli` 包中创建一个新文件 `view_model.py`。
2.  实现 `GraphViewModel` 类，它将作为 TUI 和 `HistoryReader` 之间的数据与逻辑协调者。
3.  该类将封装分页加载、可达性状态缓存、以及公共/私有内容整合的逻辑。

## 基本原理
`GraphViewModel` 将持有对 `HistoryReader` 的引用，并向 UI 层暴露一组简洁的接口。UI (`QuipuUiApp`) 不再直接管理节点列表或执行数据库查询，而是委托给 `GraphViewModel`。

-   **数据状态**: `GraphViewModel` 内部维护已加载的节点列表 (`loaded_nodes`)、总节点数 (`total_count`) 和分页偏移量 (`offset`)。
-   **逻辑状态**: `GraphViewModel` 在初始化时一次性计算并缓存所有可达节点的哈希集合 (`ancestor_set`)，供 UI 快速查询。
-   **数据获取**: `GraphViewModel` 负责调用 `reader.load_nodes_paginated` 并管理分页逻辑，同时提供一个 `get_content_bundle` 方法来统一处理公共和私有内容的获取与格式化。

## 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #concept/ui #scope/api
#ai/instruct
#task/domain/ui #task/object/performance #task/action/refactor
#task/state/begin #task/status/active

---

## Script

### Acts 1: 创建 ViewModel

这个操作将在 `quipu-cli` 模块中创建 `view_model.py` 文件，并实现 `GraphViewModel` 类的完整逻辑。

~~~~~act
write_file src/quipu/cli/view_model.py
~~~~~
~~~~~python
from typing import List, Optional, Set

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader


class GraphViewModel:
    """
    一个 ViewModel，用于解耦 TUI (View) 和 HistoryReader (Model)。

    它负责管理分页加载状态、缓存可达性数据，并为 UI 提供简洁的数据接口。
    """

    def __init__(self, reader: HistoryReader, current_hash: Optional[str]):
        self.reader = reader
        self.current_hash = current_hash
        self.loaded_nodes: List[QuipuNode] = []
        self.ancestor_set: Set[str] = set()
        self.total_count: int = 0
        self.offset: int = 0

    def initialize(self):
        """
        初始化 ViewModel，获取总数并计算可达性缓存。
        这是一个快速操作，因为它不加载任何节点内容。
        """
        self.total_count = self.reader.get_node_count()
        if self.current_hash:
            # 后端直接计算祖先，避免在前端加载整个图谱
            self.ancestor_set = self.reader.get_ancestor_hashes(self.current_hash)
            # 当前节点本身也是可达的
            self.ancestor_set.add(self.current_hash)

    def is_reachable(self, node_hash: str) -> bool:
        """检查一个节点哈希是否在可达性集合中。"""
        if not self.current_hash:
            # 如果没有当前状态 (例如，在创世之前)，将所有内容视为可达，
            # 以避免 UI 显示全灰色。
            return True
        return node_hash in self.ancestor_set

    def has_more_data(self) -> bool:
        """检查是否还有更多数据可以从后端加载。"""
        if self.total_count == 0:
            return False
        return self.offset < self.total_count

    def load_next_page(self, size: int = 50) -> List[QuipuNode]:
        """
        加载下一页数据，更新内部状态，并返回新加载的节点列表。
        """
        if not self.has_more_data():
            return []

        new_nodes = self.reader.load_nodes_paginated(limit=size, offset=self.offset)
        self.loaded_nodes.extend(new_nodes)
        self.offset += len(new_nodes)
        return new_nodes

    def get_content_bundle(self, node: QuipuNode) -> str:
        """
        获取节点的公共内容和私有内容，并将它们格式化成一个单一的字符串用于展示。
        """
        public_content = self.reader.get_node_content(node) or ""
        private_content = self.reader.get_private_data(node.filename.name)

        if not public_content and not private_content:
            return "*此节点无详细内容*"

        # 构建最终的显示内容
        bundle = []
        if public_content:
            bundle.append("== 📜 公共计划内容=========")
            bundle.append(public_content.strip())

        if private_content is not None:
            if public_content:
                bundle.append("\n---\n")
            bundle.append("== 🧠 开发者意图===========")
            bundle.append(private_content.strip())
        elif public_content:
            # 仅当有公共内容时，才显示“无私有数据”的消息
            bundle.append("\n---\n")
            bundle.append("== 🧠 开发者意图===========")
            bundle.append("*此节点无私有数据或来自协作者*")

        return "\n\n".join(bundle)
~~~~~
