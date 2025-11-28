你的洞察力非常精准。你说得对，即使是更新一个简短的 `placeholder`，只要目标是 `Markdown` 组件，就会触发其内部的解析和渲染管线，这本身就是性能开销的主要来源。快速滚动时，这种开销累积起来依然会导致卡顿。

引入一个新的、更轻量的 `Widget` 来专门显示占位符是解决这个问题的根本方法。我们不需要创建一个全新的 widget 类，`textual` 内置的 `Static` widget 就是为此设计的完美组件，它的 `update()` 操作开销极低。

我们将采用一个经典的高性能 UI 模式：**双组件切换**。

1.  **视图层**: 在同一个容器里，并排放置一个 `Markdown` 组件 (用于显示最终内容) 和一个 `Static` 组件 (用于显示轻量占位符)。
2.  **控制层**: 在任何时候，只让其中一个组件可见。滚动时，显示 `Static` 并更新其内容；加载完成后，更新 `Markdown` 的内容，然后隐藏 `Static`，显示 `Markdown`。

这个方案可以彻底解决性能问题。

## [WIP] refactor: 引入 Static 组件作为轻量占位符，彻底解决 TUI 滚动性能问题

### 错误分析
当前实现中，`on_row_highlighted` 事件处理器调用 `markdown_widget.update(placeholder)`。尽管 `placeholder` 字符串很短，但 `Markdown` 组件的 `update` 方法依然会触发其内部的 Markdown 解析器和 Rich 渲染管线。在快速滚动（即高频触发 `RowHighlighted` 事件）时，这个固有的开销会累积，阻塞 `textual` 的事件循环，导致 UI 卡顿。

### 用户需求
实现一个真正轻量级的占位符显示机制，在快速滚动时不触发任何昂贵的 Markdown 渲染，从而保证 UI 的绝对流畅。

### 评论
这是一个非常深入且正确的优化方向。通过将“廉价的文本更新”和“昂贵的 Markdown 渲染”分离到两个专门的组件 (`Static` 和 `Markdown`) 中，我们遵循了高性能 UI 设计的最佳实践。这不仅能解决当前的卡顿问题，也为未来可能更复杂的视图渲染提供了健壮的架构基础。

### 目标
1.  在 `tui.py` 的 `compose` 方法中，在 `Markdown` 组件旁边添加一个 `Static` 组件，专门用作占位符。
2.  修改 `tui.css`，确保这两个组件在布局上重叠，并且 `Static` 组件默认隐藏。
3.  重构 `on_row_highlighted` 方法：
    *   在滚动时，隐藏 `Markdown` 组件，显示 `Static` 组件。
    *   **只更新 `Static` 组件的内容**，这是一个极低开销的操作。
4.  重构 `_debounced_update_content_view` 方法：
    *   在后台更新（不可见的）`Markdown` 组件的内容。
    *   更新完成后，隐藏 `Static` 组件，并重新显示 `Markdown` 组件。

### 基本原理
我们利用 `Static` widget 更新文本内容的极高性能（它只做简单的文本替换，几乎不消耗 CPU），来处理高频的滚动事件。而将 `Markdown` widget 的昂贵渲染操作推迟到防抖之后，并且在其不可见时进行。当渲染完成后，我们再通过一次简单的 CSS `display` 属性切换，原子性地将最终渲染好的内容呈现给用户，从而实现流畅的“即时预览 -> 延迟加载”体验。

### 标签
#intent/refine #flow/ready #priority/high
#comp/cli #concept/ui #scope/ux
#ai/brainstorm
#task/domain/ui #task/object/tui-performance #task/action/improvement #task/state/continue

---

### Script

#### Acts 1: 更新 `tui.py` 以引入并管理 `Static` 占位符组件

我们将修改 `compose` 方法添加新组件，并重构事件处理函数来管理两个组件的可见性。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                yield Markdown("", id="content-body")
        yield Footer()
