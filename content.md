好的，`quipu ui` 中可达性高亮显示的错误确实会严重影响历史图谱的可读性。我已经定位到 `get_ancestor_hashes` 方法中的 SQL 查询问题，并准备好了一个使用更健壮的递归公共表表达式 (CTE) 的修复方案。

这个方案将确保从任意节点出发，都能正确地回溯并返回其完整的祖先路径。

## fix(engine): 修正用于祖先节点查找的递归查询

### 错误分析
当前在 `quipu ui` 中，高亮显示可达节点的逻辑存在缺陷。它仅将当前活动节点附近的少数祖先节点标记为可达，而通往根节点的整条主干路径上的其他节点都显示为暗色。此问题源于 `sqlite_storage.py` 中 `get_ancestor_hashes` 方法的 SQL 递归查询未能正确返回完整的祖先节点集合。

### 用户需求
用户期望在 `quipu ui` 中，从当前高亮的节点回溯到初始节点的完整路径都应被高亮显示为“可达”，以清晰地展示节点的历史沿革。

### 评论
这是一个影响核心用户体验的关键修复。历史图谱的正确可视化是 Quipu 的核心功能之一，修复此问题可以显著提升 UI 的可用性和直观性。

### 目标
修改 `SQLiteHistoryReader.get_ancestor_hashes` 方法，使其能够正确返回给定 `commit_hash` 的所有祖先节点的哈希集合。

### 基本原理
当前的递归查询存在逻辑缺陷或容易被 SQLite 规划器错误解析。我将采用一种更明确、更健壮的递归 CTE 写法：
1.  **起点**: 查询从给定的 `commit_hash` 节点本身开始。
2.  **递归**: 向上遍历 `edges` 表，持续查找父节点，并将找到的父节点加入到结果集中。
3.  **结果**: 最终返回的结果集将排除作为起点的 `commit_hash` 本身，从而得到一个纯粹的、完整的祖先节点哈希集合。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #concept/history #scope/core
#ai/instruct
#task/domain/ui #task/object/history-graph #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修正 `get_ancestor_hashes` 的 SQL 实现

我将使用 `patch_file` 指令，精确地替换 `sqlite_storage.py` 文件中存在问题的方法。

~~~~~act
patch_file packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        """
        获取指定节点的所有祖先节点的哈希集合 (用于可达性分析)。
        使用 Recursive CTE 在数据库层面高效完成。
        """
        conn = self.db_manager._get_conn()
        try:
            # 这个递归 CTE 从给定的节点开始，向上爬取所有父节点。
            # 然后我们从这次爬取的结果中选择所有哈希，但排除起始节点本身。
            sql = """
            WITH RECURSIVE upward_crawl(node_hash) AS (
                VALUES(?)
                UNION ALL
                SELECT e.parent_hash
                FROM upward_crawl uc, edges e
                WHERE e.child_hash = uc.node_hash
            )
            SELECT node_hash FROM upward_crawl WHERE node_hash != ?;
            """
            # 我们需要将 commit_hash 两次传递给查询
            cursor = conn.execute(sql, (commit_hash, commit_hash))
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"Failed to get ancestors for {commit_hash[:7]}: {e}")
            return set()
~~~~~

### 下一步建议
在应用此修复后，请重新运行 `quipu ui` 并检查可达性高亮是否按预期工作。如果问题解决，我们可以继续完成 UI 性能优化方案中的其他任务，例如在页脚正确显示页码信息和处理翻页的边界情况。
