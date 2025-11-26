好的，我将开始执行 `阶段三：前端 UI 适配 (View Layer)`。

此阶段的核心目标是改造 `quipu-cli` 中的 TUI (`tui.py`) 和其入口 (`main.py`)，使其与 `GraphViewModel` 对接，实现按需分页加载、无限滚动和私有数据显示，从而解决 UI 启动慢和内存占用高的问题。

## `refactor`: 适配 ViewModel 实现 UI 分页加载

### 用户需求

用户 `[已屏蔽]` 提出，当项目历史记录变得庞大时 (`>1000` 个节点)，`quipu ui` 命令的启动时间会变得无法接受，从毫秒级增长到数秒。同时，一次性加载所有节点对象到内存中，也造成了不必要的资源浪费。

根据 `Quipu UI 性能优化与功能增强设计方案`，需要完成前端 UI 的适配工作，实现按需分页加载。

### 评论

这是一个关键的重构步骤，它将彻底解决 UI 的性能瓶颈，为 Quipu 管理大规模、长周期的项目奠定基础。通过引入 `GraphViewModel` 作为中间层，我们可以在不改变 UI 整体布局和核心交互（如快捷键）的前提下，将数据加载逻辑与视图渲染逻辑解耦，提升了代码的可维护性。

### 目标

1.  将 `quipu-cli/src/quipu/cli/tui.py` 中的 `QuipuUiApp` 重构为使用 `GraphViewModel` 作为其唯一数据源。
2.  实现“无限滚动”功能，当用户滚动到列表底部时，自动异步加载下一页数据。
3.  在节点内容预览区，合并显示公共计划 (`plan.md`) 和私有开发者意图 (`intent.md`)。
4.  更新 `quipu-cli/src/quipu/cli/main.py` 中的 `ui` 命令，使其通过 `GraphViewModel` 来启动 TUI。
5.  确保所有现有的 UI 快捷键 (`j`, `k`, `c`, `v`, `p`, `h`) 和核心功能在新架构下依然可用。

### 基本原理

本次重构遵循 **MVVM (Model-View-ViewModel)** 设计模式。
*   **Model**: `HistoryReader` 接口及其 `SQLiteHistoryReader` 实现，负责底层数据访问。
*   **ViewModel**: `GraphViewModel` 类，封装了分页状态管理、数据加载、可达性分析和内容格式化等业务逻辑。
*   **View**: `QuipuUiApp` 类，其职责被简化为仅负责渲染 ViewModel 提供的数据，并将用户输入事件（如滚动、按键）传递给 ViewModel。

通过这种方式，`tui.py` 变得更加纯粹，只关心“如何展示”，而将“展示什么”和“如何获取”的复杂性完全交给 `ViewModel`。我们使用 Textual 的 `@work` 装饰器来执行后台数据加载，避免了数据库查询阻塞 UI 线程，保证了界面的流畅性。

### 标签

#intent/refine #flow/ready #priority/high
#comp/cli #concept/ui #scope/ux
#ai/instruct
#task/domain/ui
#task/object/pagination
#task/action/integration
#task/state/continue
#task/status/active

---

### Script

#### Acts 1: 扩展 ViewModel

首先，为 `GraphViewModel` 添加一个 `reset_pagination` 方法。这个方法是实现 `toggle_hidden` 功能所必需的，它允许 UI 在切换可见性过滤器后，能重置加载状态并从头开始重新拉取数据。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/view_model.py
~~~~~
~~~~~python
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
~~~~~python
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

    def reset_pagination(self):
        """重置分页状态，以便可以从头开始重新加载。"""
        self.offset = 0
        self.loaded_nodes = []
~~~~~

#### Acts 2: 重构 TUI 实现分页加载

接下来，我们将完全重写 `tui.py`。新的实现将围绕 `GraphViewModel` 构建，移除所有旧的数据加载和状态管理逻辑，并替换为基于 `worker` 的异步分页加载和无限滚动机制。

~~~~~act
write_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
import sys
from typing import List, Optional, Tuple, Dict
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Markdown, Static
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual import on, work

from quipu.core.models import QuipuNode
from .view_model import GraphViewModel

# 定义 UI 返回类型: (动作类型, 数据)
# 动作: "checkout" | "dump"
UiResult = Tuple[str, str]


