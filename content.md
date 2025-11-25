# 🚀 升级 Axon 核心数据模型以支持图导航

本计划将通过三个步骤完成数据模型的升级：
1.  为 `AxonNode` 数据类添加 `parent` 和 `children` 字段。
2.  重构 `core/history.py` 中的 `load_history_graph` 函数，使其在加载时构建节点间的连接关系。
3.  添加一个新的单元测试文件 `tests/test_graph_loader.py` 来验证图构建逻辑的正确性。

---

### 步骤 1: 增强 `AxonNode` 数据模型

我们将使用 `replace` 指令，为 `core/models.py` 中的 `AxonNode` 添加图遍历所需的字段，并顺便添加一个 `siblings` 属性方便后续使用。

~~~~~act
replace
~~~~~

~~~~~path
core/models.py
~~~~~

~~~~~python
from __future__ import annotations
import dataclasses
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

@dataclasses.dataclass
class AxonNode:
    """
    表示 Axon 历史图谱中的一个节点。
    
    这个数据类封装了从文件名和文件内容中解析出的所有元数据和状态信息。
    """
    # 从文件名解析
    input_tree: str
    output_tree: str
    timestamp: datetime
    
    # 从文件物理路径
    filename: Path
    
    # 从 Frontmatter 解析
    node_type: str  # "plan" | "capture"
    parent_hint: Optional[str] = None
    
    # 文件主体内容
    content: str = ""

    @property
    def short_hash(self) -> str:
        """返回一个用于UI展示的简短哈希"""
        return self.output_tree[:7]
~~~~~

~~~~~python
from __future__ import annotations
import dataclasses
from pathlib import Path
from typing import Optional, List, Dict # <-- 引入 List
from datetime import datetime

@dataclasses.dataclass
class AxonNode:
    """
    表示 Axon 历史图谱中的一个节点。
    
    这个数据类封装了从文件名和文件内容中解析出的所有元数据和状态信息。
    """
    # 从文件名解析
    input_tree: str
    output_tree: str
    timestamp: datetime
    
    # 从文件物理路径
    filename: Path
    
    # 从 Frontmatter 解析
    node_type: str  # "plan" | "capture"
    parent_hint: Optional[str] = None
    
    # 文件主体内容
    content: str = ""
    
    # --- 图遍历字段 (由加载器填充) ---
    parent: Optional[AxonNode] = None
    children: List[AxonNode] = dataclasses.field(default_factory=list)

    @property
    def short_hash(self) -> str:
        """返回一个用于UI展示的简短哈希"""
        return self.output_tree[:7]

    @property
    def siblings(self) -> List[AxonNode]:
        """获取所有兄弟节点 (包括自身)，按时间排序"""
        if not self.parent:
            return [self]
        return self.parent.children
~~~~~

---

### 步骤 2: 更新历史加载器以构建图关系

现在，我们重构 `load_history_graph` 函数。它将采用“两遍扫描”的策略：第一遍加载所有节点，第二遍根据 `input_tree` 和 `output_tree` 的关系连接它们。

~~~~~act
replace
~~~~~

~~~~~path
core/history.py
~~~~~

~~~~~python
def load_history_graph(history_dir: Path) -> Dict[str, AxonNode]:
    """
    扫描历史目录，加载所有节点，构建一个以 output_tree_hash 为键的图。
    """
    graph: Dict[str, AxonNode] = {}
    if not history_dir.exists():
        return graph

    for file_path in history_dir.glob("*.md"):
        match = FILENAME_PATTERN.match(file_path.name)
        if not match:
            logger.warning(f"跳过格式不匹配的历史文件: {file_path.name}")
            continue
        
        input_hash, output_hash, ts_str = match.groups()
        
        try:
            full_content = file_path.read_text("utf-8")
            meta, body_content = _parse_frontmatter(full_content)
            
            node = AxonNode(
                input_tree=input_hash,
                output_tree=output_hash,
                timestamp=datetime.strptime(ts_str, "%Y%m%d%H%M%S"),
                filename=file_path,
                node_type=meta.get("type", "unknown"),
                parent_hint=meta.get("parent_hint"),
                content=body_content
            )
            graph[output_hash] = node
        except Exception as e:
            logger.error(f"加载历史节点失败 {file_path.name}: {e}")

    logger.info(f"从 '{history_dir}' 加载了 {len(graph)} 个历史节点。")
    return graph
~~~~~

