好的，我将分步执行 **任务 4: 改造 QuipuUiApp 初始化**。这会将 UI (`tui.py`) 的状态管理职责转移到新的 `GraphViewModel`。

我将通过 `patch_file` 指令，一块一块地精确修改代码。

### fix: 改造 QuipuUiApp 以对接 ViewModel

#### 用户需求
根据 UI 性能优化方案，改造 `QuipuUiApp` 的初始化流程，使其不再直接接收节点列表，而是接收一个 `GraphViewModel` 实例。这将解耦视图层与数据层，为后续实现分页加载做准备。

#### 评论
这是实现 UI 秒开的关键一步。通过引入 ViewModel，我们将复杂的状态管理和数据获取逻辑从视图代码中剥离，使 TUI 代码更专注于渲染和用户交互。

#### 目标
1.  修改 `QuipuUiApp` 的 `__init__` 方法签名，使其接收 `GraphViewModel`。
2.  移除 `__init__` 方法中所有旧的数据处理和状态初始化逻辑。
3.  添加 `self.view_model` 属性。
4.  删除不再需要的 `_calculate_reachable_hashes` 辅助方法。

#### 基本原理
该重构遵循 MVVM (Model-View-ViewModel) 设计模式。`QuipuUiApp` (View) 的职责是渲染 `GraphViewModel` (ViewModel) 提供的数据。所有的数据加载、分页、缓存和可达性计算都由 ViewModel 负责，视图本身保持无状态。这使得代码更清晰、更易于测试和维护。

#### 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #concept/ui #scope/core
#ai/instruct
#task/domain/ui #task/object/tui-performance #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 导入 `GraphViewModel` 并重写 `__init__`

首先，我们需要在 `tui.py` 中导入新的 `GraphViewModel` 类。然后，我将重写 `__init__` 方法，移除旧的 `nodes`, `content_loader`, `current_hash` 等参数，替换为 `view_model`，并清理方法内部的旧逻辑。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
from quipu.core.models import QuipuNode

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = Tuple[str, str]


class QuipuUiApp(App[Optional[UiResult]]):
~~~~~
~~~~~python
from quipu.core.models import QuipuNode
from .view_model import GraphViewModel

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = Tuple[str, str]


class QuipuUiApp(App[Optional[UiResult]]):
~~~~~

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def __init__(
        self, nodes: List[QuipuNode], content_loader: Callable[[QuipuNode], str], current_hash: Optional[str] = None
    ):
        super().__init__()
        self.sorted_nodes = sorted(nodes, key=lambda n: n.timestamp, reverse=True)
        self.content_loader = content_loader
        self.current_hash = current_hash

        # 索引构建
        self.node_by_filename: Dict[str, QuipuNode] = {str(node.filename): node for node in nodes}
        self.nodes_by_output_hash: Dict[str, List[QuipuNode]] = {}
        for node in nodes:
            self.nodes_by_output_hash.setdefault(node.output_tree, []).append(node)

        # 状态
        self.show_unreachable = True
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
        self.reachable_hashes = self._calculate_reachable_hashes()
~~~~~
~~~~~python
    def __init__(self, view_model: GraphViewModel):
        super().__init__()
        self.view_model = view_model

        # 状态
        self.show_unreachable = True
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
~~~~~

#### Acts 2: 移除 `_calculate_reachable_hashes` 方法

这个方法的逻辑现在将由 `GraphViewModel` 通过后端查询高效实现，因此在视图层不再需要它。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _calculate_reachable_hashes(self) -> Set[str]:
        if not self.current_hash or self.current_hash not in self.nodes_by_output_hash:
            return set()

        start_node = self.nodes_by_output_hash[self.current_hash][-1]
        reachable = {start_node.output_tree}
        curr = start_node
        while curr.parent:
            curr = curr.parent
            reachable.add(curr.output_tree)

        queue = [start_node]
        while queue:
            node = queue.pop(0)
            for child in node.children:
                reachable.add(child.output_tree)
                queue.append(child)
        return reachable
~~~~~
~~~~~python
~~~~~

### 下一步建议
初始化改造已完成。代码目前处于一个中间的、不可运行的状态，因为 `tui.py` 中的其他方法仍然依赖于已被移除的旧属性。

下一步，我将执行 **任务 5: 实现分页加载与渲染机制**，修复这些依赖问题，让 UI 能够从 ViewModel 加载并显示第一页数据。
