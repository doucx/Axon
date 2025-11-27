### refactor: 明确数据访问层的 API 契约

#### 用户需求
`HistoryReader` 接口及其实现 (`SQLiteHistoryReader`, `GitObjectHistoryReader`) 存在标识符模糊的问题。方法的参数和返回值没有明确区分 `commit_hash` 和 `output_tree_hash`，导致上层调用错误。我们需要重构这些接口和实现，以建立清晰、无歧义的 API 契约。

#### 评论
这是消除系统性风险的核心步骤。通过在数据访问层强制执行明确的 API 契约，我们封装了所有标识符转换的复杂性，并为上层应用提供了一个简单、安全、可信赖的接口。这将从根本上解决 UI 中的可达性显示错误。

#### 目标
-   更新 `HistoryReader` 接口，使用明确的参数和方法名。
-   修改 `SQLiteHistoryReader`，正确填充 `QuipuNode.commit_hash`，并实现新的、基于递归 CTE 的 `get_ancestor_output_trees` 方法。
-   修改 `GitObjectHistoryReader`，使其符合新的接口规范。
-   更新 `GitObjectHistoryWriter`，确保新创建的 `QuipuNode` 对象也包含 `commit_hash`。

#### 基本原理
我们将遵循“契约先行”的原则，首先修改 `quipu-interfaces` 中的抽象基类，然后逐一修复每个具体实现以符合新契约。对于 `SQLiteHistoryReader`，我们将利用数据库的能力高效地执行图遍历。对于 `GitObjectHistoryReader`，我们将进行内存中的遍历作为兼容性实现。所有实现都必须将 `commit_hash` 填充到 `QuipuNode` 对象中，使其成为一个自包含的实体。

#### 标签
#intent/refactor #flow/ready #priority/high
#comp/engine #comp/interfaces #concept/history #scope/api #scope/core
#ai/instruct
#task/domain/storage #task/object/api-contract #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 更新 `HistoryReader` 抽象接口

我们首先在 `quipu-interfaces` 中定义新的、清晰的 API 契约。

`````act
patch_file
`````
`````path
packages/quipu-interfaces/src/quipu/core/storage.py
`````
`````python
    @abstractmethod
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        """
        获取指定节点的所有祖先节点的哈希集合 (用于可达性分析)。
        """
        pass

    @abstractmethod
    def get_private_data(self, commit_hash: str) -> Optional[str]:
        """
        获取指定节点的私有数据 (如 intent.md)。
        """
        pass
`````
`````python
    @abstractmethod
    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """
        获取指定状态节点的所有祖先节点的 output_tree 哈希集合 (用于可达性分析)。
        """
        pass

    @abstractmethod
    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        """
        获取指定节点的私有数据 (如 intent.md)。
        """
        pass
`````

---
#### Acts 2: 改造 `SQLiteHistoryReader` 以实现新接口

这是本次重构的核心。我们将更新 `sqlite_storage.py` 以符合新契约，并实现正确的祖先查询逻辑。

**Step 2.1: 更新节点加载逻辑，填充 `commit_hash`**

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
        for row in nodes_data:
            node = QuipuNode(
                # input_tree 将在第二阶段链接
                input_tree="",
                output_tree=row["output_tree"],
                timestamp=datetime.fromtimestamp(row["timestamp"]),
                filename=Path(f".quipu/git_objects/{row['commit_hash']}"),
                node_type=row["node_type"],
                summary=row["summary"],
                # 内容是懒加载的
                content=row["plan_md_cache"] if row["plan_md_cache"] is not None else "",
            )
            temp_nodes[row["commit_hash"]] = node
`````
`````python
        for row in nodes_data:
            commit_hash = row["commit_hash"]
            node = QuipuNode(
                commit_hash=commit_hash,
                # input_tree 将在第二阶段链接
                input_tree="",
                output_tree=row["output_tree"],
                timestamp=datetime.fromtimestamp(row["timestamp"]),
                filename=Path(f".quipu/git_objects/{commit_hash}"),
                node_type=row["node_type"],
                summary=row["summary"],
                # 内容是懒加载的
                content=row["plan_md_cache"] if row["plan_md_cache"] is not None else "",
            )
            temp_nodes[commit_hash] = node
