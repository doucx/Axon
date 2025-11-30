你的分析非常准确。当前的 `log` 和 `export` 命令首先将整个历史图谱加载到内存中，然后在应用层（Python）进行过滤，这对于拥有大量历史记录的项目来说是不可扩展的。特别是对于 SQLite 后端，这完全浪费了 SQL 数据库强大的查询和过滤能力。

我将制定一个计划，将这些过滤逻辑（时间范围、可达性）下沉到 `Engine` 和 `Storage` 层。

## [WIP] perf: 将可达性与时间过滤逻辑下沉至存储层

### 用户需求
1.  优化 `log --reachable-only` 和 `export --reachable-only` 命令的性能。
2.  利用 SQLite 数据库的能力来执行图遍历和过滤，避免在应用层加载全量数据。
3.  修复 `patch_file` 调用时参数不足的错误。

### 评论
这是一个关键的架构优化。通过扩展 `HistoryReader.find_nodes` 接口，使其支持 `since`, `until` 和 `reachable_from` 参数，我们可以将“怎么查”的逻辑封装在具体的存储实现中。对于 SQLite，这意味着可以使用 `WITH RECURSIVE` CTE 和 `WHERE` 子句在数据库内部完成所有工作；对于 Git 对象存储，则保持现有的内存过滤逻辑作为回退。这不仅提升了性能，也简化了 CLI 层的逻辑。

### 目标
1.  修改 `packages/quipu-interfaces` 中的 `HistoryReader.find_nodes` 签名，增加时间与可达性参数。
2.  在 `packages/quipu-engine` 的 `SQLiteHistoryReader` 中实现基于 SQL 的高效查询。
3.  在 `packages/quipu-engine` 的 `GitObjectHistoryReader` 中更新相应的内存实现。
4.  重构 `quipu-cli` 的 `log` 和 `export` 命令，使其调用新的引擎 API。

### 基本原理
目前的 `helpers.filter_nodes` 和 `helpers.filter_reachable_nodes` 是在获取所有节点后在 Python 端运行的。通过将这些参数传递给 `find_nodes`：
- **SQLite**: 可以生成一个包含 `AND timestamp >= ?` 和递归 CTE 的单一 SQL 查询，只返回需要的数据。
- **CLI**: 不再需要直接访问 `engine.history_graph`（这通常意味着全量加载），支持了 Lazy 加载模式下的高效查询。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/cli #comp/interfaces #concept/state #task/domain/storage #task/object/sqlite-backend #task/action/optimization #task/state/begin

---

### Script

#### Acts 1: 更新接口定义

首先，我们需要扩展 `HistoryReader` 接口，允许传递更多的过滤条件。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-interfaces/src/pyquipu/interfaces/storage.py
~~~~~
~~~~~old_string
    @abstractmethod
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        根据条件查找历史节点。
        """
        pass
~~~~~
~~~~~new_string
    @abstractmethod
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        reachable_from: Optional[str] = None,
    ) -> List[QuipuNode]:
        """
        根据条件查找历史节点。

        Args:
            summary_regex: 用于匹配摘要的正则表达式。
            node_type: 节点类型过滤。
            limit: 返回结果的最大数量。
            since: 起始时间（包含）。
            until: 结束时间（包含）。
            reachable_from: 如果提供，仅返回从该 output_tree 哈希可达的节点（祖先）。
        """
        pass
~~~~~

#### Acts 2: 更新 SQLite 存储实现

这是核心优化。我们将构建一个能够处理所有这些条件的 SQL 查询。如果指定了 `reachable_from`，我们将使用 CTE 来限制搜索范围。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-engine/src/pyquipu/engine/sqlite_storage.py
~~~~~
~~~~~old_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        直接在 SQLite 数据库中执行高效的节点查找。
        """
        query = "SELECT * FROM nodes"
        conditions = []
        params = []

        if node_type:
            conditions.append("node_type = ?")
            params.append(node_type)

        # 注意: 标准 SQLite 不支持 REGEXP。
        # 此处使用 LIKE 实现简单的子字符串匹配作为替代。
        # 完整的正则支持需要加载扩展或在 Python 端进行二次过滤。
        if summary_regex:
            conditions.append("summary LIKE ?")
            params.append(f"%{summary_regex}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self.db_manager._get_conn()
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
~~~~~
~~~~~new_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        reachable_from: Optional[str] = None,
    ) -> List[QuipuNode]:
        """
        直接在 SQLite 数据库中执行高效的节点查找。
        """
        params = []
        conditions = []
        
        # Base query structure
        if reachable_from:
            # First, resolve the output_tree to a commit_hash
            conn = self.db_manager._get_conn()
            cursor = conn.execute("SELECT commit_hash FROM nodes WHERE output_tree = ?", (reachable_from,))
            row = cursor.fetchone()
            start_commit_hash = row[0] if row else None
            
            if not start_commit_hash:
                return []

            # Use CTE to define the scope of 'nodes'
            query = """
            WITH RECURSIVE reachable(h) AS (
                SELECT ? 
                UNION ALL
                SELECT e.parent_hash FROM edges e, reachable r WHERE e.child_hash = r.h AND e.parent_hash IS NOT NULL
            )
            SELECT n.* FROM nodes n
            JOIN reachable r ON n.commit_hash = r.h
            """
            params.append(start_commit_hash)
        else:
            query = "SELECT * FROM nodes"

        # Add filters
        if node_type:
            conditions.append("node_type = ?")
            params.append(node_type)

        if summary_regex:
            # SQLite default is LIKE, not REGEXP
            conditions.append("summary LIKE ?")
            params.append(f"%{summary_regex}%")

        if since:
            conditions.append("timestamp >= ?")
            params.append(since.timestamp())
        
        if until:
            conditions.append("timestamp <= ?")
            params.append(until.timestamp())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        conn = self.db_manager._get_conn()
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()
~~~~~

