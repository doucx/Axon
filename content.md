这是一个非常深刻的系统设计问题。你的直觉是对的：之前的“纯异步+全量防抖”方案虽然解决了技术上的“I/O 阻塞”和“闪烁”，但破坏了用户体验的**连续性**和**直观性**。

我将分析之前状态机模式的优点，诊断当前模式的缺陷，并提出一个符合现代 UI 开发标准的**“渐进式增强 (Progressive Enhancement)”** 模式。

### 1. 深度分析：为什么之前的“状态机”某种程度上是好的？

之前的代码（`HIDDEN` -> `LOADING` -> `SHOWING`）虽然有闪烁，但它无意中实现了一个重要特性：**即时反馈层级**。

*   **它解决了什么？** 它承认了“加载”是一个过程。当你滚动时，它虽然清空了旧内容（闪烁），但它同时也**卸载了沉重的 Markdown 组件**，回到了轻量级的状态。
*   **用户的心理模型**：用户在快速浏览历史时，潜意识里是在进行“扫视”。他们不需要看到完美的渲染，他们需要看到**数据流**。之前的模式在 `LOADING` 阶段可能会更新一个轻量级的 `placeholder`（即使只是短暂的），这给用户一种“我在穿越数据”的速度感。

### 2. 当前“异步+防抖”模式的致命缺陷

目前的模式（保持旧内容 -> 等待停止 -> 加载新内容）实际上引入了**“状态解离 (State Dissociation)”**。

*   **视觉欺骗**：当你从 A 滚动到 B 时，Header 变成了 B，但内容体依然显示 A。这在 UI 设计中被称为 **“Stale Content” (陈旧内容)** 问题。这比“闪烁”更糟糕，因为它传递了**错误的信息**。
*   **丢失了“浏览感”**：由于采用了激进的防抖（debounce），在滚动过程中，中间节点的数据获取被完全切断了。用户感觉像是在操作一个“死”的界面，只有停下来它才“活”过来。这对于需要快速定位（比如通过肉眼扫视代码片段）的场景是灾难性的。

### 3. 标准与优雅的解法：渐进式渲染 (Progressive Rendering)

要解决这个问题，我们需要借鉴现代浏览器或高性能 IDE（如 VS Code）处理大文件预览的策略：**将“数据获取”与“富文本渲染”解耦。**

我们不再把加载看作一个单一的原子操作，而是将其拆分为两个阶段：

*   **阶段一：数据获取 (Fetch) —— 高优先级、低延迟**
    *   从 Git/SQLite 读取纯文本内容通常是非常快的（毫秒级）。
    *   **策略**：这部分**不应该防抖**（或者使用极短的防抖，如 10ms），而应该使用**“可取消的并发任务 (Cancellable Concurrency)”**。只要用户滚动，就立即去读文本。

*   **阶段二：富文本渲染 (Render) —— 低优先级、高消耗**
    *   将纯文本解析为 Markdown 并布局渲染是昂贵的（可能几十到几百毫秒）。
    *   **策略**：这部分**必须防抖**。只有当数据获取完成，且用户似乎停留在该节点时，才触发 Markdown 渲染。

#### 新的 UI 状态流转图

1.  **用户滚动到节点 B**。
2.  **立即动作**：
    *   更新 Header。
    *   **视图切换**：立即将内容区域从 `Markdown` 组件切换回轻量级的 `Static` (纯文本) 组件。
    *   **启动 Worker**：去后台读取节点 B 的内容。
3.  **用户继续滚动到节点 C**：
    *   取消节点 B 的 Worker。
    *   启动节点 C 的 Worker。
4.  **用户在节点 C 暂停**：
    *   **Worker 完成**：节点 C 的纯文本读取完毕。
    *   **UI 更新 (阶段一)**：更新 `Static` 组件显示节点 C 的源码。**用户此时看到了正确的、最新的内容（虽然是纯文本）。**
    *   **启动渲染计时器**：开始 0.2s 的倒计时。
5.  **计时器结束**：
    *   **UI 更新 (阶段二)**：在后台渲染 Markdown，完成后将视图从 `Static` 切换到 `Markdown` 组件。

### 4. 为什么这个方案优雅？

1.  **消除了“陈旧内容”**：只要开始滚动，我们就切换回 `Static` 视图（哪怕先显示“Loading...”），用户立刻知道“旧内容已去，新内容在来”。
2.  **找回了“纯文本浏览”**：由于读取文本很快且不防抖，当用户中速滚动时，他们能看到纯文本内容像流一样更新。这就是你想要的“cherry-pick”体验。
3.  **保持了高性能**：最昂贵的 Markdown 渲染依然被防抖保护着，不会阻塞 UI 线程。

这是标准的**双缓冲 (Double Buffering)** 或 **LOD (Level of Detail)** 策略在 TUI 中的应用。

## [WIP] refactor(cli): 重构 TUI 为渐进式渲染架构

