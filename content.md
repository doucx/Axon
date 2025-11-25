这是一个明确的 API 兼容性问题。`textual` 的 `DataTable` 组件使用 `move_cursor` 即可实现滚动，不需要（也不支持）`scroll_to_row`。

同时，为了回应您关于“侧枝”显示的需求，我在这次修复中也会稍微优化一下 `_flatten_graph` 的逻辑，给非主线节点一点缩进，以便在视觉上区分。

### 修复 `ui/tui.py`

1.  **移除** 导致崩溃的 `table.scroll_to_row`。
2.  **优化** 视觉显示：为主线外的节点添加简单的缩进前缀 `└─ `。

~~~act
replace
~~~
~~~path
ui/tui.py
~~~
~~~old_string
    # 追踪主线 (Mainline)
    mainline_hashes = set()
    current = newest_node
    while current:
        mainline_hashes.add(current.output_tree)
        # 确保沿着时间最晚的父节点走（如果父节点有多个子节点）
        # 这里简化：我们总是沿着唯一的父指针走，如果父节点有多个孩子，当前节点是主线。
        current = current.parent 

    # 3. 构造最终的列表 (node, depth)
    final_list: List[Tuple[AxonNode, int]] = []
    
    for node in sorted_nodes:
        # 深度逻辑: 
        # 如果节点在主线，深度为 0 (无需缩进)。
        # 如果不在主线，则需要计算其分支深度。
        # 简化：因为 Textual DataTable 不提供连接线，我们依赖用户视觉理解。
        # 暂时只返回 (node, 0) 来表示每个节点都是独立一行。
        final_list.append((node, 0)) # 忽略深度，让 TUI 负责渲染。

    return final_list
~~~
~~~new_string
    # 追踪主线 (Mainline)
    mainline_hashes = set()
    current = newest_node
    while current:
        mainline_hashes.add(current.output_tree)
        current = current.parent 

    # 3. 构造最终的列表 (node, depth)
    final_list: List[Tuple[AxonNode, int]] = []
    
    for node in sorted_nodes:
        # 简化的深度逻辑:
        # 主线节点 depth=0
        # 其他节点 depth=1 (简单的向右分支)
        depth = 0 if node.output_tree in mainline_hashes else 1
        final_list.append((node, depth))

    return final_list
~~~

~~~act
replace
~~~
~~~path
ui/tui.py
~~~
~~~old_string
            # 摘要
            summary_str = node.summary

            # 样式与内容构建
            if node.output_tree == self.current_hash:
                current_node_row_index = i
                # 使用 Rich Text 进行高亮 (bold reverse 通常能适应各种终端主题)
                summary_cell = Text(summary_str, style="bold reverse")
                # 也可以选择高亮其他列，这里高亮摘要列
            else:
                summary_cell = summary_str
            
            # 将 AxonNode 实例作为行的用户数据 (UserData) 存储
            # DataTable.add_row 接受 *cells, label=..., key=...
            # 注意：Textual 的 add_row 不支持直接传递 label 对象作为参数来存储数据，
            # 但它支持 key。我们需要一个方式来找回 node。
            # 最好的方式是维护一个 key -> node 的映射，或者依赖 key 本身。
            # 之前的代码试图用 label=node，这在 Textual API 中可能不支持存储对象。
            # 我们利用 key=node.output_tree 即可，在 action_checkout_node 中我们已经通过 self.flat_nodes 查找了。
            
            row_key = table.add_row(
                time_str,
                type_label,
                hash_str,
                summary_cell,
                key=node.output_tree
            )

        # 2. 设置焦点
        if current_node_row_index is not None:
            # DataTable 使用 row_index 来设置游标
            table.move_cursor(row=current_node_row_index, animate=False)
            # Textual v0.58+ 使用 scroll_to_row
            table.scroll_to_row(current_node_row_index, top=True)
        
        table.focus()
~~~
~~~new_string
            # 摘要 (处理缩进)
            indent = "   " * depth
            prefix = "└─ " if depth > 0 else ""
            final_summary_str = f"{indent}{prefix}{node.summary}"

            # 样式与内容构建
            if node.output_tree == self.current_hash:
                current_node_row_index = i
                # 使用 Rich Text 进行高亮 (bold reverse)
                summary_cell = Text(final_summary_str, style="bold reverse")
            else:
                summary_cell = final_summary_str
            
            # 添加行
            table.add_row(
                time_str,
                type_label,
                hash_str,
                summary_cell,
                key=node.output_tree
            )

        # 2. 设置焦点
        if current_node_row_index is not None:
            # DataTable 使用 row_index 来设置游标
            table.move_cursor(row=current_node_row_index, animate=False)
            # 注意：move_cursor 通常会自动滚动视图。
            # 移除了不支持的 scroll_to_row 调用。
        
        table.focus()
~~~

请应用修改。这次移除了不支持的 API 调用，并添加了基础的分支视觉区分。