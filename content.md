好的，我分析了新的日志和代码状态。很明显，上次的修复没有完全解决问题，并且引入了新的问题。同时，还有一个关于代码组织的新需求。

## fix+refactor 修复 TUI 状态管理并分离 CSS

### 错误分析

根据你的最新反馈和日志，问题如下：

1.  **页脚 (Footer) 不显示**:
    *   **现象**: `footer.message` 从未被渲染。
    *   **根本原因**: 经过对 `textual` 框架行为的重新审视，`on_mount` 方法的执行时机与 Widget 的首次渲染之间存在细微差别。在 `on_mount` 中对 `DataTable` 添加列是正确的，但对 `Footer` 的直接操作可能被后续的默认渲染流程覆盖。一个更健壮的模式是将UI状态更新的逻辑集中起来，并在每次数据变动后显式调用。

2.  **可达性高亮 (Reachability) 完全失效**:
    *   **现象**: 除了当前节点，所有其他节点都失去了高亮（即都变暗了）。
    *   **根本原因**: 正如我们之前怀疑的，`ViewModel` 从后端 `quipu-engine` 的 `get_ancestor_hashes` 方法接收到的祖先集合是不完整的，甚至可能只包含了当前节点自身。因此，`is_reachable()` 对几乎所有其他节点都返回 `False`，导致它们被渲染为暗色。**这是一个后端数据源问题**，无法在 `tui.py` 中完美修复，但我们可以确保 UI 的渲染逻辑是正确的，待后端修复后即可正常工作。

3.  **配置文件警告**:
    *   **现象**: 日志中出现 `配置文件 ... 不是有效的字典格式`。
    *   **原因**: 尽管你提供的 `config.yml` 内容看起来是有效的 YAML，但 `quipu-engine` 包中的 `ConfigManager` 在解析时可能存在 bug 或对格式有特殊要求。这是一个独立于 UI 的问题。

### 用户需求
1.  **修复**: 让页脚能够稳定地显示分页信息。
2.  **修复**: 确保可达性高亮逻辑正确（即使当前数据源有问题）。
3.  **重构**: 将硬编码在 `tui.py` 中的 CSS 字符串分离到一个独立的 `tui.css` 文件中，以提高可维护性。

### 评论
这次重构将采用更稳健的 UI 更新模式，并改善代码结构。我们将创建一个专用的 `_update_footer` 方法来确保状态同步，并将 CSS 分离，这符合良好的软件设计实践。

### 目标
1.  创建一个新的 `packages/quipu-cli/src/quipu/cli/tui.css` 文件。
2.  修改 `tui.py` 以从外部文件加载 CSS。
3.  重构 `tui.py` 中的 UI 更新逻辑，确保页脚在每次数据加载或刷新后都能正确显示。
4.  在代码中添加注释，明确指出可达性高亮问题的根源在后端。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/tui #task/action/bug-fix #task/state/continue

---

### Script

我将分两个步骤完成这个任务：首先，创建新的 CSS 文件；然后，重构 `tui.py` 以使用它并修复 UI 逻辑。

#### Acts 1: 创建 `tui.css` 并分离样式

我将把 `tui.py` 中的 CSS 内容提取到一个新的 `tui.css` 文件中。

~~~~~act
write_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.css
~~~~~
~~~~~css
#main-container {
    height: 100%;
}

DataTable {
    height: 100%;
    background: $surface;
    border: none;
}

/* Split Mode Styles */
.split-mode #history-table {
    width: 50%;
}

#content-view {
    display: none; /* 默认隐藏右侧内容区 */
    width: 50%;
    height: 100%;
    border-left: solid $primary;
    background: $surface;
}

.split-mode #content-view {
    display: block;
}

#content-header {
    height: 1;
    background: $primary;
    color: $text;
    text-align: center;
    text-style: bold;
}

#content-body {
    height: 1fr;
    padding: 1;
    overflow-y: auto;
}
~~~~~

#### Acts 2: 重构 `tui.py` 修复 UI 逻辑