`````

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
            for row in rows:
                commit_hash = row["commit_hash"]
                node_hashes.append(commit_hash)
                nodes_map[commit_hash] = QuipuNode(
                    input_tree="",  # Placeholder
                    output_tree=row["output_tree"],
                    timestamp=datetime.fromtimestamp(row["timestamp"]),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=row["node_type"],
                    summary=row["summary"],
                    content=row["plan_md_cache"] if row["plan_md_cache"] is not None else "",
                )
`````
`````python
            for row in rows:
                commit_hash = row["commit_hash"]
                node_hashes.append(commit_hash)
                nodes_map[commit_hash] = QuipuNode(
                    commit_hash=commit_hash,
                    input_tree="",  # Placeholder
                    output_tree=row["output_tree"],
                    timestamp=datetime.fromtimestamp(row["timestamp"]),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=row["node_type"],
                    summary=row["summary"],
                    content=row["plan_md_cache"] if row["plan_md_cache"] is not None else "",
                )
`````

**Step 2.2: 实现 `get_ancestor_output_trees` 的正确逻辑**

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        """
        获取指定节点的所有祖先节点的哈希集合 (用于可达性分析)。
        使用 Recursive CTE 在数据库层面高效完成。
        """
        conn = self.db_manager._get_conn()
        try:
            sql = """
            WITH RECURSIVE ancestors(parent_hash) AS (
                SELECT parent_hash FROM edges WHERE child_hash = ?
                UNION ALL
                SELECT e.parent_hash FROM edges e, ancestors a WHERE e.child_hash = a.parent_hash
            )
            SELECT parent_hash FROM ancestors;
            """
            cursor = conn.execute(sql, (commit_hash,))
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Failed to get ancestors for {commit_hash[:7]}: {e}")
            return set()

    def get_private_data(self, commit_hash: str) -> Optional[str]:
`````
`````python
    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """
        获取指定状态节点的所有祖先节点的 output_tree 哈希集合 (用于可达性分析)。
        使用三步策略：
        1. 将 output_tree 哈希翻译为 commit_hash。
        2. 使用递归 CTE 查找所有祖先的 commit_hash。
        3. 将祖先 commit_hash 集合翻译回 output_tree 哈希集合。
        """
        conn = self.db_manager._get_conn()
        try:
            # 1. 查找起点的 commit_hash
            cursor = conn.execute("SELECT commit_hash FROM nodes WHERE output_tree = ?", (start_output_tree_hash,))
            row = cursor.fetchone()
            if not row:
                return set()
            start_commit_hash = row[0]

            # 2. 使用递归 CTE 查找所有祖先 commit_hash
            sql = """
            WITH RECURSIVE ancestors(h) AS (
                SELECT parent_hash FROM edges WHERE child_hash = ?
                UNION ALL
                SELECT e.parent_hash FROM edges e, ancestors a WHERE e.child_hash = a.h AND e.parent_hash IS NOT NULL
            )
            SELECT h FROM ancestors WHERE h IS NOT NULL;
            """
            cursor = conn.execute(sql, (start_commit_hash,))
            ancestor_commit_hashes = {row[0] for row in cursor.fetchall()}

            if not ancestor_commit_hashes:
                return set()

            # 3. 将 commit_hash 集合转换为 output_tree 集合
            placeholders = ",".join("?" * len(ancestor_commit_hashes))
            sql_out = f"SELECT output_tree FROM nodes WHERE commit_hash IN ({placeholders})"
            cursor = conn.execute(sql_out, tuple(ancestor_commit_hashes))
            return {row[0] for row in cursor.fetchall()}

        except sqlite3.Error as e:
            logger.error(f"Failed to get ancestors for {start_output_tree_hash[:7]}: {e}")
            return set()

    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
