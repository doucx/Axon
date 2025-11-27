好的，明白了。我将只更新 `tests/helpers.py` 文件，为 `InMemoryHistoryManager` 实现缺失的接口方法。

### fix(tests): 为 InMemoryHistoryManager 实现新接口

### 错误分析
`InMemoryHistoryManager` 未实现 `HistoryReader` 接口中新增的 `get_descendant_output_trees` 和 `get_node_position` 方法，导致依赖它的 `memory_engine` 相关测试全部失败。

### 用户需求
修复 `tests/engine/test_engine_memory.py` 中的测试错误。

### 目标
在 `InMemoryHistoryManager` 中添加 `get_descendant_output_trees` 和 `get_node_position` 方法的内存实现。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新 `tests/helpers.py`

~~~~~act
patch_file
tests/helpers.py
~~~~~
~~~~~python
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        内存后端的节点查找实现，通过在内存中过滤所有节点来工作。
        """
        candidates = self.load_all_nodes()

        if summary_regex:
            try:
                pattern = re.compile(summary_regex, re.IGNORECASE)
                candidates = [node for node in candidates if pattern.search(node.summary)]
            except re.error:
                return []  # 在测试中，无效的正则表达式直接返回空列表

        if node_type:
            candidates = [node for node in candidates if node.node_type == node_type]

        # 按时间戳降序排序
        candidates.sort(key=lambda n: n.timestamp, reverse=True)

        return candidates[:limit]
~~~~~
~~~~~python
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        内存后端的节点查找实现，通过在内存中过滤所有节点来工作。
        """
        candidates = self.load_all_nodes()

        if summary_regex:
            try:
                pattern = re.compile(summary_regex, re.IGNORECASE)
                candidates = [node for node in candidates if pattern.search(node.summary)]
            except re.error:
                return []  # 在测试中，无效的正则表达式直接返回空列表

        if node_type:
            candidates = [node for node in candidates if node.node_type == node_type]

        # 按时间戳降序排序
        candidates.sort(key=lambda n: n.timestamp, reverse=True)

        return candidates[:limit]

    def get_descendant_output_trees(self, start_output_tree_hash: str) -> Set[str]:
        """内存实现：通过广度优先搜索遍历子节点。"""
        descendants = set()
        queue = []

        if start_output_tree_hash in self.db.nodes:
            queue.append(self.db.nodes[start_output_tree_hash])

        while queue:
            current_node = queue.pop(0)
            for child in current_node.children:
                c_hash = child.output_tree
                if c_hash not in descendants:
                    descendants.add(c_hash)
                    if c_hash in self.db.nodes:
                        queue.append(self.db.nodes[c_hash])
        return descendants

    def get_node_position(self, output_tree_hash: str) -> int:
        """内存实现：排序并查找索引。"""
        all_nodes = sorted(self.db.nodes.values(), key=lambda n: n.timestamp, reverse=True)
        for i, node in enumerate(all_nodes):
            if node.output_tree == output_tree_hash:
                return i
        return -1
~~~~~