class QuipuUiApp(App[Optional[UiResult]]):
    CSS = """
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
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("v", "toggle_view", "切换内容视图"),
        Binding("p", "dump_content", "输出内容(stdout)"),
        Binding("h", "toggle_hidden", "显隐非关联分支"),
        # Vim 风格导航
        Binding("k", "move_up", "上移", show=False),
        Binding("j", "move_down", "下移", show=False),
        Binding("up", "move_up", "上移", show=False),
        Binding("down", "move_down", "下移", show=False),
    ]

    def __init__(self, view_model: GraphViewModel):
        super().__init__()
        self.view_model = view_model
        self.node_by_filename: Dict[str, QuipuNode] = {}
        self.is_split_mode = False
        self.current_selected_node: Optional[QuipuNode] = None
        self.show_unreachable = True
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                yield Markdown("", id="content-body")
        yield Footer()

    def on_mount(self) -> None:
        self.run_load(is_initial=True)

    @work(exclusive=True, group="data_loader")
    async def run_load(self, is_initial: bool = False):
        if self._loading:
            return

        if is_initial:
            self.query_one(Footer).push_status("正在初始化...")
            self.view_model.initialize()
            self.query_one(Footer).pop_status()

        if not self.view_model.has_more_data():
            return

        self._loading = True
        self.query_one(Footer).push_status("正在加载...")

        new_nodes = self.view_model.load_next_page()

        def update_ui():
            if is_initial:
                self._reset_and_populate_table(new_nodes)
            elif new_nodes:
                self._append_to_table(new_nodes)
            self.query_one(Footer).pop_status()
            self._loading = False

        self.call_from_thread(update_ui)

    # --- Actions ---

    def action_move_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.show_unreachable = not self.show_unreachable
        self.view_model.reset_pagination()
        self.node_by_filename.clear()
        self.run_load(is_initial=True)

    def action_toggle_view(self) -> None:
        self.is_split_mode = not self.is_split_mode
        container = self.query_one("#main-container")
        container.toggle_class("split-mode")
        if self.is_split_mode:
            self._update_content_view()

    def action_checkout_node(self) -> None:
        if self.current_selected_node:
            self.exit(result=("checkout", self.current_selected_node.output_tree))

    def action_dump_content(self) -> None:
        if self.current_selected_node:
            content = self.view_model.reader.get_node_content(self.current_selected_node)
            self.exit(result=("dump", content))

    # --- UI Logic ---

    def _reset_and_populate_table(self, nodes_to_render: List[QuipuNode]):
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Time", "Graph", "Node Info")
        self._append_to_table(nodes_to_render)
        self._focus_current_node(table)

    def _append_to_table(self, nodes_to_render: List[QuipuNode]):
        table = self.query_one(DataTable)
        tracks: List[Optional[str]] = []
        for node in nodes_to_render:
            self.node_by_filename[str(node.filename)] = node
            is_reachable = self.view_model.is_reachable(node.output_tree)
            if not self.show_unreachable and not is_reachable:
                continue

            dim_tag = "[dim]" if not is_reachable else ""
            end_dim_tag = "[/dim]" if dim_tag else ""

            base_color = "magenta"
            if node.node_type == "plan":
                base_color = "green" if node.input_tree == node.output_tree else "cyan"

            graph_chars = self._render_graph_line(tracks, node, dim_tag, end_dim_tag, base_color)
            ts_str = f"{dim_tag}{node.timestamp.strftime('%Y-%m-%d %H:%M')}{end_dim_tag}"
            info_str = f"{dim_tag}[{base_color}][{node.node_type.upper()}] {node.short_hash}[/{base_color}] - {node.summary or 'No description'}{end_dim_tag}"

            table.add_row(ts_str, "".join(graph_chars), info_str, key=str(node.filename))

    def _render_graph_line(
        self, tracks: List[Optional[str]], node: QuipuNode, dim_tag: str, end_dim_tag: str, base_color: str
    ) -> List[str]:
        merging_indices = [i for i, h in enumerate(tracks) if h == node.output_tree]
        try:
            col_idx = tracks.index(None) if not merging_indices else merging_indices[0]
        except ValueError:
            col_idx = len(tracks) if not merging_indices else merging_indices[0]

        while len(tracks) <= col_idx:
            tracks.append(None)
        tracks[col_idx] = node.output_tree

        graph_chars = []
        for i, track_hash in enumerate(tracks):
            if i == col_idx:
                symbol_char = "●" if node.node_type == "plan" else "○"
                graph_chars.append(f"{dim_tag}[{base_color}]{symbol_char}[/] {end_dim_tag}")
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

    def _focus_current_node(self, table: DataTable):
        if not self.view_model.current_hash:
            return
        
        # Best-effort: find the current node in the already loaded data
        for node in self.view_model.loaded_nodes:
            if node.output_tree == self.view_model.current_hash:
                try:
                    row_index = table.get_row_index(str(node.filename))
                    table.cursor_coordinate = Coordinate(row=row_index, column=0)
                    self.current_selected_node = node
                    return
                except Exception:
                    pass

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if node := self.node_by_filename.get(row_key):
            self.current_selected_node = node
            if self.is_split_mode:
                self._update_content_view()

    @on(DataTable.Scrolled)
    def on_scrolled(self, event: DataTable.Scrolled) -> None:
        # Trigger load when scrollbar is near the bottom
        if event.y + event.visible_size >= event.virtual_size - 10:
            self.run_load()

    def _update_content_view(self):
        if not self.current_selected_node:
            return

        node = self.current_selected_node
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")
        
        content_bundle = self.view_model.get_content_bundle(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content_bundle)
~~~~~

#### Acts 3: 更新 CLI 入口

最后，修改 `main.py` 中的 `ui` 命令。它将不再加载所有节点，而是创建 `GraphViewModel` 实例并将其传递给 `QuipuUiApp`。同时，为了健壮性，移除了在 UI 返回后对 `engine.history_graph` 的冗余检查。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
@app.command()
def ui(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
):
    """
    以交互式 TUI 模式显示 Axon 历史图谱。
    """
    try:
        from .tui import QuipuUiApp
    except ImportError:
        typer.secho("❌ TUI 依赖 'textual' 未安装。", fg=typer.colors.RED, err=True)
        typer.secho("💡 请运行: pip install 'textual>=0.58.0'", err=True)
        ctx.exit(1)

    setup_logging()

    engine = create_engine(work_dir)
    all_nodes = engine.reader.load_all_nodes()

    if not all_nodes:
        typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
        ctx.exit(0)

    graph = engine.history_graph
    current_hash = engine.git_db.get_tree_hash()

    # 定义内容加载器闭包，供 UI 按需调用
    def content_loader(node: QuipuNode) -> str:
        return engine.reader.get_node_content(node)

    # 注入 loader
    app_instance = QuipuUiApp(all_nodes, content_loader=content_loader, current_hash=current_hash)
    result = app_instance.run()

    # 处理 UI 返回结果
    if result:
        action, data = result

        if action == "checkout":
            target_hash = data
            if target_hash in graph:
                typer.secho(f"\n> TUI 请求检出到: {target_hash[:7]}", err=True)
                _execute_visit(ctx, engine, target_hash, f"正在导航到 TUI 选定节点: {target_hash[:7]}")
            else:
                typer.secho(f"❌ 错误: 无法在历史图谱中找到目标哈希 {target_hash[:7]}", fg=typer.colors.RED, err=True)
                ctx.exit(1)

        elif action == "dump":
            # 直接将内容打印到 stdout，方便用户通过管道处理 (e.g. quipu ui | less)
            print(data)
            ctx.exit(0)
~~~~~
~~~~~python
@app.command()
def ui(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
):
    """
    以交互式 TUI 模式显示 Axon 历史图谱。
    """
    try:
        from .tui import QuipuUiApp
        from .view_model import GraphViewModel
    except ImportError:
        typer.secho("❌ TUI 依赖 'textual' 未安装。", fg=typer.colors.RED, err=True)
        typer.secho("💡 请运行: pip install 'textual>=0.58.0'", err=True)
        ctx.exit(1)

    setup_logging()

    engine = create_engine(work_dir)

    if engine.reader.get_node_count() == 0:
        typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
        ctx.exit(0)

    current_hash = engine.git_db.get_tree_hash()

    # 实例化 ViewModel 作为 TUI 的数据源
    view_model = GraphViewModel(reader=engine.reader, current_hash=current_hash)

    # 注入 ViewModel
    app_instance = QuipuUiApp(view_model)
    result = app_instance.run()

    # 处理 UI 返回结果
    if result:
        action, data = result

        if action == "checkout":
            target_hash = data
            typer.secho(f"\n> TUI 请求检出到: {target_hash[:7]}", err=True)
            _execute_visit(ctx, engine, target_hash, f"正在导航到 TUI 选定节点: {target_hash[:7]}")

        elif action == "dump":
            # 直接将内容打印到 stdout，方便用户通过管道处理 (e.g. quipu ui | less)
            print(data)
            ctx.exit(0)
~~~~~
