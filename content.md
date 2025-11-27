这是对回归问题的全面修复计划。我们将通过引入节点位置查询能力来实现精准的页面跳转，并清理渲染逻辑以解决视觉穿插问题。

## fix: 修复 UI 回归问题：定位偏移与渲染穿插

### 错误分析
1.  **渲染穿插 (Visual Artifacts)**: `TUI._populate_table` 中存在一段为了保证“主线连贯”而强制将 `HEAD` 加入绘图轨迹 (`tracks`) 的逻辑。在引入“后代显示”功能后，如果 `HEAD` 位于历史中间，这段逻辑会导致一条直线从顶部强行贯穿到 `HEAD`，不仅视觉上不正确（表现为“什么也没连着的线”），还会挤占其他分支的空间。
2.  **定位偏移 (Lost Focus)**: UI 启动时默认加载第 1 页。如果当前 `HEAD` 是一个较旧的节点（例如位于第 5 页），用户打开 UI 时会看到最新的历史，而找不到当前所在的位置，且光标无法聚焦。

### 用户需求
-   **精准定位**: 打开 `quipu ui` 时，应自动跳转到当前 `HEAD` 所在的页面，并高亮当前节点。
-   **纯净渲染**: 图谱连线应完全基于父子关系自然生成，消除人为强制添加的干扰线。

### 评论
这是一个典型的“技术债”清理。强制连线逻辑是早期为了解决“仅显示祖先”时主线断裂问题的临时方案，在全量图谱下已不再适用。

### 目标
1.  **存储层能力升级**: 在 `HistoryReader` 接口及其实现中增加 `get_node_position` 方法，用于查询节点的时间排名。
2.  **ViewModel 增强**: 利用排名信息计算 `HEAD` 所在的初始页码。
3.  **UI 逻辑修正**: 启动时加载计算出的页码，并移除强制连线代码。

### 基本原理
-   **位置查询**: 利用 SQLite 的 `COUNT(*)` (WHERE timestamp > target) 高效计算排名。Git 后端则通过内存列表索引实现。
-   **分页计算**: `page = (rank // page_size) + 1`。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/engine #comp/interfaces #scope/ux #ai/instruct #task/domain/ui #task/object/reachability #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 扩展接口定义 (Interfaces)

在 `HistoryReader` 中添加 `get_node_position` 抽象方法。

~~~~~act
patch_file
packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~
~~~~~python
    @abstractmethod
    def get_descendant_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """
        获取指定状态节点的所有后代节点的 output_tree 哈希集合。
        """
        pass
~~~~~
~~~~~python
    @abstractmethod
    def get_descendant_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """
        获取指定状态节点的所有后代节点的 output_tree 哈希集合。
        """
        pass

    @abstractmethod
    def get_node_position(self, output_tree_hash: str) -> int:
        """
        获取指定节点在按时间倒序排列的全局列表中的索引位置（从 0 开始）。
        如果节点不存在，返回 -1。
        """
        pass
~~~~~

#### Acts 2: Git 后端实现 (Engine - Git)

在 `GitObjectHistoryReader` 中实现该方法。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
    def get_node_count(self) -> int:
        """Git后端: 低效实现，加载所有节点后计数"""
        return len(self.load_all_nodes())
~~~~~
~~~~~python
    def get_node_count(self) -> int:
        """Git后端: 低效实现，加载所有节点后计数"""
        return len(self.load_all_nodes())

    def get_node_position(self, output_tree_hash: str) -> int:
        """Git后端: 低效实现，加载所有节点后查找索引"""
        all_nodes = self.load_all_nodes()
        # load_all_nodes 内部已经按时间倒序排序了
        # 但为了保险，还是在这里再次确认排序逻辑
        all_nodes.sort(key=lambda n: n.timestamp, reverse=True)

        for i, node in enumerate(all_nodes):
            if node.output_tree == output_tree_hash:
                return i
        return -1
