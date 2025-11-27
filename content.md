好的，我将开始执行 **任务 5: 实现分页加载与渲染机制**。

此任务的目标是重构 `QuipuUiApp`，使其通过 `GraphViewModel` 按需加载数据，而不是在启动时加载所有内容。这将涉及修改数据加载入口 (`on_mount`)、实现分页逻辑 (`_load_page`)，并更新所有依赖旧数据结构的方法。

我将分步应用 `patch_file` 指令来完成此项改造。

### refactor: 实现 TUI 分页加载与渲染机制

#### 用户需求
根据 UI 性能优化方案，实现 `QuipuUiApp` 的分页加载机制。UI 启动时应只加载第一页数据，并通过新的方法按需加载其他页面，以解决性能瓶颈。

#### 评论
这是提升 UI 响应速度和降低内存占用的核心步骤。通过将重量级的数据加载操作从启动时 (`on_mount`) 转移到按需加载 (`_load_page`)，即使用户历史记录非常庞大，UI 也能实现秒级启动。

#### 目标
1.  将 `on_mount` 改造为异步初始化入口，加载第一页数据。
2.  创建新的 `_load_page` 方法，负责从 ViewModel 获取数据并更新 `DataTable`。
3.  更新 `_populate_table`、`_refresh_table`、`_focus_current_node` 和 `action_dump_content` 等方法，使其与新的分页数据流兼容。
4.  确保 `on_row_highlighted` 等事件在分页模式下依然能正确工作。

#### 基本原理
此重构将 UI 从“状态持有者”转变为“状态渲染器”。`on_mount` 启动数据加载流程，`_load_page` 成为核心的数据刷新入口。所有依赖全量节点列表的方法都被修改为依赖 ViewModel 或当前页的节点子集，从而实现低内存、高响应的设计。

#### 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #concept/ui #scope/core
#ai/instruct
#task/domain/ui #task/object/tui-performance #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 实现核心分页加载逻辑

我将首先替换 `on_mount` 方法，使其调用 ViewModel 进行初始化并加载第一页数据。同时，我将插入新的 `_load_page` 方法，这是分页机制的核心。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def on_mount(self) -> None:
        self._refresh_table()
~~~~~
~~~~~python
    def on_mount(self) -> None:
        """Initializes the view model and loads the first page of data."""
        self.view_model.initialize()
        self._load_page(1)

    def _load_page(self, page_number: int) -> None:
        """Loads and displays a specific page of nodes."""
        nodes = self.view_model.load_page(page_number)
        if not nodes and page_number > 1:
            self.bell()  # Give feedback on boundary
            return

        # Build a page-local index for mapping row keys to nodes, used by on_row_highlighted
        self.node_by_filename = {str(node.filename): node for node in nodes}

        table = self.query_one(DataTable)
        table.clear()
        self._populate_table(table, nodes)

        footer = self.query_one(Footer)
        footer.message = f"Page {self.view_model.current_page} / {self.view_model.total_pages}"

        self._focus_current_node(table)
~~~~~

#### Acts 2: 更新数据填充与刷新逻辑

现在，`_populate_table` 需要接收节点列表作为参数，并使用 ViewModel 进行可达性检查。同时，`_refresh_table` 逻辑也需要更新，以刷新当前页的数据，而不是整个列表。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _refresh_table(self):
        table = self.query_one(DataTable)
        table.clear(columns=True)

        # 始终显示详细信息列，即使在分栏模式下
        cols = ["Time", "Graph", "Node Info"]

        table.add_columns(*cols)
        self._populate_table(table)

        # 初始加载时定位到当前 HEAD
        if table.cursor_row == 0 and self.current_hash and not self.current_selected_node:
            self._focus_current_node(table)

    def _populate_table(self, table: DataTable):
        nodes_to_render = [
            node for node in self.sorted_nodes if self.show_unreachable or node.output_tree in self.reachable_hashes
        ]
        tracks: List[Optional[str]] = []
        for node in nodes_to_render:
            is_reachable = node.output_tree in self.reachable_hashes
~~~~~
~~~~~python
    def _refresh_table(self):
        table = self.query_one(DataTable)
        # Get the nodes for the current page from our page-local index
        current_page_nodes = list(getattr(self, "node_by_filename", {}).values())

        table.clear(columns=True)
        cols = ["Time", "Graph", "Node Info"]
        table.add_columns(*cols)

        # Repopulate using the nodes for the current page
        if current_page_nodes:
            # Sort them again by timestamp just in case the dict order is not guaranteed
            sorted_nodes = sorted(current_page_nodes, key=lambda n: n.timestamp, reverse=True)
            self._populate_table(table, sorted_nodes)

        self._focus_current_node(table)

    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = [
            node for node in nodes if self.show_unreachable or self.view_model.is_reachable(node.output_tree)
        ]
        tracks: List[Optional[str]] = []
        for node in nodes_to_render:
            is_reachable = self.view_model.is_reachable(node.output_tree)
~~~~~

#### Acts 3: 适配依赖旧数据结构的方法

最后，我将修复 `_focus_current_node` 和 `action_dump_content`，使它们能够在新架构下工作。

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
            content = self.content_loader(self.current_selected_node)
            self.exit(result=("dump", content))
~~~~~
~~~~~python
    def action_dump_content(self) -> None:
        """退出 UI 并将当前选中节点的内容输出到 stdout"""
        if self.current_selected_node:
            content = self.view_model.get_content_bundle(self.current_selected_node)
            self.exit(result=("dump", content))
~~~~~

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _focus_current_node(self, table: DataTable):
        if not self.current_hash:
            return
        target_nodes = self.nodes_by_output_hash.get(self.current_hash, [])
        if not target_nodes:
            return
        latest_node = target_nodes[-1]
        try:
            row_index = table.get_row_index(str(latest_node.filename))
            table.cursor_coordinate = Coordinate(row=row_index, column=0)
            # 初始化选中状态
            self.current_selected_node = latest_node
        except Exception:
            pass
~~~~~
~~~~~python
    def _focus_current_node(self, table: DataTable):
        current_hash = self.view_model.current_hash
        if not current_hash:
            return

        # Search for the node with the current hash on the currently displayed page
        target_node = next(
            (node for node in self.node_by_filename.values() if node.output_tree == current_hash), None
        )

        if not target_node:
            return

        try:
            row_key = str(target_node.filename)
            if table.is_valid_row_key(row_key):
                row_index = table.get_row_index(row_key)
                table.cursor_coordinate = Coordinate(row=row_index, column=0)
                # Only set initially, don't override user selection during a refresh
                if not self.current_selected_node:
                    self.current_selected_node = target_node
        except Exception:
            # Silently fail if something goes wrong, it's not critical
            pass
~~~~~

### 下一步建议
分页加载和渲染机制的核心改造已经完成。UI 现在能够通过 ViewModel 按需加载数据。

下一步是 **任务 6: 实现分页快捷键绑定和动作**，为用户提供在页面间导航的能力。