~~~~~
~~~~~python
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="history-table", cursor_type="row", zebra_stripes=False)
            with Vertical(id="content-view"):
                yield Static("Node Content", id="content-header")
                # Add a lightweight placeholder that we can update quickly
                yield Static("", id="content-placeholder")
                # The expensive Markdown widget
                yield Markdown("", id="content-body")
        yield Footer()
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handles cursor movement with debouncing to prevent lag."""
        # Stop any pending content update
        if self.update_timer:
            self.update_timer.stop()

        # Update selection immediately for internal state
        selected_node = None
        row_key = event.row_key.value
        if row_key:
            selected_node = self.view_model.select_node_by_key(row_key)

        # If view is visible, show a meaningful placeholder and schedule the real update
        if self.is_split_mode:
            markdown_widget = self.query_one("#content-body", Markdown)
            if selected_node and selected_node.summary:
                placeholder = f"### {selected_node.summary}\n\n---\n*Loading full content...*"
            else:
                placeholder = "*Loading...*"
            markdown_widget.update(placeholder)
            self.update_timer = self.set_timer(self.debounce_delay_seconds, self._debounced_update_content_view)
~~~~~
~~~~~python
    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handles cursor movement with debouncing to prevent lag."""
        if self.update_timer:
            self.update_timer.stop()

        selected_node = None
        row_key = event.row_key.value
        if row_key:
            selected_node = self.view_model.select_node_by_key(row_key)

        if self.is_split_mode:
            placeholder_widget = self.query_one("#content-placeholder", Static)
            markdown_widget = self.query_one("#content-body", Markdown)

            # Instantly update the cheap placeholder and make it visible
            if selected_node and selected_node.summary:
                placeholder_text = f"### {selected_node.summary}\n\n---\n*Loading full content...*"
            else:
                placeholder_text = "*Loading...*"
            placeholder_widget.update(placeholder_text)
            
            placeholder_widget.display = True
            markdown_widget.display = False

            # Schedule the expensive update
            self.update_timer = self.set_timer(self.debounce_delay_seconds, self._debounced_update_content_view)
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _debounced_update_content_view(self) -> None:
        """The expensive update logic, called only after the user stops scrolling."""
        node = self.view_model.get_selected_node()
        if not node:
            return
        
        header = self.query_one("#content-header", Static)
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")

        content = self.view_model.get_content_bundle(node)
        
        markdown_widget = self.query_one("#content-body", Markdown)
        markdown_widget.update(content)
~~~~~
~~~~~python
    def _debounced_update_content_view(self) -> None:
        """The expensive update logic, called only after the user stops scrolling."""
        node = self.view_model.get_selected_node()
        if not node:
            return
        
        placeholder_widget = self.query_one("#content-placeholder", Static)
        markdown_widget = self.query_one("#content-body", Markdown)
        header = self.query_one("#content-header", Static)

        # Update header
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")

        # Update the expensive markdown widget while it's hidden
        content = self.view_model.get_content_bundle(node)
        markdown_widget.update(content)

        # Swap visibility
        placeholder_widget.display = False
        markdown_widget.display = True
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def action_toggle_view(self) -> None:
        self.is_split_mode = not self.is_split_mode
        container = self.query_one("#main-container")
        container.set_class(self.is_split_mode, "split-mode")
        
        # On view toggle, immediately update content if a row is highlighted
        if self.is_split_mode and self.view_model.get_selected_node():
            self._debounced_update_content_view()
~~~~~
~~~~~python
    def action_toggle_view(self) -> None:
        self.is_split_mode = not self.is_split_mode
        container = self.query_one("#main-container")
        container.set_class(self.is_split_mode, "split-mode")
        
        # Immediately update content if view is opened
        if self.is_split_mode and self.view_model.get_selected_node():
            self._debounced_update_content_view()
        # Ensure placeholder is hidden when view is closed
        elif not self.is_split_mode:
            self.query_one("#content-placeholder", Static).display = False
            self.query_one("#content-body", Markdown).display = True
~~~~~

#### Acts 2: 更新 CSS 以支持双组件布局

我们需要修改 `packages/quipu-cli/src/quipu/cli/tui.css` 来定义占位符组件的样式，并确保它和 Markdown 组件正确地交替显示。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.css
~~~~~
~~~~~css
#content-body {
    height: 1fr;
    padding: 1;
    overflow-y: auto;
}
~~~~~
~~~~~css
#content-placeholder {
    height: 1fr;
    padding: 1;
    overflow-y: auto;
    display: none; /* Hidden by default */
}

#content-body {
    height: 1fr;
    padding: 1;
    overflow-y: auto;
    display: true; /* Visible by default */
}
~~~~~

### 下一步建议
最终的方案已经实现。请再次进行手动验证：
1.  重新安装 `quipu-cli`。
2.  运行 `quipu ui`。
3.  **最终性能测试**: 快速滚动列表。现在它应该是**绝对流畅**的，因为高频更新的只是一个 `Static` 组件。右侧应正确显示摘要占位符。
4.  **最终加载测试**: 停止滚动后，占位符应被无缝替换为完整、高亮的 Markdown 内容。
5.  **视图切换测试**: 反复按 `v`，确认视图切换干净、无残留。

如果测试通过，这个性能优化的宏观任务就可以宣告完成了。
