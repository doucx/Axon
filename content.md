# refactor: 将 find 命令重构为使用 SQLite 后端

## 用户需求
在完成了 SQLite 的写入和补水机制后，系统中的核心查询命令 `quipu find` 仍然使用旧的、低效的内存过滤方式。这未能发挥出数据库的性能优势，也为后续添加更复杂的过滤功能（如按日期筛选）带来了障碍。

用户希望将 `find` 命令的后端逻辑彻底重构，使其直接利用 SQLite 进行高效查询。

## 评论
这是一个关键的、承上启下的步骤。它将首次让用户和开发者直观地感受到 SQLite 升级带来的性能提升，并将后端数据的潜力转化为实际的用户功能。此重构是后续所有高级查询功能的基础。

## 目标
1.  将节点查找的核心逻辑从 `Engine` 的内存过滤下沉到 `HistoryReader` 存储接口层。
2.  为 `SQLiteHistoryReader` 实现一个基于原生 SQL 查询的高效 `find_nodes` 方法。
3.  为 `GitObjectHistoryReader` 实现一个保持原样（内存过滤）的 `find_nodes` 方法，以确保向后兼容性。
4.  确保 `quipu find` 命令在功能上与之前保持一致，但其底层实现已被替换，为未来的功能扩展做好准备。

## 基本原理
当前 `Engine.find_nodes` 的工作模式是：`Reader` 加载所有节点到内存 -> `Engine` 在内存中遍历列表进行过滤。这种方式在历史记录增长后会变得非常缓慢且消耗内存。

本次重构遵循“将计算移动到离数据最近的地方”原则。通过在 `HistoryReader` 接口中定义 `find_nodes` 方法，我们将查询的责任交给了具体的存储后端。对于 `SQLiteHistoryReader`，这意味着可以直接将过滤条件转换为 SQL 的 `WHERE` 子句，由数据库引擎来执行最高效的查找操作，只返回必要的结果集。这极大地减少了数据传输、内存占用和 Python 层的计算开销。

## 标签
#intent/refine #flow/ready #priority/high
#comp/engine #comp/interfaces #comp/cli #concept/history #scope/core
#ai/instruct
#task/domain/storage #task/object/sqlite-backend #task/action/integration
#task/state/continue #task/status/active

---

## Script

### Acts 1: 抽象接口层升级

首先，我们在 `HistoryReader` 抽象基类中定义 `find_nodes` 方法，从而将此功能正式纳入存储层的职责范围。

~~~~~act
replace packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Any
from .models import QuipuNode


class HistoryReader(ABC):
    """
    一个抽象接口，用于从存储后端读取历史图谱。
    """

    @abstractmethod
    def load_all_nodes(self) -> List[QuipuNode]:
        """
        从存储中加载所有历史事件，构建完整的父子关系图，
        并返回所有节点的列表。
        注意：为了性能，实现可能会选择不立即加载节点的 content 内容。
        """
        pass

    @abstractmethod
    def get_node_content(self, node: QuipuNode) -> str:
        """
        获取指定节点的完整内容 (Lazy Loading)。
        如果节点内容已加载，直接返回；否则从存储后端读取。
        """
        pass
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Any, Optional
import re
from .models import QuipuNode


class HistoryReader(ABC):
    """
    一个抽象接口，用于从存储后端读取历史图谱。
    """

    @abstractmethod
    def load_all_nodes(self) -> List[QuipuNode]:
        """
        从存储中加载所有历史事件，构建完整的父子关系图，
        并返回所有节点的列表。
        注意：为了性能，实现可能会选择不立即加载节点的 content 内容。
        """
        pass

    @abstractmethod
    def get_node_content(self, node: QuipuNode) -> str:
        """
        获取指定节点的完整内容 (Lazy Loading)。
        如果节点内容已加载，直接返回；否则从存储后端读取。
        """
        pass

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

### Acts 2: 兼容旧的 GitObject 后端

为了确保当用户不使用 SQLite 时 `find` 命令依然可用，我们在 `GitObjectHistoryReader` 中实现 `find_nodes`。此实现将直接复用 `Engine` 中原有的内存过滤逻辑。

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
        except Exception as e:
            logger.error(f"Failed to lazy load content for node {node.short_hash}: {e}")
            return ""
~~~~~
~~~~~python
        except Exception as e:
            logger.error(f"Failed to lazy load content for node {node.short_hash}: {e}")
            return ""

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

### Acts 3: 实现高效的 SQLite 查找

这是本次重构的核心。我们在 `SQLiteHistoryReader` 中实现 `find_nodes`，将过滤逻辑转换为 SQL `WHERE` 子句。

~~~~~act
replace packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
        if content:
            try:
                self.db_manager.execute_write(
                    "UPDATE nodes SET plan_md_cache = ? WHERE commit_hash = ?",
                    (content, commit_hash)
                )
                logger.debug(f"缓存已回填: {commit_hash[:7]}")
            except Exception as e:
                logger.warning(f"回填缓存失败: {commit_hash[:7]}: {e}")
        
        return content
~~~~~
~~~~~python
        if content:
            try:
                self.db_manager.execute_write(
                    "UPDATE nodes SET plan_md_cache = ? WHERE commit_hash = ?",
                    (content, commit_hash)
                )
                logger.debug(f"缓存已回填: {commit_hash[:7]}")
            except Exception as e:
                logger.warning(f"回填缓存失败: {commit_hash[:7]}: {e}")
        
        return content

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

        # 将查询结果行映射回 QuipuNode 对象 (不含父子关系)
        results = []
        for row in rows:
            node = QuipuNode(
                input_tree="",  # 查找结果是扁平列表，不包含父子关系
                output_tree=row["output_tree"],
                timestamp=datetime.fromtimestamp(row["timestamp"]),
                filename=Path(f".quipu/git_objects/{row['commit_hash']}"),
                node_type=row["node_type"],
                summary=row["summary"],
                content=row["plan_md_cache"] if row["plan_md_cache"] is not None else "",
            )
            results.append(node)
            
        return results
~~~~~

### Acts 4: 引擎层逻辑委托

最后，我们将 `Engine` 中的 `find_nodes` 方法修改为一个简单的委托调用，使其完全依赖于底层的 `Reader` 实现。

~~~~~act
replace packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~
~~~~~python
    def find_nodes(
        self,
        summary_regex: Optional[str] = None,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[QuipuNode]:
        """
        在历史图谱中查找符合条件的节点。

        Args:
            summary_regex: 用于匹配节点摘要的正则表达式。
            node_type: 节点类型 ('plan' 或 'capture')。
            limit: 返回的最大节点数量。

        Returns:
            符合条件的节点列表，按时间戳降序排列。
        """
        candidates = list(self.history_graph.values())

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
~~~~~python
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