`````

**Step 2.3: 更新 `get_private_data` 和 `get_node_content` 的实现**

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        """
        获取指定节点的私有数据 (如 intent.md)。
        """
        conn = self.db_manager._get_conn()
        try:
            cursor = conn.execute("SELECT intent_md FROM private_data WHERE node_hash = ?", (commit_hash,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get private data for {commit_hash[:7]}: {e}")
            return None
`````
`````python
    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        """
        获取指定节点的私有数据 (如 intent.md)。
        """
        conn = self.db_manager._get_conn()
        try:
            cursor = conn.execute("SELECT intent_md FROM private_data WHERE node_hash = ?", (node_commit_hash,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get private data for {node_commit_hash[:7]}: {e}")
            return None
`````

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
    def get_node_content(self, node: QuipuNode) -> str:
        """
        实现通读缓存策略来获取节点内容。
        """
        if node.content:
            return node.content

        commit_hash = node.filename.name

        # 尝试从 Git 加载内容
        content = self._git_reader.get_node_content(node)
`````
`````python
    def get_node_content(self, node: QuipuNode) -> str:
        """
        实现通读缓存策略来获取节点内容。
        """
        if node.content:
            return node.content

        commit_hash = node.commit_hash

        # 尝试从 Git 加载内容
        content = self._git_reader.get_node_content(node)
`````

---
#### Acts 3: 改造 `GitObjectHistoryReader`

现在我们更新纯 Git 后端，使其与新接口兼容。

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
                node = QuipuNode(
                    # Placeholder, will be filled in the linking phase
                    input_tree="",
                    output_tree=output_tree,
                    timestamp=datetime.fromtimestamp(
                        float(meta_data.get("exec", {}).get("start") or entry["timestamp"])
                    ),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=meta_data.get("type", "unknown"),
                    content=content,
                    summary=meta_data.get("summary", "No summary available"),
                )

                temp_nodes[commit_hash] = node
`````
`````python
                node = QuipuNode(
                    commit_hash=commit_hash,
                    # Placeholder, will be filled in the linking phase
                    input_tree="",
                    output_tree=output_tree,
                    timestamp=datetime.fromtimestamp(
                        float(meta_data.get("exec", {}).get("start") or entry["timestamp"])
                    ),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=meta_data.get("type", "unknown"),
                    content=content,
                    summary=meta_data.get("summary", "No summary available"),
                )

                temp_nodes[commit_hash] = node
`````

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        """Git后端: 在内存中遍历图谱"""
        all_nodes = self.load_all_nodes()
        node_map = {n.output_tree: n for n in all_nodes}

        ancestors = set()
        queue = []

        # 查找起始节点 (commit_hash 在这里对应 output_tree)
        # 注意: load_all_nodes 返回的 node.output_tree 是 key
        # 但传入的可能是 commit_hash (对于 GitObject 后端，output_tree 和 commit_hash 不一样)
        # 这里假设 commit_hash 参数实际上是指 output_tree (因为 HistoryGraph key 是 output_tree)
        # 或者我们需要建立 commit -> node 的映射。
        # 鉴于 GitObjectHistoryReader.load_all_nodes 返回的 nodes filename 实际上包含了 commit hash

        # 为了简化兼容性实现，我们假设这里的 commit_hash 指的是 output_tree (与 UI 行为一致)
        if commit_hash in node_map:
            queue.append(node_map[commit_hash])

        while queue:
            current_node = queue.pop(0)
            if current_node.parent:
                p_hash = current_node.parent.output_tree
                if p_hash not in ancestors:
                    ancestors.add(p_hash)
                    queue.append(current_node.parent)

        return ancestors

    def get_private_data(self, commit_hash: str) -> Optional[str]:
