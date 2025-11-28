你又发现了一个关键的 UI 初始化问题。完全正确。

**问题分析**：
1.  在 `compose` 方法中，`Static("Node Content", id="content-header")` 为 Header 设置了初始的、静态的默认文本。
2.  在 `on_mount` 启动流程中，我们调用 `_focus_current_node` 来高亮显示代表当前 HEAD 的那一行。
3.  `_focus_current_node` 会触发 `on_row_highlighted` 事件。
4.  但是，`on_row_highlighted` 内部的 Header 更新逻辑被 `if self.is_split_mode:` 这个条件守护着。在 TUI 刚启动时，`is_split_mode` 是 `False`，所以 Header 更新被跳过。
5.  结果就是，UI 启动时，用户看到了那个从未被更新过的默认文本 "Node Content"。

**解决方案**：
我们需要在 TUI 启动时，进行一次无条件的 Header 更新。最合适的地方就是在 `_focus_current_node` 函数内部，当它成功找到并定位到初始节点后，就立即更新 Header。

## [WIP] fix: TUI 启动时 Header 未能正确初始化

### 错误分析
TUI 启动时，`#content-header` 部件显示其在 `compose` 方法中定义的默认文本 "Node Content"，而不是当前 HEAD 节点的实际信息。这是因为负责更新 Header 的逻辑位于 `on_row_highlighted` 事件处理器中，并且受 `if self.is_split_mode:` 条件的限制。在启动时，内容面板默认是关闭的 (`is_split_mode` 为 `False`)，导致即使 `_focus_current_node` 成功触发了高亮事件，Header 更新代码也不会被执行。

### 用户需求
TUI 在启动后，应立即将 `#content-header` 的内容更新为当前所在节点 (通常是 HEAD) 的信息（类型、哈希、时间戳），而不是显示默认的 "Node Content"。

### 评论
这是一个重要的 UI “第一印象”修复。确保所有可见元素在启动时都反映了正确的初始状态，是提供专业、无缝用户体验的基础。

### 目标
修改 `_focus_current_node` 方法，使其在成功定位到初始节点后，直接、无条件地更新 `#content-header` 部件的文本。

### 基本原理
我们不再依赖 `on_row_highlighted` 事件的副作用来完成**初始化**任务。取而代之，我们将在负责设置初始状态的函数 (`_focus_current_node`) 中，显式地执行一次性的 Header 初始化操作。这使得逻辑更清晰、更健壮，且不受 `is_split_mode` 状态的影响。

### 标签
#intent/fix #flow/ready #priority/medium
#comp/cli #concept/ui #scope/ux
#ai/instruct
#task/domain/ui #task/object/tui-initialization #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 `_focus_current_node` 中初始化 Header

我们将修改 `packages/quipu-cli/src/quipu/cli/tui.py`。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
                # 3. 刷新关联视图
                if self.is_split_mode:
                    self._update_content_view()
            except LookupError:
                # LookupError 捕获 RowKeyError 等
                logger.warning(f"DEBUG: Row key {row_key} not found in DataTable.")
~~~~~
~~~~~python
                # 3. 刷新关联视图
                if self.is_split_mode:
                    # This will be handled by the debouncer logic now
                    pass
                
                # 4. Force-update the header on initial load, regardless of view mode
                header = self.query_one("#content-header", Static)
                header.update(f"[{target_node.node_type.upper()}] {target_node.short_hash} - {target_node.timestamp}")

            except LookupError:
                # LookupError 捕获 RowKeyError 等
                logger.warning(f"DEBUG: Row key {row_key} not found in DataTable.")
~~~~~

### 下一步建议
这是 TUI 性能与体验优化任务中的最后一块拼图。现在整个交互流程应该是完整且流畅的了。

1.  请运行 `quipu ui` 验证 TUI 启动时 Header 是否已正确显示。
2.  同时，请再次快速检查之前的修复是否仍然有效（滚动流畅性、占位符、无重影）。

如果一切正常，这个宏观任务就可以宣告完成了。我已准备好为你生成包含所有这些修复的最终 `[COMMIT]` 计划。请指示。