#### Acts 3: 更新 Git 对象存储实现

Git 实现必须保持接口兼容，尽管它需要在内存中进行过滤。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-engine/src/pyquipu/engine/git_object_storage.py
~~~~~
~~~~~old_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        GitObject 后端的查找实现。
        由于没有索引，此实现加载所有节点并在内存中进行过滤。
        """
        # 这是一个高成本操作，因为它需要加载整个图
        candidates = self.load_all_nodes()

        if summary_regex:
            try:
                pattern = re.compile(summary_regex, re.IGNORECASE)
                candidates = [node for node in candidates if pattern.search(node.summary)]
            except re.error as e:
                logger.error(f"无效的正则表达式: {summary_regex} ({e})")
                return []

        if node_type:
            candidates = [node for node in candidates if node.node_type == node_type]

        # 按时间戳降序排序
        candidates.sort(key=lambda n: n.timestamp, reverse=True)

        return candidates[:limit]
~~~~~
~~~~~new_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        reachable_from: Optional[str] = None,
    ) -> List[QuipuNode]:
        """
        GitObject 后端的查找实现。
        由于没有索引，此实现加载所有节点并在内存中进行过滤。
        """
        # 这是一个高成本操作，因为它需要加载整个图
        candidates = self.load_all_nodes()

        if reachable_from:
            ancestors = self.get_ancestor_output_trees(reachable_from)
            ancestors.add(reachable_from)
            candidates = [n for n in candidates if n.output_tree in ancestors]

        if summary_regex:
            try:
                pattern = re.compile(summary_regex, re.IGNORECASE)
                candidates = [node for node in candidates if pattern.search(node.summary)]
            except re.error as e:
                logger.error(f"无效的正则表达式: {summary_regex} ({e})")
                return []

        if node_type:
            candidates = [node for node in candidates if node.node_type == node_type]
        
        if since:
            candidates = [node for node in candidates if node.timestamp >= since]
        
        if until:
            candidates = [node for node in candidates if node.timestamp <= until]

        # 按时间戳降序排序
        candidates.sort(key=lambda n: n.timestamp, reverse=True)

        return candidates[:limit]
~~~~~

#### Acts 4: 更新 Engine 代理

`Engine` 类也需要更新其 `find_nodes` 方法以透传新参数。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~old_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        在历史图谱中查找符合条件的节点。
        此方法现在委托给配置的 HistoryReader 来执行查找。
        """
        return self.reader.find_nodes(
            summary_regex=summary_regex,
            node_type=node_type,
            limit=limit,
        )
~~~~~
~~~~~new_string
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        reachable_from: Optional[str] = None,
    ) -> List[QuipuNode]:
        """
        在历史图谱中查找符合条件的节点。
        此方法现在委托给配置的 HistoryReader 来执行查找。
        """
        return self.reader.find_nodes(
            summary_regex=summary_regex,
            node_type=node_type,
            limit=limit,
            since=since,
            until=until,
            reachable_from=reachable_from,
        )