`````
`````python
    def get_ancestor_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """Git后端: 在内存中遍历图谱"""
        all_nodes = self.load_all_nodes()
        node_map = {n.output_tree: n for n in all_nodes}

        ancestors = set()
        queue = []

        if start_output_tree_hash in node_map:
            queue.append(node_map[start_output_tree_hash])

        while queue:
            current_node = queue.pop(0)
            if current_node.parent:
                p_hash = current_node.parent.output_tree
                if p_hash not in ancestors:
                    ancestors.add(p_hash)
                    queue.append(current_node.parent)

        return ancestors

    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
`````

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        """Git后端: 不支持私有数据"""
        return None

    def get_node_content(self, node: QuipuNode) -> str:
`````
`````python
    def get_private_data(self, node_commit_hash: str) -> Optional[str]:
        """Git后端: 不支持私有数据"""
        return None

    def get_node_content(self, node: QuipuNode) -> str:
`````

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
        if node.content:
            return node.content

        try:
            # Extract commit hash from the virtual filename
            commit_hash = node.filename.name

            # 1. Get Tree Hash from Commit
            commit_bytes = self.git_db.cat_file(commit_hash, "commit")
`````
`````python
        if node.content:
            return node.content

        try:
            commit_hash = node.commit_hash

            # 1. Get Tree Hash from Commit
            commit_bytes = self.git_db.cat_file(commit_hash, "commit")
`````

---
#### Acts 4: 改造 `GitObjectHistoryWriter`

最后，我们确保写入器在创建新的 `QuipuNode` 实例时，也填充 `commit_hash`。

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
        # 返回一个 QuipuNode 实例，content 此时已在内存中，无需 Lazy Load
        node = QuipuNode(
            input_tree=input_tree,
            output_tree=output_tree,
            timestamp=datetime.fromtimestamp(start_time),
            filename=Path(f".quipu/git_objects/{new_commit_hash}"),
            node_type=node_type,
            content=content,
        )
`````
`````python
        # 返回一个 QuipuNode 实例，content 此时已在内存中，无需 Lazy Load
        node = QuipuNode(
            commit_hash=new_commit_hash,
            input_tree=input_tree,
            output_tree=output_tree,
            timestamp=datetime.fromtimestamp(start_time),
            filename=Path(f".quipu/git_objects/{new_commit_hash}"),
            node_type=node_type,
            content=content,
            summary=summary,  # Populate summary for immediate use
        )
`````
`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
`````
`````python
            # 这里的 filename 实际上存储的是 commit hash
            node.parent = QuipuNode(
                input_tree="",  # Placeholder
                output_tree="",  # Placeholder
                timestamp=datetime.fromtimestamp(0),  # Placeholder
                filename=Path(f".quipu/git_objects/{parent_commit}"),
                node_type="unknown",
                content="",
            )
`````
`````python
            node.parent = QuipuNode(
                commit_hash=parent_commit,
                input_tree="",  # Placeholder
                output_tree=input_tree,  # Use parent's output_tree which is our input_tree
                timestamp=datetime.fromtimestamp(0),  # Placeholder, not critical here
                filename=Path(f".quipu/git_objects/{parent_commit}"),
                node_type="unknown",
                content="",
            )
`````
`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/sqlite_storage.py
`````
`````python
            # 2.3 写入 'edges' 表
            # 关键修改：直接使用 GitWriter 传递回来的确切父节点信息，不再进行 Tree 反查
            if git_node.parent:
                parent_hash = git_node.parent.filename.name
                self.db_manager.execute_write(
                    "INSERT OR IGNORE INTO edges (child_hash, parent_hash) VALUES (?, ?)",
                    (commit_hash, parent_hash),
                )
`````
`````python
            # 2.3 写入 'edges' 表
            # 关键修改：直接使用 GitWriter 传递回来的确切父节点信息，不再进行 Tree 反查
            if git_node.parent:
                parent_commit_hash = git_node.parent.commit_hash
                self.db_manager.execute_write(
                    "INSERT OR IGNORE INTO edges (child_hash, parent_hash) VALUES (?, ?)",
                    (commit_hash, parent_commit_hash),
                )
`````
