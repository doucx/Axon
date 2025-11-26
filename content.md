# [Refactor] 扩展 HistoryReader 接口以支持分页与私有数据

## 用户需求
为了优化 Quipu UI 在处理大量历史记录时的启动性能（秒开）并支持“无限滚动”，以及展示私有数据（开发者意图），需要对底层的 `HistoryReader` 接口进行扩展，从“全量加载”模式转向“按需分页”模式。

## 评论
这是“Quipu UI 性能优化”重构的第一步。修改接口定义是破坏性变更，需要同时更新所有实现类 (`GitObjectHistoryReader`, `SQLiteHistoryReader`, `InMemoryHistoryManager`) 以保持代码库的可编译性和测试通过率。对于非 SQLite 的实现，我们将提供基于全量数据的兼容性实现（Shim）。

## 目标
1.  在 `HistoryReader` 中定义分页 (`load_nodes_paginated`)、计数 (`get_node_count`)、祖先查询 (`get_ancestor_hashes`) 和私有数据 (`get_private_data`) 接口。
2.  更新所有 `HistoryReader` 的子类，提供默认或兼容性实现。

## 基本原理
-   **接口隔离**: 将分页逻辑抽象在接口层，允许后端自由选择实现策略（Git后端在内存中分页，SQLite后端在数据库层分页）。
-   **增量演进**: 先确立契约，后续步骤再填充 `SQLiteHistoryReader` 的高性能实现。
-   **兼容性**: 为 `GitObjectHistoryReader` 提供低效但正确的 fallback 实现，确保现有功能不受影响。

## 标签
#intent/architect #flow/ready #priority/high
#comp/interfaces #comp/engine #comp/tests
#concept/storage #concept/api
#ai/instruct
#task/domain/storage #task/object/history-reader #task/action/expand-interface
#task/state/begin

---

## Script

### Acts 1: 更新接口定义与所有实现类

在 `quipu-interfaces` 中扩展接口，并在 `quipu-engine` 和 `tests` 中更新所有子类。

~~~~~act
replace packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Any, Optional
import re
from .models import QuipuNode
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Set
import re
from .models import QuipuNode
~~~~~
~~~~~act
append_file packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~
~~~~~python

    @abstractmethod
    def get_node_count(self) -> int:
        """
        获取历史节点总数。
        """
        pass

    @abstractmethod
    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        """
        按需加载一页节点数据。
        注意：返回的节点应包含与直接父节点的关系，但不一定构建完整的全量图谱。
        """
        pass

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
~~~~~

### Acts 2: 更新 GitObjectHistoryReader (提供兼容性实现)

为 Git 对象存储提供基于全量加载的 fallback 实现。

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
from typing import Any, Dict, List, Optional
import importlib.metadata
~~~~~
~~~~~python
from typing import Any, Dict, List, Optional, Set
import importlib.metadata
~~~~~
~~~~~act
replace packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
        return list(temp_nodes.values())

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~
~~~~~python
        return list(temp_nodes.values())

    def get_node_count(self) -> int:
        """Git后端: 低效实现，加载所有节点后计数"""
        return len(self.load_all_nodes())

    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        """Git后端: 低效实现，加载所有节点后切片"""
        all_nodes = self.load_all_nodes()
        # load_all_nodes 通常按时间倒序返回
        return all_nodes[offset : offset + limit]

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
        """Git后端: 不支持私有数据"""
        return None

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~

### Acts 3: 更新 SQLiteHistoryReader (添加存根)

添加空实现，避免实例化报错。真正的实现将在下一阶段进行。

~~~~~act
replace packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
from typing import Any, List, Dict, Optional
from datetime import datetime
~~~~~
~~~~~python
from typing import Any, List, Dict, Optional, Set
from datetime import datetime
~~~~~
~~~~~act
replace packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
        return list(temp_nodes.values())

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~
~~~~~python
        return list(temp_nodes.values())

    def get_node_count(self) -> int:
        # 待实现
        return 0

    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        # 待实现
        return []

    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        # 待实现
        return set()

    def get_private_data(self, commit_hash: str) -> Optional[str]:
        # 待实现
        return None

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~

### Acts 4: 更新测试辅助类 InMemoryHistoryManager

更新测试用的内存实现，确保测试套件通过。

~~~~~act
replace tests/helpers.py
~~~~~
~~~~~python
from typing import Dict, List, Optional, Tuple, Any

from quipu.core.models import QuipuNode
~~~~~
~~~~~python
from typing import Dict, List, Optional, Tuple, Any, Set

from quipu.core.models import QuipuNode
~~~~~
~~~~~act
replace tests/helpers.py
~~~~~
~~~~~python
    def load_all_nodes(self) -> List[QuipuNode]:
        return list(self.db.nodes.values())

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~
~~~~~python
    def load_all_nodes(self) -> List[QuipuNode]:
        return list(self.db.nodes.values())

    def get_node_count(self) -> int:
        return len(self.db.nodes)

    def load_nodes_paginated(self, limit: int, offset: int) -> List[QuipuNode]:
        all_nodes = sorted(self.db.nodes.values(), key=lambda n: n.timestamp, reverse=True)
        return all_nodes[offset : offset + limit]

    def get_ancestor_hashes(self, commit_hash: str) -> Set[str]:
        # In memory DB uses output_tree as key
        ancestors = set()
        if commit_hash in self.db.nodes:
            curr = self.db.nodes[commit_hash]
            while curr.parent:
                ancestors.add(curr.parent.output_tree)
                curr = curr.parent
        return ancestors

    def get_private_data(self, commit_hash: str) -> Optional[str]:
        return None

    def get_node_content(self, node: QuipuNode) -> str:
~~~~~
