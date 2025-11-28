你的观察非常细致。

**问题分析**：
目前的实现中，Header（顶部状态栏，显示 Hash 和时间）的更新逻辑被放在了 `_debounced_update_content_view` 函数里。这意味着它和繁重的 Markdown 渲染一样，只有在你**停止滚动**触发防抖后才会更新。
在滚动过程中，Header 会“卡”在开始滚动前的那个节点上，导致它显示的信息与下方的占位符（已经实时更新为新节点的 summary）不一致。

**解决方案**：
`Header` 实际上是一个 `Static` 组件，更新它的文本开销极低（和占位符一样）。我们完全没有理由对它进行防抖。
我们应该将 Header 的更新逻辑从防抖函数中提取出来，放回 `on_row_highlighted` 事件中，使其**实时跟随**光标移动。

这样，在快速滚动时：
1.  **Header**: 实时跳变，显示当前经过节点的 Hash/时间。
2.  **占位符**: 实时跳变，显示当前经过节点的 Summary。
3.  **Markdown**: 保持空白/隐藏，直到停止滚动才加载。

这将提供最连贯的视觉反馈。

## [WIP] fix: 让 TUI Header 信息实时跟随滚动更新

### 用户需求
在 TUI 快速滚动列表时，右侧顶部的 Header（显示节点类型、哈希和时间戳）应实时更新，而不是等待防抖延迟后才更新。

### 评论
这是一个低成本高收益的 UX 修复。将轻量级的元数据更新与重量级的内容渲染解耦，是提升 UI 响应感的关键策略。

### 目标
1.  修改 `on_row_highlighted`：在检测到行高亮时，立即更新 Header 的内容。
2.  修改 `_debounced_update_content_view`：移除其中重复的 Header 更新逻辑（或者保留作为冗余安全措施，但在高亮时必须已经更新）。为了代码清晰，建议移除或简化。

### 标签
#intent/fix #flow/ready #priority/medium
#comp/cli #concept/ui #scope/ux
#ai/instruct
#task/domain/ui #task/object/tui-header #task/action/synchronization #task/state/continue

---

### Script

#### Acts 1: 移动 Header 更新逻辑

我们将修改 `packages/quipu-cli/src/quipu/cli/tui.py`。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
        if self.is_split_mode:
            placeholder_widget = self.query_one("#content-placeholder", Static)
            markdown_widget = self.query_one("#content-body", Markdown)
            header = self.query_one("#content-header", Static)

            # Instantly update the cheap header
            if selected_node:
                header.update(f"[{selected_node.node_type.upper()}] {selected_node.short_hash} - {selected_node.timestamp}")

            # Instantly update the cheap placeholder and make it visible
            if selected_node and selected_node.summary:
                placeholder_text = f"### {selected_node.summary}\n\n---\n*Loading full content...*"
            else:
                placeholder_text = "*Loading...*"
            placeholder_widget.update(placeholder_text)
            
            placeholder_widget.display = True
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
        
        placeholder_widget = self.query_one("#content-placeholder", Static)
        markdown_widget = self.query_one("#content-body", Markdown)
        header = self.query_one("#content-header", Static)

        # Update header
        header.update(f"[{node.node_type.upper()}] {node.short_hash} - {node.timestamp}")

        # Update the expensive markdown widget while it's hidden
        content = self.view_model.get_content_bundle(node)
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
        
        # Header is already updated in on_row_highlighted

        # Update the expensive markdown widget while it's hidden
        content = self.view_model.get_content_bundle(node)
        markdown_widget.update(content)
~~~~~

### 下一步建议
现在 TUI 的交互逻辑应该非常完善了：
1.  **Header**: 实时跟手。
2.  **Placeholder**: 实时跟手，显示语义摘要。
3.  **Content**: 防抖加载，无旧内容残留。

请进行最后一次验证，如果没有问题，我强烈建议将这四次代码变更（防抖、Placeholder语义化、CSS修复、Header实时化、反Ghosting）打包成一个 `[COMMIT]` 提交，因为它们共同构成了一个完整的“TUI 性能与体验优化”功能集。

你需要我为你生成这个合并后的 Commit 计划吗？