~~~~~

#### Acts 5: 重构 CLI - log 命令

现在我们更新 `log` 命令，使用新的 `engine.find_nodes` API，移除对 `helpers.filter_nodes` 的依赖。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/pyquipu/cli/commands/query.py
~~~~~
~~~~~old_string
            if not graph:
                if json_output:
                    bus.data("[]")
                else:
                    bus.info("query.info.emptyHistory")
                raise typer.Exit(0)

            nodes_to_process = sorted(graph.values(), key=lambda n: n.timestamp, reverse=True)

            if reachable_only:
                nodes_to_process = filter_reachable_nodes(engine, nodes_to_process)

            try:
                nodes = filter_nodes(nodes_to_process, limit, since, until)
            except typer.BadParameter as e:
                bus.error("common.error.invalidConfig", error=str(e))
                ctx.exit(1)
~~~~~
~~~~~new_string
            if not graph:
                if json_output:
                    bus.data("[]")
                else:
                    bus.info("query.info.emptyHistory")
                raise typer.Exit(0)

            # 解析时间参数
            since_dt = None
            until_dt = None
            try:
                if since:
                    since_dt = datetime.fromisoformat(since.replace(" ", "T"))
                if until:
                    until_dt = datetime.fromisoformat(until.replace(" ", "T"))
            except ValueError:
                bus.error("common.error.invalidConfig", error="无效的时间戳格式，请使用 'YYYY-MM-DD HH:MM'")
                ctx.exit(1)

            current_hash = engine.git_db.get_tree_hash()
            reachable_from = current_hash if reachable_only else None

            # 使用下沉后的 Engine API 进行查询
            nodes = engine.find_nodes(
                limit=limit if limit is not None else 100, # 设置一个合理的默认上限
                since=since_dt,
                until=until_dt,
                reachable_from=reachable_from
            )
~~~~~

#### Acts 6: 重构 CLI - export 命令

同样更新 `export` 命令。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/pyquipu/cli/commands/export.py
~~~~~
~~~~~old_string
            nodes_to_process = sorted(engine.history_graph.values(), key=lambda n: n.timestamp, reverse=True)

            if reachable_only:
                nodes_to_process = filter_reachable_nodes(engine, nodes_to_process)

            try:
                # filter_nodes returns preserving input order (reverse chrono),
                # but export expects chronological order for file generation/processing
                filtered = filter_nodes(nodes_to_process, limit, since, until)
                nodes_to_export = list(reversed(filtered))
            except typer.BadParameter as e:
                bus.error("export.error.badParam", error=str(e))
                ctx.exit(1)
~~~~~
~~~~~new_string
            # 解析时间参数
            since_dt = None
            until_dt = None
            try:
                if since:
                    since_dt = datetime.fromisoformat(since.replace(" ", "T"))
                if until:
                    until_dt = datetime.fromisoformat(until.replace(" ", "T"))
            except ValueError:
                bus.error("export.error.badParam", error="无效的时间戳格式")
                ctx.exit(1)

            current_hash = engine.git_db.get_tree_hash()
            reachable_from = current_hash if reachable_only else None

            # 使用 Engine API 查询
            # 注意: export 默认可能需要导出全部，所以 limit 默认值如果不传应为 None 或很大
            # 这里我们如果 limit 为 None，就不传给 find_nodes (其默认是 10)，或者传一个很大的数
            # 更好的做法是在 Engine find_nodes 里处理 limit=-1 代表无限
            # 暂时为了兼容性，如果不传 limit，我们不依赖 find_nodes 的默认 10，而是传 maxsize
            
            import sys
            nodes_found = engine.find_nodes(
                limit=limit if limit is not None else sys.maxsize,
                since=since_dt,
                until=until_dt,
                reachable_from=reachable_from
            )
            
            # export expects chronological order (oldest first) for processing
            nodes_to_export = list(reversed(nodes_found))
~~~~~

### 下一步建议
我们已经完成了核心逻辑的重构。下一步应该运行测试，确保新的 `find_nodes` 在两种存储后端下行为一致，并且 `log` 和 `export` 命令在开启和关闭 `reachable_only` 时都能正确过滤节点。特别是要验证 SQLite 后端生成的 SQL 语句是否正确使用了 CTE。
