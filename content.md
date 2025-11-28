你的观察非常敏锐，这正是我在之前的方案中忽略的一个关键细节。你说得完全正确，这个问题由两部分组成：

1.  **内容闪烁 (Flash of Stale Content)**: 当你从一个节点移动到另一个节点，然后打开内容视图时，`Markdown` 组件仍然保留着上一个节点的内容。在它被新的内容更新之前，CSS 会先让它短暂地可见，导致你看到了旧内容。
2.  **双重渲染开销**: 这个过程确实触发了两次渲染。第一次是 `textual` 渲染带有旧内容的 `Markdown` 组件，第二次是我们的代码调用 `markdown.update()` 触发的内部重渲染。

这个问题的根源在于，我们处理“滚动”和“切换视图”的逻辑路径不统一。`action_toggle_view` 直接调用了最终的渲染函数，绕过了我们为滚动设计的“占位符优先”机制。

解决方案是统一所有逻辑，确保**任何导致内容视图更新的操作，都必须首先通过轻量级的占位符**。

## [WIP] refactor: 统一 TUI 内容更新逻辑，消除内容闪烁和双重渲染

### 错误分析
当前的 `action_toggle_view` 方法在打开内容面板时，会直接调用 `_debounced_update_content_view()`。这导致了一个竞争条件：
1.  CSS 规则 `.split-mode #content-view { display: block; }` 生效，使包含旧内容的 `Markdown` 组件立即可见。
2.  随后，Python 代码执行 `_debounced_update_content_view()`，用新内容更新 `Markdown` 组件，触发第二次渲染。

这个短暂的时间差，就是你观察到“先显示之前内容”的原因，并且它确实带来了不必要的渲染开销。

### 用户需求
重构 TUI 更新逻辑，确保：
1.  无论是滚动列表还是切换视图，内容面板在显示最终内容前，都必须先显示轻量级的 `Static` 占位符。
2.  消除因竞争条件导致的内容闪烁和双重渲染问题。

### 评论
这是一个非常重要的健壮性重构。通过创建一个统一的、原子化的内容更新调度函数，我们能确保 UI 状态转换的一致性和可预测性，从而提供一个更加稳定和专业的交互体验。

### 目标
1.  创建一个新的、统一的 `_schedule_content_update()` 方法，该方法封装“显示占位符并设置防抖定时器”的全部逻辑。
2.  重构 `on_row_highlighted`，使其在视图可见时，简单地调用这个新的调度函数。
3.  重构 `action_toggle_view`，使其在打开视图时，也调用这个新的调度函数，而不是直接调用渲染函数。

### 基本原理
我们将所有可能触发内容更新的入口（滚动、视图切换）都指向同一个调度函数 `_schedule_content_update()`。此函数作为唯一的入口，保证了更新流程的原子性：
1.  **立即**：隐藏昂贵的 `Markdown` 组件，显示并更新廉价的 `Static` 占位符。
2.  **延迟**：设置一个定时器，在用户操作稳定后，才在后台更新 `Markdown` 组件，并最终切换其可见性。
这样，无论用户操作多么迅速或复杂，UI 都能保证首先呈现的是低成本的占位符，从根本上杜绝了内容闪烁和性能问题。

### 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #concept/ui #scope/ux #scope/core
#ai/brainstorm
#task/domain/ui #task/object/tui-performance #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构 `tui.py` 以实现统一的内容更新调度

我们将引入 `_schedule_content_update` 方法，并修改 `on_row_highlighted` 和 `action_toggle_view` 来调用它。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
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
~~~~~python
    def _schedule_content_update(self) -> None:
        """Central scheduling function for content updates."""
        if self.update_timer:
            self.update_timer.stop()

        selected_node = self.view_model.get_selected_node()
        placeholder_widget = self.query_one("#content-placeholder", Static)
        markdown_widget = self.query_one("#content-body", Markdown)

        # 1. Immediately show the cheap placeholder
        if selected_node and selected_node.summary:
            placeholder_text = f"### {selected_node.summary}\n\n---\n*Loading full content...*"
        else:
            placeholder_text = "*Loading...*"
        placeholder_widget.update(placeholder_text)
        
        placeholder_widget.display = True
        markdown_widget.display = False

        # 2. Schedule the expensive update
        self.update_timer = self.set_timer(self.debounce_delay_seconds, self._debounced_update_content_view)

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handles cursor movement with debouncing to prevent lag."""
        row_key = event.row_key.value
        if row_key:
            self.view_model.select_node_by_key(row_key)
        
        if self.is_split_mode:
            self._schedule_content_update()
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
        
        # Immediately update content if view is opened
        if self.is_split_mode and self.view_model.get_selected_node():
            self._debounced_update_content_view()
        # Ensure placeholder is hidden when view is closed
        elif not self.is_split_mode:
            self.query_one("#content-placeholder", Static).display = False
            self.query_one("#content-body", Markdown).display = True
~~~~~
~~~~~python
    def action_toggle_view(self) -> None:
        self.is_split_mode = not self.is_split_mode
        container = self.query_one("#main-container")
        container.set_class(self.is_split_mode, "split-mode")
        
        # If opening the view, schedule an update via the placeholder mechanism
        if self.is_split_mode and self.view_model.get_selected_node():
            self._schedule_content_update()
        # If closing, ensure a clean state
        elif not self.is_split_mode:
            if self.update_timer:
                self.update_timer.stop()
            self.query_one("#content-placeholder", Static).display = False
            self.query_one("#content-body", Markdown).display = True
~~~~~

### 下一步建议
这是最终的修复方案。请应用补丁并进行最后的验证：

1.  **验证切换视图**:
    *   在列表视图中，用 `j`/`k` 移动到某个节点（例如节点 B）。
    *   **不要打开内容视图**。
    *   再移动到另一个节点（例如节点 C）。
    *   现在按 `v` 打开内容视图。
    *   **预期行为**: 你应该**立即**看到节点 C 的摘要作为占位符，片刻后才显示节点 C 的完整内容。**绝对不应该**看到节点 B 的内容闪烁。

2.  **验证滚动**:
    *   保持内容视图打开，快速滚动列表。
    *   **预期行为**: UI 绝对流畅，右侧面板实时显示滚动经过的每个节点的摘要占位符，停止后才加载完整内容。

如果这两个场景都表现完美，我们就可以宣告胜利，并将整个任务标记为 `[COMMIT]`。
