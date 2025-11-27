好的，为了彻底解决 UI 渲染异常和焦点丢失问题，并避免 `patch_file` 可能因上下文不匹配而失败的风险，我将直接重写 `tui.py`。

此次重写将确保：
1.  **彻底移除**导致渲染穿插的“强制连线”逻辑。
2.  **强化焦点定位**：使用 `move_cursor` 替代直接设置坐标，以确保视图滚动；并在 `on_mount` 中显式调用 `table.focus()`。

## fix: 重写 TUI 逻辑以修复渲染与焦点问题

### 错误分析
-   **焦点问题**：直接设置 `cursor_coordinate` 可能未触发必要的滚动行为，且表格组件未获得应用级焦点，导致键盘导航失效。
-   **渲染问题**：旧的强制连线逻辑导致了视觉伪影。虽然之前的补丁意图移除它，但为了稳健性，全量重写能确保该逻辑彻底消失。

### 用户需求
-   UI 启动时，光标自动定位到当前 HEAD 节点。
-   图谱渲染清晰，无错误的连线干扰。

### 目标
-   使用 `write_file` 重置 `packages/quipu-cli/src/quipu/cli/tui.py`。
-   确保 `tracks` 初始化为空。
-   在 `on_mount` 和 `_load_page` 中正确处理焦点和光标移动。

### 基本原理
-   **Focus**: `table.focus()` 激活组件。
-   **Scroll**: `table.move_cursor(row=row_index)` 确保高亮行进入视野。
-   **Clean Graph**: `tracks` 列表每页重置，仅依据当前页节点关系绘图。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #scope/ux #ai/instruct #task/domain/ui #task/object/reachability #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 重写 tui.py

~~~~~act
write_file
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
    TITLE = "Quipu History Explorer"

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("v", "toggle_view", "切换内容视图"),
        Binding("p", "dump_content", "输出内容(stdout)"),
        Binding("t", "toggle_hidden", "显隐非关联分支"),
        Binding("k", "move_up", "上移", show=False),
        Binding("j", "move_down", "下移", show=False),
        Binding("up", "move_up", "上移", show=False),
        Binding("down", "move_down", "下移", show=False),
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
        self.show_unreachable = True
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
        self.node_by_filename: dict[str, QuipuNode] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                yield Markdown("", id="content-body")
        yield Footer()

    def on_mount(self) -> None:
        """Loads the first page of data."""
        logger.debug("TUI: on_mount started.")
        self.query_one(Header).tall = False

        self.engine = create_engine(self.work_dir, lazy=True)
        current_output_tree_hash = self.engine.git_db.get_tree_hash()
        self.view_model = GraphViewModel(reader=self.engine.reader, current_output_tree_hash=current_output_tree_hash)
        self.view_model.initialize()

        table = self.query_one(DataTable)
        table.add_columns("Time", "Graph", "Node Info")

        # 计算 HEAD 所在的页码并跳转
        initial_page = self.view_model.calculate_initial_page()
        logger.debug(f"TUI: HEAD is on page {initial_page}. Loading...")
        self._load_page(initial_page)
        
        # 强制将焦点给到表格，确保高亮可见且键盘可用
        table.focus()

    def on_unmount(self) -> None:
        logger.debug("TUI: on_unmount called, closing engine.")
        if self.engine:
            self.engine.close()

    def _update_header(self):
        """Centralized method to update the app's title and sub_title."""
        self.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages}"

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
        self._update_header()

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

    def _refresh_table(self):
        table = self.query_one(DataTable)
        current_page_nodes = list(self.node_by_filename.values())
        sorted_nodes = sorted(current_page_nodes, key=lambda n: n.timestamp, reverse=True)
        table.clear()
        self._populate_table(table, sorted_nodes)
        self._focus_current_node(table)
        self._update_header()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        # Ensure tracks starts empty to avoid rendering artifacts from previous logic
        tracks: list[Optional[str]] = []

        for node in nodes_to_render:
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
        current_output_tree_hash = self.view_model.current_output_tree_hash
        target_node = next(
            (n for n in self.node_by_filename.values() if n.output_tree == current_output_tree_hash), None
        )
        if not target_node:
            return
        try:
            row_key = str(target_node.filename)
            if table.is_valid_row_key(row_key):
                row_index = table.get_row_index(row_key)
                # Use move_cursor for robust scrolling and highlighting
                table.move_cursor(row=row_index, animate=False)
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
TUI 的核心功能修复已完成。下一步可以考虑：
1.  **实现 `search` 功能**: 在 TUI 中添加按 `/` 键触发的搜索框。
2.  **内容视图优化**: 为右侧 Markdown 预览添加语法高亮支持。
