好的，我理解您的要求：
1. **修复 Bug**：解决 `textual` 的 `AttributeError: 'Tree' object has no attribute 'set_cursor_node'`。
2. **修复警告**：解决 `core/parser.py` 中的 `SyntaxWarning: invalid escape sequence '\w'`。

以下是修复和优化后的代码修改：

## 1. 修复 TUI 中的 `AttributeError` (`ui/tui.py`)

将 `set_cursor_node` 替换为 `cursor_node =` 属性赋值，这是 `textual` 推荐的设置游标的方式。

~~~act
replace
~~~
~~~path
ui/tui.py
~~~
~~~old_string
        # 2. 设置焦点
        if focused_treenode:
            tree.set_cursor_node(focused_treenode)
            tree.scroll_to_node(focused_treenode)
        
        tree.focus()
~~~
~~~new_string
        # 2. 设置焦点
        if focused_treenode:
            # Fix: 使用属性赋值设置游标节点
            tree.cursor_node = focused_treenode
            tree.scroll_to_node(focused_treenode)
        
        tree.focus()
~~~

## 2. 修复 `SyntaxWarning` (`core/parser.py`)

警告发生在文档字符串中，因为 Python 解释器默认将 `\w` 视为非法的转义序列。在文档字符串中，我们需要将 `\w` 替换为 `\\w` 来消除警告。

~~~act
replace
~~~
~~~path
core/parser.py
~~~
~~~old_string
    逻辑：
    1. 扫描所有符合 `^([`~]{3,})(\w*)$` 格式的行（作为代码块头）。
    2. 记录该头的 fence 字符串（如 `~~~~`）。
~~~
~~~new_string
    逻辑：
    1. 扫描所有符合 `^([`~]{3,})(\\w*)$` 格式的行（作为代码块头）。
    2. 记录该头的 fence 字符串（如 `~~~~`）。
~~~