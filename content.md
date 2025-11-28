Excellent feedback. You've identified two critical points: user customizability and content consistency. Giving users the choice to disable a potentially slow feature is a great design principle, and ensuring both views show the same information is essential for a coherent experience.

I will generate a plan that implements all of your suggestions.

## [WIP] feat: 添加 TUI Markdown 渲染切换功能并确保内容一致性

### 用户需求
1.  **命令行配置**: 为 `quipu ui` 命令添加一个命令行选项 (例如 `--raw`)，允许用户在启动时就禁用 Markdown 渲染，直接以纯文本模式查看内容。
2.  **运行时切换**: 在 TUI 内部增加一个快捷键 (`m`)，让用户可以随时在 Markdown 渲染模式和纯文本模式之间切换。
3.  **内容一致性**: 确保无论在哪种模式下（纯文本或 Markdown），用户看到的内容信息是完全一致的，都应包含公共的计划内容和私有的开发者意图。

### 评论
这是一组非常重要的可用性改进。它将控制权交给了用户，允许那些追求极致性能或不喜欢复杂渲染的用户选择更简洁的视图。同时，通过统一数据源确保了视图间的内容一致性，解决了之前版本中预览信息不完整的问题，使整个 TUI 体验更加健壮和专业。

### 目标
1.  在 `quipu/cli/commands/ui.py` 中为 `ui` 命令添加 `--raw` 布尔选项。
2.  修改 `quipu/cli/tui.py` 中的 `QuipuUiApp`：
    *   在其 `__init__` 方法中接收一个 `initial_raw_mode` 参数。
    *   添加一个新的状态属性 `self.markdown_enabled`。
    *   添加一个新的 `Binding` (`m`) 和对应的 `action_toggle_markdown` 方法来切换此状态。
    *   修改 `_update_loading_preview` 方法，使其调用 `view_model.get_content_bundle()` 来获取包含开发者意图的完整内容，确保预览信息完整。
    *   重构 `_set_state` 方法中的 `SHOWING_CONTENT` 逻辑，根据 `self.markdown_enabled` 的值来决定是显示 `Markdown` 组件还是 `Static` 组件。

### 基本原理
我们将引入一个布尔状态 `markdown_enabled` 来控制 TUI 的渲染行为。这个状态的初始值由新的 `--raw` 命令行参数决定。

核心改动在于 TUI 的状态机。`LOADING` 状态将始终使用 `Static` 组件显示从 `ViewModel` 获取的完整内容包（公共+私有），确保了滚动时的信息完整性和高性能。当滚动停止后，`SHOWING_CONTENT` 状态会检查 `markdown_enabled` 标志：
-   如果为 `True`，它会显示 `Markdown` 组件并隐藏 `Static` 组件，进行富文本渲染。
-   如果为 `False`，它会继续显示（或重新显示）`Static` 组件并隐藏 `Markdown` 组件，维持纯文本视图。

`action_toggle_markdown` 方法会简单地翻转这个标志，并重新触发一次内容区域的渲染，从而实现即时切换。由于两种最终视图都使用 `view_model.get_content_bundle()` 作为唯一数据源，内容的一致性得到了保证。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/ui #task/object/tui-performance #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 在 `ui.py` 中添加 `--raw` 命令行选项

我们将为 `ui` 命令添加新的选项，并将其传递给 TUI 应用的构造函数。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~
~~~~~python
    def ui(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
    ):
~~~~~
~~~~~python
    def ui(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        raw: Annotated[bool, typer.Option("--raw", help="默认以纯文本模式启动，禁用 Markdown 渲染。")] = False,
    ):
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~
~~~~~python
        app_instance = QuipuUiApp(work_dir=work_dir)
        result = app_instance.run()
~~~~~
~~~~~python
        app_instance = QuipuUiApp(work_dir=work_dir, initial_raw_mode=raw)
        result = app_instance.run()