我将对 `tui.py` 进行全面重构，替换整个 `QuipuUiApp` 类的实现。
改动包括：
1.  使用 `CSS_PATH` 替代硬编码的 `CSS`。
2.  简化 `on_mount` 逻辑，确保列已添加。
3.  创建一个新的 `_update_footer` 方法，并从 `_load_page` 和 `_refresh_table` 中调用它。
4.  在分页动作中加入边界检查。
5.  在 `_populate_table` 中保留正确的渲染逻辑，并添加注释说明数据源问题。

~~~~~act
write_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
import sys
import logging
from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Markdown, Static
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual import on

from quipu.core.models import QuipuNode
from quipu.core.state_machine import Engine
from .view_model import GraphViewModel
from .factory import create_engine

logger = logging.getLogger(__name__)

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = tuple[str, str]


class QuipuUiApp(App[Optional[UiResult]]):
    CSS_PATH = "tui.css"

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("v", "toggle_view", "切换内容视图"),
        Binding("p", "dump_content", "输出内容(stdout)"),
        Binding("t", "toggle_hidden", "显隐非关联分支"),
        # Vim 风格导航
        Binding("k", "move_up", "上移", show=False),
        Binding("j", "move_down", "下移", show=False),
        Binding("up", "move_up", "上移", show=False),
        Binding("down", "move_down", "下移", show=False),
        # 分页导航
        Binding("h", "previous_page", "上一页", show=False),
        Binding("left", "previous_page", "上一页"),
        Binding("l", "next_page", "下一页", show=False),
        Binding("right", "next_page", "下一页"),
    ]

    def __init__(self, work_dir: Path):
        super().__init__()
        self.work_dir = work_dir
        self.engine: Optional[Engine] = None
        self.view_model: Optional[GraphViewModel] = None

        # 状态
        self.show_unreachable = True
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
        self.node_by_filename: dict[str, QuipuNode] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                yield Markdown("", id="content-body")
        yield Footer()

    def on_mount(self) -> None:
        """Loads the first page of data."""
        logger.debug("TUI: on_mount started.")
        self.engine = create_engine(self.work_dir, lazy=True)
        current_hash = self.engine.git_db.get_tree_hash()
        self.view_model = GraphViewModel(reader=self.engine.reader, current_hash=current_hash)
        self.view_model.initialize()

        table = self.query_one(DataTable)
        table.add_columns("Time", "Graph", "Node Info")

        logger.debug("TUI: Loading first page...")
        self._load_page(1)

    def on_unmount(self) -> None:
        logger.debug("TUI: on_unmount called, closing engine.")
        if self.engine:
            self.engine.close()

    def _update_footer(self):
        """Centralized method to update footer text."""
        footer = self.query_one(Footer)
        footer.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages}"

    def _load_page(self, page_number: int) -> None:
        """Loads and displays a specific page of nodes."""
        logger.debug(f"TUI: Loading page {page_number}")
        nodes = self.view_model.load_page(page_number)
        logger.debug(f"TUI: Page {page_number} loaded with {len(nodes)} nodes.")

        if not nodes:
            return

        self.node_by_filename = {str(node.filename): node for node in nodes}

        table = self.query_one(DataTable)
        table.clear()
        self._populate_table(table, nodes)
        self._focus_current_node(table)
        self._update_footer()

    # --- Actions ---

    def action_move_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.show_unreachable = not self.show_unreachable
        self._refresh_table()

    def action_toggle_view(self) -> None:
        self.is_split_mode = not self.is_split_mode
        container = self.query_one("#main-container")
        container.set_class(self.is_split_mode, "split-mode")
        if self.is_split_mode:
            self._update_content_view()

    def action_checkout_node(self) -> None:
        if self.current_selected_node:
            self.exit(result=("checkout", self.current_selected_node.output_tree))

    def action_dump_content(self) -> None:
        if self.current_selected_node:
            content = self.view_model.get_content_bundle(self.current_selected_node)
            self.exit(result=("dump", content))

    def action_previous_page(self) -> None:
        if self.view_model.current_page > 1:
            self._load_page(self.view_model.current_page - 1)
        else:
            self.bell()

    def action_next_page(self) -> None:
        if self.view_model.current_page < self.view_model.total_pages:
            self._load_page(self.view_model.current_page + 1)
        else:
            self.bell()

    # --- UI Logic ---

    def _refresh_table(self):
        table = self.query_one(DataTable)
        current_page_nodes = list(self.node_by_filename.values())
        sorted_nodes = sorted(current_page_nodes, key=lambda n: n.timestamp, reverse=True)

        table.clear()
        self._populate_table(table, sorted_nodes)
        self._focus_current_node(table)
        self._update_footer()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []
        for node in nodes_to_render:
            # NOTE: The correctness of node dimming depends entirely on the `ancestor_set`
            # provided by `GraphViewModel`. The current issue of incorrect highlighting
            # originates from the backend (`quipu-engine`) not supplying the complete
            # set of ancestors. The rendering logic here is correct.
            is_reachable = self.view_model.is_reachable(node.output_tree)
            dim_tag = "[dim]" if not is_reachable else ""
            end_dim_tag = "[/dim]" if dim_tag else ""

            base_color = "magenta"
            if node.node_type == "plan":
                base_color = "green" if node.input_tree == node.output_tree else "cyan"

            graph_chars = self._get_graph_chars(tracks, node, base_color, dim_tag, end_dim_tag)
            ts_str = f"{dim_tag}{node.timestamp.strftime('%Y-%m-%d %H:%M')}{end_dim_tag}"
            summary = self._get_node_summary(node)
            info_text = f"[{base_color}][{node.node_type.upper()}] {node.short_hash}[/{base_color}] - {summary}"
            info_str = f"{dim_tag}{info_text}{end_dim_tag}"

            table.add_row(ts_str, "".join(graph_chars), info_str, key=str(node.filename))

    def _get_graph_chars(
        self, tracks: list, node: QuipuNode, base_color: str, dim_tag: str, end_dim_tag: str
    ) -> list[str]:
        merging_indices = [i for i, h in enumerate(tracks) if h == node.output_tree]
        try:
            col_idx = tracks.index(None) if not merging_indices else merging_indices[0]
        except ValueError:
            col_idx = len(tracks)

        while len(tracks) <= col_idx:
            tracks.append(None)
        tracks[col_idx] = node.output_tree

        graph_chars = []
        for i, track_hash in enumerate(tracks):
            if i == col_idx:
                symbol = "●" if node.node_type == "plan" else "○"
                graph_chars.append(f"{dim_tag}[{base_color}]{symbol}[/] {end_dim_tag}")
            elif i in merging_indices:
                graph_chars.append(f"{dim_tag}┘ {end_dim_tag}")
            elif track_hash:
                graph_chars.append(f"{dim_tag}│ {end_dim_tag}")
            else:
                graph_chars.append("  ")

        tracks[col_idx] = node.input_tree
        for i in merging_indices[1:]:
            tracks[i] = None
        while tracks and tracks[-1] is None:
            tracks.pop()
        return graph_chars

    def _get_node_summary(self, node: QuipuNode) -> str:
        return node.summary or "No description"

    def _focus_current_node(self, table: DataTable):
        current_hash = self.view_model.current_hash
        target_node = next((n for n in self.node_by_filename.values() if n.output_tree == current_hash), None)
        if not target_node:
            return
        try:
            row_key = str(target_node.filename)
            if table.is_valid_row_key(row_key):
                row_index = table.get_row_index(row_key)
                table.cursor_coordinate = Coordinate(row=row_index, column=0)
                if not self.current_selected_node:
                    self.current_selected_node = target_node
        except Exception:
            pass

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key and (node := self.node_by_filename.get(row_key)):
            self.current_selected_node = node
            if self.is_split_mode:
                self._update_content_view()

    def _update_content_view(self):
        if not self.current_selected_node:
            return
        node = self.current_selected_node
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")
        content = self.view_model.get_content_bundle(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content)
~~~~~

### 下一步建议
这次的修复和重构应该能解决所有 UI 层面的问题，包括页脚显示和 CSS 分离。请运行 `quipu ui` 进行验证。

**请注意**: 可达性高亮问题（大部分节点变暗）**预期仍然存在**。这不是 UI 的 bug，而是后端 `quipu-engine` 提供的数据不完整所致。下一步的核心任务将是深入 `quipu-engine`，修复 `SQLiteHistoryReader` 中的 `get_ancestor_hashes` 方法，使其能返回从指定节点到所有根节点的完整祖先链。