~~~~~

#### Acts 3: SQLite 后端实现 (Engine - SQLite)

在 `SQLiteHistoryReader` 中使用 SQL 高效实现。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
    def get_node_count(self) -> int:
        """
        获取历史节点总数。
        """
        conn = self.db_manager._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM nodes")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"Failed to get node count: {e}")
            return 0
~~~~~
~~~~~python
    def get_node_count(self) -> int:
        """
        获取历史节点总数。
        """
        conn = self.db_manager._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM nodes")
            row = cursor.fetchone()
            return row[0] if row else 0
        except sqlite3.Error as e:
            logger.error(f"Failed to get node count: {e}")
            return 0

    def get_node_position(self, output_tree_hash: str) -> int:
        """
        计算节点在时间倒序列表中的位置 (Rank)。
        """
        conn = self.db_manager._get_conn()
        try:
            # 1. 获取目标节点的时间戳
            cursor = conn.execute("SELECT timestamp FROM nodes WHERE output_tree = ?", (output_tree_hash,))
            row = cursor.fetchone()
            if not row:
                return -1
            target_ts = row[0]

            # 2. 计算有多少个节点比它新（时间戳更大）
            cursor = conn.execute("SELECT COUNT(*) FROM nodes WHERE timestamp > ?", (target_ts,))
            count = cursor.fetchone()[0]
            return count
        except sqlite3.Error as e:
            logger.error(f"Failed to get node position: {e}")
            return -1
~~~~~

#### Acts 4: ViewModel 计算页码 (CLI - VM)

在 `GraphViewModel` 中添加 `calculate_initial_page`。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/view_model.py
~~~~~
~~~~~python
    def is_reachable(self, output_tree_hash: str) -> bool:
        """检查一个节点哈希是否在可达性集合中。"""
        if not self.current_output_tree_hash:
            # 如果没有当前状态 (例如，在创世之前)，将所有内容视为可达，
            # 以避免 UI 显示全灰色。
            return True
        return output_tree_hash in self.reachable_set
~~~~~
~~~~~python
    def is_reachable(self, output_tree_hash: str) -> bool:
        """检查一个节点哈希是否在可达性集合中。"""
        if not self.current_output_tree_hash:
            # 如果没有当前状态 (例如，在创世之前)，将所有内容视为可达，
            # 以避免 UI 显示全灰色。
            return True
        return output_tree_hash in self.reachable_set

    def calculate_initial_page(self) -> int:
        """根据当前 HEAD 位置计算其所在的页码"""
        if not self.current_output_tree_hash:
            return 1

        position = self.reader.get_node_position(self.current_output_tree_hash)
        if position == -1:
            return 1

        # position 是从 0 开始的索引
        # e.g. pos 0 -> page 1; pos 49 -> page 1; pos 50 -> page 2
        return (position // self.page_size) + 1
~~~~~

#### Acts 5: TUI 修复 (CLI - TUI)

1.  移除强制连线逻辑。
2.  启动时跳转到计算出的页码。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []
        # Add the current node's full ancestry to the initial tracks to ensure the main line is drawn
        if self.view_model.current_output_tree_hash:
            tracks.append(self.view_model.current_output_tree_hash)

        for node in nodes_to_render:
~~~~~
~~~~~python
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []

        for node in nodes_to_render:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
        table = self.query_one(DataTable)
        table.add_columns("Time", "Graph", "Node Info")

        logger.debug("TUI: Loading first page...")
        self._load_page(1)

    def on_unmount(self) -> None:
~~~~~
~~~~~python
        table = self.query_one(DataTable)
        table.add_columns("Time", "Graph", "Node Info")

        # 计算 HEAD 所在的页码并跳转
        initial_page = self.view_model.calculate_initial_page()
        logger.debug(f"TUI: HEAD is on page {initial_page}. Loading...")
        self._load_page(initial_page)

    def on_unmount(self) -> None:
~~~~~
