# fix: 修复 TUI 中 j/k 导航键无效的问题

## 用户需求
用户在确认了 `j/k` 导航键不生效的原因后，要求生成一个可执行的计划来修复此问题。

## 评论
此修复方案解决了 Textual 框架中的事件处理优先级问题。之前 `j/k` 按键事件被 `DataTable` 小部件作为字符输入消费掉，未能触发 App 级别的绑定。通过创建自定义动作，我们可以建立一个更高优先级的处理链路，确保按键能够正确地控制光标移动。

## 目标
*   在 `QuipuUiApp` 类中添加 `action_move_up` 和 `action_move_down` 两个自定义动作方法。
*   在这两个方法内部，显式调用 `DataTable` 小部件的光标移动方法。
*   更新 `BINDINGS` 列表，将 `k` 键和 `j` 键分别绑定到新的 `move_up` 和 `move_down` 动作。

## 基本原理
通过在 App 类中定义 `action_` 前缀的方法，我们创建了可以被 `BINDINGS` 列表引用的新动作。当按下 `j` 或 `k` 时，Textual 会优先调用这些在 App 层面定义的、更具体的动作 (`action_move_up`/`action_move_down`)，而不是让 `DataTable` 执行其默认的、针对字符输入的“跳转”行为。在我们的自定义动作内部，我们再直接命令 `DataTable` 执行光标移动，从而绕过了默认的事件处理逻辑，实现了预期的导航功能。

## 标签
 #fix #tui #ux

---

## Script

### Act 1: 添加自定义动作并更新 TUI 按键绑定

在 `quipu.cli.tui.py` 文件中，为 `QuipuUiApp` 添加 `action_move_up` 和 `action_move_down` 方法，并修改 `BINDINGS` 列表以使用这些新动作。

~~~~~act
replace
~~~~~

~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~

~~~~~python
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("h", "toggle_hidden", "显隐非关联分支"),
        Binding("up", "cursor_up", "上移", show=False),
        Binding("down", "cursor_down", "下移", show=False),
    ]

    def __init__(self, nodes: List[QuipuNode], current_hash: Optional[str] = None):
~~~~~

~~~~~python
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("c", "checkout_node", "检出节点"),
        Binding("enter", "checkout_node", "检出节点"),
        Binding("h", "toggle_hidden", "显隐非关联分支"),
        Binding("up", "cursor_up", "上移", show=False),
        Binding("down", "cursor_down", "下移", show=False),
        Binding("k", "move_up", "上移", show=False),
        Binding("j", "move_down", "下移", show=False),
    ]

    def action_move_up(self) -> None:
        """在 DataTable 中上移光标。"""
        self.query_one(DataTable).action_cursor_up()

    def action_move_down(self) -> None:
        """在 DataTable 中下移光标。"""
        self.query_one(DataTable).action_cursor_down()

    def __init__(self, nodes: List[QuipuNode], current_hash: Optional[str] = None):
~~~~~