~~~~~

#### Acts 2: 更新 `tui.py` 实现渲染切换和内容一致性

这是核心修改。由于涉及构造函数、绑定、状态机等多个部分的改动，使用 `write_file` 是最安全、最清晰的方式。

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
import sys
import logging
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Markdown, Static
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual import on
from textual.timer import Timer

from quipu.core.models import QuipuNode
from quipu.core.state_machine import Engine
from .view_model import GraphViewModel
from .factory import create_engine

logger = logging.getLogger(__name__)

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = tuple[str, str]


class ContentViewSate(Enum):
    HIDDEN = auto()
    LOADING = auto()
    SHOWING_CONTENT = auto()


class QuipuUiApp(App[Optional[UiResult]]):
    CSS_PATH = "tui.css"
    TITLE = "Quipu History Explorer"

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                # Add a lightweight placeholder that we can update quickly.
                # It's used for both fast-scrolling and the "raw" text mode.
                yield Static("", id="content-placeholder", markup=False)
                # The expensive Markdown widget
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
        # If the content view is already showing, force a re-render with the new mode.
        if self.content_view_state == ContentViewSate.SHOWING_CONTENT:
            self._set_state(ContentViewSate.SHOWING_CONTENT)
        elif self.content_view_state == ContentViewSate.LOADING:
            # If it's loading, let the timer finish and it will naturally pick up the new mode.
            pass


    def action_checkout_node(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            self.exit(result=("checkout", selected_node.output_tree))

    def action_dump_content(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            content = self.view_model.get_content_bundle(selected_node)
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
        # 从 ViewModel 获取要渲染的节点
        nodes_to_render = self.view_model.get_nodes_to_render()
        self._populate_table(table, nodes_to_render)
        self._focus_current_node(table)
        self._update_header()

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        # 移除了过滤逻辑，因为 ViewModel 已经处理
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

            info_text = f"{owner_info}[{base_color}][{node.node_type.upper()}] {node.short_hash}[/{base_color}] - {summary}"
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
        logger.debug(f"DEBUG: Attempting focus. HEAD={current_output_tree_hash}")

        if not current_output_tree_hash:
            logger.debug("DEBUG: No HEAD hash, skipping.")
            return

        # 查找当前页面中匹配 HEAD 的所有节点
        matching = [
            n for n in self.view_model.current_page_nodes if n.output_tree == current_output_tree_hash
        ]
        logger.debug(f"DEBUG: Found {len(matching)} matching nodes in current page map.")

        target_node = matching[0] if matching else None
        if not target_node:
            logger.debug("DEBUG: Target node not found in current page.")
            return

        try:
            row_key = str(target_node.filename)
            logger.debug(f"DEBUG: Target row key: {row_key}")

            # Textual 的 DataTable API 中，get_row_index 会在 key 不存在时抛出 KeyError
            # 或者 RowKeyError，具体取决于版本，但 KeyError 是基类
            try:
                row_index = table.get_row_index(row_key)
                logger.debug(f"DEBUG: Row index found: {row_index}. Setting cursor.")

                # 1. 设置视觉光标
                table.cursor_coordinate = Coordinate(row=row_index, column=0)

                # 2. Sync data model state
                self.view_model.select_node_by_key(row_key)
                
                # 3. Force-update the header on initial load, regardless of view mode.
                # The state machine will handle the rest of the UI.
                header = self.query_one("#content-header", Static)
                header.update(f"[{target_node.node_type.upper()}] {target_node.short_hash} - {target_node.timestamp}")

            except LookupError:
                # LookupError 捕获 RowKeyError 等
                logger.warning(f"DEBUG: Row key {row_key} not found in DataTable.")

        except Exception as e:
            logger.error(f"DEBUG: Failed to focus current node: {e}", exc_info=True)

    def _update_loading_preview(self):
        """A lightweight method to only update header/placeholder text."""
        node = self.view_model.get_selected_node()
        if not node:
            return

        # Update header and placeholder text
        self.query_one("#content-header", Static).update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")
        
        # Always get the full content bundle for consistent information display.
        # The Static widget is in markup=False mode, so it's fast and safe.
        content_bundle = self.view_model.get_content_bundle(node)
        self.query_one("#content-placeholder", Static).update(content_bundle)
        

    def _set_state(self, new_state: ContentViewSate):
        # Allow re-entering SHOWING_CONTENT to force a re-render after toggling markdown
        if self.content_view_state == new_state and new_state != ContentViewSate.SHOWING_CONTENT:
            return

        self.content_view_state = new_state
        
        container = self.query_one("#main-container")
        placeholder_widget = self.query_one("#content-placeholder", Static)
        markdown_widget = self.query_one("#content-body", Markdown)
        
        if self.update_timer:
            self.update_timer.stop()

        match new_state:
            case ContentViewSate.HIDDEN:
                container.set_class(False, "split-mode")

            case ContentViewSate.LOADING:
                container.set_class(True, "split-mode")
                
                # Perform lightweight text updates
                self._update_loading_preview()
                
                # Perform heavy, one-time visibility setup
                placeholder_widget.display = True
                markdown_widget.display = False
                markdown_widget.update("") # Prevent ghosting

                # Start timer for next state transition
                self.update_timer = self.set_timer(self.debounce_delay_seconds, self._on_timer_finished)

            case ContentViewSate.SHOWING_CONTENT:
                container.set_class(True, "split-mode")
                node = self.view_model.get_selected_node()
                
                if node:
                    content = self.view_model.get_content_bundle(node)
                    # Update header
                    self.query_one("#content-header", Static).update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")

                    if self.markdown_enabled:
                        markdown_widget.update(content)
                        placeholder_widget.display = False
                        markdown_widget.display = True
                    else:
                        placeholder_widget.update(content)
                        placeholder_widget.display = True
                        markdown_widget.display = False
                
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # 1. Update data model
        if event.row_key.value:
            self.view_model.select_node_by_key(event.row_key.value)
        
        # 2. Handle UI updates based on current state
        if self.update_timer:
            self.update_timer.stop()

        if self.content_view_state == ContentViewSate.HIDDEN:
            return # Do nothing if panel is closed
        
        elif self.content_view_state == ContentViewSate.SHOWING_CONTENT:
            # Transition from showing content to loading
            self._set_state(ContentViewSate.LOADING)
        
        elif self.content_view_state == ContentViewSate.LOADING:
            # Already loading, just do a lightweight update and restart timer
            self._update_loading_preview()
            self.update_timer = self.set_timer(self.debounce_delay_seconds, self._on_timer_finished)

    def _on_timer_finished(self) -> None:
        """Callback for the debounce timer."""
        # The timer finished, so we are ready to show content
        self._set_state(ContentViewSate.SHOWING_CONTENT)
    
    def action_toggle_view(self) -> None:
        """Handles the 'v' key press to toggle the content view."""
        if self.content_view_state == ContentViewSate.HIDDEN:
            # If a node is selected, transition to loading, otherwise do nothing
            if self.view_model.get_selected_node():
                self._set_state(ContentViewSate.LOADING)
        else:
            self._set_state(ContentViewSate.HIDDEN)
~~~~~

### 下一步建议
我们已经完成了一个相当大的功能集：
1.  修复了滚动时的崩溃问题。
2.  实现了命令行启动选项 `--raw`。
3.  实现了 TUI 内的 `m` 键切换渲染模式。
4.  确保了两种视图模式下的内容完全一致。

请运行 `qd ui` 和 `qd ui --raw` 进行全面测试。如果一切符合预期，这标志着 TUI 性能和可用性优化的宏观任务已完成，我们可以创建一个 `[COMMIT]` 计划来总结并提交这些成果。
