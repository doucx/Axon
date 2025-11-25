您遇到的问题是因为 `textual` 框架在不同的版本或环境中，设置 `Tree` 的游标节点（Cursor Node）的方式有所不同。

根据您提供的 traceback：`AttributeError: property 'cursor_node' of 'Tree' object has no setter`，这意味着在您当前使用的 `textual` 版本中，`cursor_node` 是一个只读属性，或者您需要使用 `textual.widgets.tree.Tree.set_current()` 方法来设置当前选中的节点。

Textual 的 `Tree` 组件的 API 确实在一些版本中将 `set_cursor_node` 废弃，但正确的替代方法是设置 `tree.show_line` (内部方法，不推荐) 或通过 `tree.select_node(node)` 或 `tree.cursor = tree.get_node_id(node)`。然而，最稳定的方法是直接使用 `select_node` 或操作其内部 ID。

我将修改 `ui/tui.py` 中的 `on_mount` 逻辑，使用更可靠的 `select_node` 或 ID 方式来定位节点。由于 `textual` 的 Tree API 经常变动，我们将使用 `tree.select_node` 或 `tree.cursor` 的变通方案。

**方案：使用 `tree.select_node(node_id)` 或 `tree.cursor` 属性**

我们不能直接使用 `tree.cursor_node = focused_treenode`，因为这会触发 `AttributeError`。我们应该使用 `tree.cursor` 属性（期望一个整数 ID）。

### 1. 修复 TUI 焦点定位 (`ui/tui.py`)

为了兼容性，我们将使用节点 ID 来设置游标。

~~~act
replace
~~~
~~~path
ui/tui.py
~~~
~~~old_string
        # 2. 设置焦点
        if focused_treenode:
            # Fix: 使用属性赋值设置游标节点
            tree.cursor_node = focused_treenode
            tree.scroll_to_node(focused_treenode)
        
        tree.focus()
~~~
~~~new_string
        # 2. 设置焦点
        if focused_treenode:
            # 兼容性修复：使用 cursor 属性设置游标位置 (期望 ID 或索引)
            # 在某些 Textual 版本中，cursor=node.id 属性赋值是设置游标的正确方式。
            tree.cursor = focused_treenode.id
            tree.scroll_to_node(focused_treenode)
        
        tree.focus()
~~~

请应用此修改并重新运行。如果 `Tree.cursor` 属性在您的版本中仍不支持直接赋值 `node.id`，我将需要进一步调整以使用更底层的节点索引。