~~~~~python
def load_history_graph(history_dir: Path) -> Dict[str, AxonNode]:
    """
    扫描历史目录，加载所有节点，并构建一个包含父子关系的图。
    返回以 output_tree_hash 为键的节点字典。
    """
    graph: Dict[str, AxonNode] = {}
    if not history_dir.exists():
        return graph

    # --- 第一遍: 加载所有独立的节点 ---
    for file_path in history_dir.glob("*.md"):
        match = FILENAME_PATTERN.match(file_path.name)
        if not match:
            logger.warning(f"跳过格式不匹配的历史文件: {file_path.name}")
            continue
        
        input_hash, output_hash, ts_str = match.groups()
        
        try:
            full_content = file_path.read_text("utf-8")
            meta, body_content = _parse_frontmatter(full_content)
            
            node = AxonNode(
                input_tree=input_hash,
                output_tree=output_hash,
                timestamp=datetime.strptime(ts_str, "%Y%m%d%H%M%S"),
                filename=file_path,
                node_type=meta.get("type", "unknown"),
                parent_hint=meta.get("parent_hint"),
                content=body_content
            )
            graph[output_hash] = node
        except Exception as e:
            logger.error(f"加载历史节点失败 {file_path.name}: {e}")

    # --- 第二遍: 连接父子关系 ---
    for node in graph.values():
        # 节点的 input_tree 就是其父节点的 output_tree
        if node.input_tree in graph:
            parent_node = graph[node.input_tree]
            node.parent = parent_node
            parent_node.children.append(node)

    # 为所有节点的子列表按时间排序，确保导航行为一致
    for node in graph.values():
        node.children.sort(key=lambda n: n.timestamp)

    logger.info(f"从 '{history_dir}' 加载并连接了 {len(graph)} 个历史节点。")
    return graph
~~~~~

---

### 步骤 3: 为图加载器添加单元测试

这是最关键的一步，确保我们的图构建逻辑是正确的。我们将创建一个新的测试文件 `tests/test_graph_loader.py`。

~~~~~act
write_file
~~~~~

~~~~~path
tests/test_graph_loader.py
~~~~~

~~~~~python
import pytest
from pathlib import Path
from datetime import datetime
from core.history import load_history_graph

@pytest.fixture
def graph_history_dir(tmp_path: Path) -> Path:
    """
    创建一个模拟的历史目录，包含一个分叉的图结构：
    A -> B
      -> C (C 比 B 新)
    """
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    
    hash_a = "a" * 40
    hash_b = "b" * 40
    hash_c = "c" * 40
    genesis = "_" * 40

    # 节点 A (根)
    (history_dir / f"{genesis}_{hash_a}_20230101000000.md").write_text("---\ntype: plan\n---")
    # 节点 B (A 的子节点)
    (history_dir / f"{hash_a}_{hash_b}_20230101010000.md").write_text("---\ntype: plan\n---")
    # 节点 C (A 的子节点, C is newer than B)
    (history_dir / f"{hash_a}_{hash_c}_20230101020000.md").write_text("---\ntype: plan\n---")
    
    return history_dir


class TestGraphLoader:

    def test_graph_loading_and_linking(self, graph_history_dir: Path):
        graph = load_history_graph(graph_history_dir)
        
        assert len(graph) == 3
        
        hash_a = "a" * 40
        hash_b = "b" * 40
        hash_c = "c" * 40
        
        node_a = graph[hash_a]
        node_b = graph[hash_b]
        node_c = graph[hash_c]
        
        # 1. 验证父子关系
        assert node_a.parent is None
        assert node_b.parent == node_a
        assert node_c.parent == node_a
        
        # 2. 验证子节点列表
        assert len(node_a.children) == 2
        # 验证子节点已按时间戳排序
        assert node_a.children == [node_b, node_c]
        assert len(node_b.children) == 0
        assert len(node_c.children) == 0
        
        # 3. 验证兄弟关系
        assert node_b.siblings == [node_b, node_c]
        assert node_c.siblings == [node_b, node_c]
        # 根节点没有兄弟
        assert node_a.siblings == [node_a]
~~~~~

---

## ✅ 完成

执行完这份 Markdown 脚本后，Axon 的核心数据模型和历史加载器就完成了升级，并且有了相应的测试保障。

现在，我们可以基于这个坚实的基础来开发 `undo`, `redo`, `prev`, `next` 等导航命令以及 TUI 界面了。