### 用户需求
1.  **消除陈旧内容**：滚动时不要一直显示上一个节点的内容。
2.  **恢复快速浏览体验**：在快速移动时，能够看到纯文本内容的实时更新（像旧版一样），而不是界面冻结。
3.  **最终一致性**：停止滚动后，自动升级为美观的 Markdown 渲染。

### 目标
1.  重构 `tui.py`，引入 `ContentSwitcher` 来管理 `Raw` (纯文本) 和 `Markdown` (富文本) 两种视图。
2.  实现**双轨异步模型**：
    *   **Fetch Track (数据轨)**：使用 Textual 的 `exclusive` worker，**不防抖**，负责快速读取文本并更新 `Raw` 视图。
    *   **Render Track (渲染轨)**：使用 `Timer` 防抖，负责将 `Raw` 视图的内容升级为 `Markdown` 视图。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/ui #task/object/tui-progressive-loader #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `tui.py` 实现渐进式渲染

我们将引入 `ContentSwitcher`，并重新设计事件处理逻辑。

~~~~~act
write_file packages/quipu-cli/src/pyquipu/cli/tui.py
~~~~~
~~~~~python
import logging
from functools import partial
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
from textual.widgets import ContentSwitcher, DataTable, Footer, Header, Markdown, Static

from .factory import create_engine
from .view_model import GraphViewModel

logger = logging.getLogger(__name__)

