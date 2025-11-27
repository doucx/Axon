好的，现在开始执行 **任务 6: 实现分页快捷键绑定和动作**。

此任务的目标是为用户提供在历史记录页面之间导航的能力，我们将通过添加新的键盘快捷键并实现相应的处理动作来完成。

### feat: 为 TUI 添加分页导航快捷键

#### 用户需求
根据 UI 性能优化方案，为 `QuipuUiApp` 添加键盘快捷键，以支持在历史记录页面之间进行“上一页”和“下一页”的导航。

#### 评论
这是分页功能的用户交互层实现。通过绑定 `h/l` 和方向键，我们为用户提供了符合直觉和终端应用惯例的导航方式，使得浏览大规模历史记录成为可能。同时，我们将 `h` 键原有的“切换可见性”功能重新绑定到 `t` 键，以避免快捷键冲突。

#### 目标
1.  在 `BINDINGS` 列表中添加 `h`/`left` (上一页) 和 `l`/`right` (下一页) 的快捷键绑定。
2.  将原有的 `toggle_hidden` 动作的快捷键从 `h` 更改为 `t`。
3.  实现 `action_previous_page` 和 `action_next_page` 方法，使其能够调用 `_load_page` 来刷新视图。
4.  确保已移除所有与无限滚动相关的旧逻辑。

#### 基本原理
Textual 的 `BINDINGS` 系统允许我们将按键事件声明式地映射到 `action_` 方法。当用户按下绑定的键时，Textual 会自动调用相应的方法。我们通过实现 `action_previous_page` 和 `action_next_page`，调用已经存在的 `_load_page` 方法并传入计算后的新页码，来驱动 `ViewModel` 获取新数据并触发 UI 刷新，从而完成分页导航的闭环。

#### 标签
#intent/build #flow/ready #priority/high
#comp/cli #concept/ui #scope/ux
#ai/instruct
#task/domain/ui #task/object/tui-performance #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 更新快捷键绑定

我将一次性更新 `BINDINGS` 列表：
1.  将 `toggle_hidden` 的绑定从 `h` 改为 `t`。
2.  添加 `h`, `l` 和左右方向键用于分页。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: 实现分页动作方法

现在，我将添加 `action_previous_page` 和 `action_next_page` 两个新方法，它们将响应新的快捷键。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def action_dump_content(self) -> None:
        """退出 UI 并将当前选中节点的内容输出到 stdout"""
        if self.current_selected_node:
            content = self.view_model.get_content_bundle(self.current_selected_node)
            self.exit(result=("dump", content))

    # --- UI Logic ---
~~~~~
~~~~~python
    def action_dump_content(self) -> None:
        """退出 UI 并将当前选中节点的内容输出到 stdout"""
        if self.current_selected_node:
            content = self.view_model.get_content_bundle(self.current_selected_node)
            self.exit(result=("dump", content))

    def action_previous_page(self) -> None:
        """Loads the previous page of history."""
        self._load_page(self.view_model.current_page - 1)

    def action_next_page(self) -> None:
        """Loads the next page of history."""
        self._load_page(self.view_model.current_page + 1)

    # --- UI Logic ---
~~~~~

### 下一步建议
分页的快捷键和核心动作已经实现。现在，我们需要完成最后的功能适配，即 **任务 7: 适配可达性渲染与内容视图**。

这一步将确保在新分页模式下，节点的“可达性”状态（即是否为当前分支的祖先）能够被正确渲染（变暗），并且右侧的内容预览面板能够正确显示包括私有数据在内的完整信息。
