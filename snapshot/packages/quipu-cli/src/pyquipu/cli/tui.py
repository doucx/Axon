import itertools
import logging
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from pyquipu.engine.state_machine import Engine
from pyquipu.interfaces.models import QuipuNode
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Header, Markdown, Static
from textual.worker import Worker, work

from .factory import create_engine
from .view_model import GraphViewModel

logger = logging.getLogger(__name__)

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = tuple[str, str]


class ContentViewSate(Enum):
    HIDDEN = auto()
    # LOADING 状态在异步模型中不再需要显式清空内容，
    # 但我们保留它用于表示“正在等待后台结果”的逻辑状态（例如显示加载指示器，虽然目前不显示）
    # 或者简单地，我们可以简化为 SHOWING 和 HIDDEN，因为内容总是存在的。
    # 为了保持逻辑清晰，我们主要使用 HIDDEN 和 ACTIVE (SHOWING)。
    SHOWING_CONTENT = auto()


class QuipuUiApp(App[Optional[UiResult]]):
    CSS_PATH = "tui.css"
    TITLE = "Quipu History Explorer"

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("space", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("v", "toggle_view", "切换内容视图"),
        Binding("m", "toggle_markdown", "切换 Markdown 渲染"),
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

    def __init__(self, work_dir: Path, initial_raw_mode: bool = False):
        super().__init__()
        self.work_dir = work_dir
        self.engine: Optional[Engine] = None
        self.view_model: Optional[GraphViewModel] = None

        # --- State Machine ---
        self.content_view_state = ContentViewSate.HIDDEN
        self.update_timer: Optional[Timer] = None
        self.debounce_delay_seconds: float = 0.15
        self.markdown_enabled = not initial_raw_mode

        # --- Async Coordination ---
        self.request_id_gen = itertools.count()
        self.current_request_id = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                # Header 用于显示当前选中的节点信息，即使内容还没加载出来
                yield Static("Node Content", id="content-header")
                
                # Placeholder 用于 Raw 模式显示
                yield Static("", id="content-placeholder", markup=False)
                
                # Markdown 用于渲染模式显示
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
        mode = "Markdown" if self.markdown_enabled else "Raw Text"
        self.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages} | View: {mode} (m)"

    def _load_page(self, page_number: int) -> None:
        """Loads and displays a specific page of nodes."""
        logger.debug(f"TUI: Loading page {page_number}")
        self.view_model.load_page(page_number)
        logger.debug(f"TUI: Page {page_number} loaded with {len(self.view_model.current_page_nodes)} nodes.")

        table = self.query_one(DataTable)
        table.clear()
        # 从 ViewModel 获取过滤后的节点列表进行渲染
        self._populate_table(table, self.view_model.get_nodes_to_render())
        self._focus_current_node(table)
        self._update_header()

    def action_move_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.view_model.toggle_unreachable()
        self._refresh_table()

    def action_toggle_markdown(self) -> None:
        """Toggles the rendering mode between Markdown and raw text."""
        self.markdown_enabled = not self.markdown_enabled
        self._update_header()
        
        # 切换模式时，如果当前视图是打开的，强制刷新内容
        if self.content_view_state == ContentViewSate.SHOWING_CONTENT:
             # 我们通过重新触发加载逻辑来刷新，这会使用正确的渲染模式
            self._trigger_content_load()

    def action_checkout_node(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            self.exit(result=("checkout", selected_node.output_tree))

    def action_dump_content(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            content = self.view_model.get_public_content(selected_node)
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
        table.clear()
        nodes_to_render = self.view_model.get_nodes_to_render()
        self._populate_table(table, nodes_to_render)
        self._focus_current_node(table)
        self._update_header()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        tracks: list[Optional[str]] = []

        for node in nodes:
            is_reachable = self.view_model.is_reachable(node.output_tree)
            dim_tag = "[dim]" if not is_reachable else ""
            end_dim_tag = "[/dim]" if dim_tag else ""
            base_color = "magenta"
            if node.node_type == "plan":
                base_color = "green" if node.input_tree == node.output_tree else "cyan"
            graph_chars = self._get_graph_chars(tracks, node, base_color, dim_tag, end_dim_tag)
            ts_str = f"{dim_tag}{node.timestamp.strftime('%Y-%m-%d %H:%M')}{end_dim_tag}"
            summary = self._get_node_summary(node)

            owner_info = ""
            if node.owner_id:
                owner_display = node.owner_id[:12]
                owner_info = f"[yellow]({owner_display}) [/yellow]"

            info_text = (
                f"{owner_info}[{base_color}][{node.node_type.upper()}] {node.short_hash}[/{base_color}] - {summary}"
            )
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
        if not current_output_tree_hash:
            return

        matching = [n for n in self.view_model.current_page_nodes if n.output_tree == current_output_tree_hash]
        target_node = matching[0] if matching else None
        if not target_node:
            return

        try:
            row_key = str(target_node.filename)
            try:
                row_index = table.get_row_index(row_key)
                table.cursor_coordinate = Coordinate(row=row_index, column=0)
                self.view_model.select_node_by_key(row_key)
                
                # 初始化时也触发一次内容更新
                self._update_header_info_only(target_node)
                self._trigger_content_load()

            except LookupError:
                pass

        except Exception as e:
            logger.error(f"DEBUG: Failed to focus current node: {e}", exc_info=True)

    # --- Async Content Loading Logic ---

    @work(exclusive=True, group="content_loader")
    async def load_content_task(self, node: QuipuNode, request_id: int) -> tuple[int, str]:
        """
        后台 Worker：负责从 ViewModel 加载内容。
        这是耗时操作，不应阻塞 UI。
        """
        # 模拟可能的耗时（实际上文件读取就是 I/O）
        content = self.view_model.get_content_bundle(node)
        return request_id, content

    def on_load_content_task_finished(self, worker: Worker) -> None:
        """
        当后台加载任务完成时被 Textual 调用。
        在这里进行请求 ID 校验和 UI 更新。
        """
        try:
            request_id, content = worker.result
        except Exception:
            # 如果任务被取消或出错，直接忽略
            return

        # 核心协调逻辑：如果这个结果对应的请求不是当前最新的请求，丢弃它
        if request_id != self.current_request_id:
            logger.debug(f"Discarding stale content result for req_id {request_id} (current: {self.current_request_id})")
            return
            
        # 如果视图已经关闭，也不再更新
        if self.content_view_state == ContentViewSate.HIDDEN:
            return

        self._update_content_ui(content)

    def _update_content_ui(self, content: str):
        """执行原子化的 UI 内容替换"""
        placeholder_widget = self.query_one("#content-placeholder", Static)
        markdown_widget = self.query_one("#content-body", Markdown)

        if self.markdown_enabled:
            markdown_widget.update(content)
            placeholder_widget.display = False
            markdown_widget.display = True
        else:
            placeholder_widget.update(content)
            placeholder_widget.display = True
            markdown_widget.display = False

    def _update_header_info_only(self, node: QuipuNode):
        """轻量级更新：仅更新标题栏，不涉及内容读取"""
        self.query_one("#content-header", Static).update(
            f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}"
        )

    def _trigger_content_load(self):
        """
        启动加载流程：
        1. 停止之前的计时器
        2. 生成新 ID
        3. 启动后台 Worker
        """
        if self.update_timer:
            self.update_timer.stop()

        node = self.view_model.get_selected_node()
        if not node:
            return

        # 生成新的请求 ID，宣告之前的请求作废
        self.current_request_id = next(self.request_id_gen)
        logger.debug(f"Triggering content load for node {node.short_hash} with req_id {self.current_request_id}")
        
        # 启动后台任务
        self.load_content_task(node, self.current_request_id)

    # --- Event Handlers ---

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # 1. Update data model
        if event.row_key.value:
            node = self.view_model.select_node_by_key(event.row_key.value)
            if node:
                # 立即更新 Header，提供即时反馈
                self._update_header_info_only(node)

        # 2. Debounce Logic
        # 停止之前的计时器（如果存在）
        if self.update_timer:
            self.update_timer.stop()

        if self.content_view_state == ContentViewSate.HIDDEN:
            return

        # 启动新的防抖计时器
        # 注意：这里我们不再清空内容面板！旧内容会一直保留，直到新内容加载完毕。
        self.update_timer = self.set_timer(self.debounce_delay_seconds, self._on_timer_finished)

    def _on_timer_finished(self) -> None:
        """当用户停止滚动时触发。"""
        # 只有在计时器真正走完时，才触发昂贵的加载操作
        self._trigger_content_load()

    def action_toggle_view(self) -> None:
        """Handles the 'v' key press to toggle the content view."""
        container = self.query_one("#main-container")
        
        if self.content_view_state == ContentViewSate.HIDDEN:
            # 打开视图
            self.content_view_state = ContentViewSate.SHOWING_CONTENT
            container.set_class(True, "split-mode")
            
            # 立即触发加载
            node = self.view_model.get_selected_node()
            if node:
                self._update_header_info_only(node)
                self._trigger_content_load()
        else:
            # 关闭视图
            self.content_view_state = ContentViewSate.HIDDEN
            container.set_class(False, "split-mode")
            # 停止任何正在进行的加载计时器
            if self.update_timer:
                self.update_timer.stop()