# 定义 UI 返回类型: (动作类型, 数据)
UiResult = tuple[str, str]


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

        # --- UI State ---
        self.markdown_enabled = not initial_raw_mode
        self.is_details_visible = False

        # --- Async State ---
        self._render_timer: Optional[Timer] = None
        self._current_request_id: int = 0
        # 渲染防抖延迟，数据获取(Fetch)不防抖
        self._render_delay: float = 0.2

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                
                # 使用 ContentSwitcher 管理多态视图
                # 默认显示 raw-view (轻量级)
                with ContentSwitcher(initial="content-raw", id="content-switcher"):
                    yield Static("", id="content-raw", markup=False)
                    yield Markdown("", id="content-body")
                    
        yield Footer()

    def on_mount(self) -> None:
        """初始化数据并加载第一页"""
        logger.debug("TUI: on_mount started.")
        self.query_one(Header).tall = False

        # Lazy load engine
        self.engine = create_engine(self.work_dir, lazy=True)
        current_output_tree_hash = self.engine.git_db.get_tree_hash()
        self.view_model = GraphViewModel(reader=self.engine.reader, current_output_tree_hash=current_output_tree_hash)
        self.view_model.initialize()

        table = self.query_one(DataTable)
        table.add_columns("Time", "Graph", "Node Info")

        # 计算 HEAD 所在的页码并跳转
        initial_page = self.view_model.calculate_initial_page()
        self._load_page(initial_page)

        # 初始 UI 状态设置
        self._update_header_title()
        self._update_visibility_classes()

        table.focus()

    def on_unmount(self) -> None:
        if self.engine:
            self.engine.close()

    def _update_header_title(self):
        """更新顶部状态栏"""
        mode = "Markdown" if self.markdown_enabled else "Raw Text"
        self.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages} | View: {mode} (m)"

    def _update_visibility_classes(self):
        """根据当前状态控制面板显隐"""
        container = self.query_one("#main-container")
        container.set_class(self.is_details_visible, "split-mode")

    # --- Actions ---
    
    def action_move_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_move_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_toggle_hidden(self) -> None:
        self.view_model.toggle_unreachable()
        self._refresh_table()

    def action_toggle_markdown(self) -> None:
        self.markdown_enabled = not self.markdown_enabled
        self._update_header_title()
        
        # 切换模式时，如果已打开详情页，强制触发一次渲染更新
        if self.is_details_visible:
            self._try_upgrade_to_markdown()

    def action_toggle_view(self) -> None:
        self.is_details_visible = not self.is_details_visible
        self._update_visibility_classes()
        # 打开视图时，立即触发当前选中节点的内容加载
        if self.is_details_visible:
            node = self.view_model.get_selected_node()
            if node:
                self._trigger_progressive_load(node)

    def action_checkout_node(self) -> None:
        selected_node = self.view_model.get_selected_node()
        if selected_node:
            self.exit(result=("checkout", selected_node.output_tree))

    def action_dump_content(self) -> None:
        """仅输出公共内容 (Cherry-pick)"""
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

    # --- Data & Rendering Logic ---

    def _load_page(self, page_number: int) -> None:
        self.view_model.load_page(page_number)
        self._refresh_table()

    def _refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()
        nodes_to_render = self.view_model.get_nodes_to_render()
        self._populate_table(table, nodes_to_render)
        self._focus_current_node(table)
        self._update_header_title()

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
            
            owner_info = ""
            if node.owner_id:
                owner_info = f"[yellow]({node.owner_id[:12]}) [/yellow]"

            info_text = f"{owner_info}[{base_color}][{node.node_type.upper()}] {node.short_hash}[/{base_color}] - {node.summary or 'No description'}"
            info_str = f"{dim_tag}{info_text}{end_dim_tag}"
            
            table.add_row(ts_str, "".join(graph_chars), info_str, key=str(node.filename))

    def _get_graph_chars(self, tracks: list, node: QuipuNode, base_color: str, dim_tag: str, end_dim_tag: str) -> list[str]:
        # Graph 渲染逻辑
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

    def _focus_current_node(self, table: DataTable):
        current_hash = self.view_model.current_output_tree_hash
        if not current_hash:
            return

        matching = [n for n in self.view_model.current_page_nodes if n.output_tree == current_hash]
        if not matching:
            return

        try:
            target_node = matching[0]
            row_key = str(target_node.filename)
            row_index = table.get_row_index(row_key)
            table.cursor_coordinate = Coordinate(row=row_index, column=0)
            
            self.view_model.select_node_by_key(row_key)
            if self.is_details_visible:
                # 初始加载，无需动画
                self._trigger_progressive_load(target_node)
        except LookupError:
            pass

    # --- Progressive Loading Architecture ---

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """
        核心交互逻辑：
        1. 立即更新 ViewModel 选中状态
        2. 立即更新 Header (Metadata)
        3. 启动渐进式内容加载 (Fetch -> Render)
        """
        if event.row_key.value:
            node = self.view_model.select_node_by_key(event.row_key.value)
            
            # Step 1: Immediate Metadata Feedback
            if node and self.is_details_visible:
                self._update_header_ui(node)
                # Step 2: Trigger Progressive Load
                self._trigger_progressive_load(node)

    def _update_header_ui(self, node: QuipuNode):
        """同步更新 Header，保证跟手性"""
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp.strftime('%Y-%m-%d %H:%M')}")

    def _trigger_progressive_load(self, node: QuipuNode):
        """
        启动渐进式加载流程：
        1. 立即切换到 Raw View (避免显示陈旧的 Markdown)
        2. 启动独占 Worker 获取内容 (无防抖，低延迟)
        3. 重置 Markdown 渲染计时器
        """
        # 1. 立即降级到 Raw View
        # 这消除了“陈旧内容”问题：用户看到的是正在加载或刚加载好的 Raw Text
        self.query_one("#content-switcher", ContentSwitcher).current = "content-raw"
        
        # 2. 停止之前的渲染计时器 (如果存在)
        if self._render_timer:
            self._render_timer.stop()
            self._render_timer = None

        # 3. 启动数据获取 Worker (Textual 会自动取消同组旧 Worker)
        self._current_request_id += 1
        req_id = self._current_request_id
        
        worker_func = partial(self._fetch_content_bg, node, req_id)
        self.run_worker(
            worker_func, 
            thread=True, 
            group="content_fetcher", 
            exclusive=True
        )

    def _fetch_content_bg(self, node: QuipuNode, req_id: int):
        """后台线程：快速读取文本内容"""
        try:
            # 耗时 I/O 操作
            content = self.view_model.get_content_bundle(node)
            # 调度回主线程
            self.call_from_thread(self._on_content_fetched, content, req_id)
        except Exception as e:
            logger.error(f"Fetch failed: {e}")

    def _on_content_fetched(self, content: str, req_id: int):
        """
        主线程：内容获取完成 (Stage 1 Complete)
        此时我们有了最新的纯文本，立即显示它，并安排 Markdown 渲染。
        """
        if req_id != self._current_request_id:
            return # 结果已过时

        # 1. 更新 Raw View (这是用户滚动时看到的内容)
        self.query_one("#content-raw", Static).update(content)
        
        # 2. 安排升级到 Markdown (Stage 2)
        if self.markdown_enabled:
            # 启动防抖计时器
            self._render_timer = self.set_timer(
                self._render_delay, 
                partial(self._upgrade_to_markdown, content, req_id)
            )

    def _upgrade_to_markdown(self, content: str, req_id: int):
        """
        主线程：执行昂贵的 Markdown 渲染 (Stage 2 Complete)
        """
        if req_id != self._current_request_id:
            return

        # 1. 更新 Markdown 组件 (Textual 会在此时解析 Markdown)
        self.query_one("#content-body", Markdown).update(content)
        
        # 2. 切换视图
        self.query_one("#content-switcher", ContentSwitcher).current = "content-body"

    def _try_upgrade_to_markdown(self):
        """辅助方法：在切换开关时手动触发升级"""
        if not self.markdown_enabled:
            self.query_one("#content-switcher", ContentSwitcher).current = "content-raw"
            return
            
        # 如果当前 Raw View 有内容，尝试渲染它
        raw_content = str(self.query_one("#content-raw", Static).renderable)
        if raw_content:
            self.query_one("#content-body", Markdown).update(raw_content)
            self.query_one("#content-switcher", ContentSwitcher).current = "content-body"

~~~~~
