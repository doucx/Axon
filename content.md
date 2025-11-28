我的错误。

我分析了测试报告和你提供的文件内容。问题非常清楚：**我在上一个计划中把补丁打错了文件**。

我试图将 `get_node_blobs` 方法添加到 `InMemoryHistoryManager` 类中，但这个类实际上定义在 `tests/helpers.py` 文件里，而不是 `tests/engine/test_engine_memory.py`。我的 `patch_file` 指令错误地将这段代码插入到了 `test_engine_memory.py` 的模块级别，这不仅没有解决 `TypeError`，还造成了语法上的混乱。

现在，我将生成一个正确的计划来修正我之前的错误。

## [WIP] fix(tests): 修正错误的补丁位置以修复 `TypeError`

### 错误分析
上一个计划错误地将 `get_node_blobs` 方法的实现添加到了 `tests/engine/test_engine_memory.py` 文件中，而不是它所属的 `InMemoryHistoryManager` 类的定义文件 `tests/helpers.py`。这导致 `InMemoryHistoryManager` 仍然没有实现所需的抽象方法，因此在实例化时继续抛出 `TypeError`。

### 用户需求
1.  清理 `tests/engine/test_engine_memory.py` 中被错误添加的无效代码。
2.  在正确的文件 (`tests/helpers.py`) 中为 `InMemoryHistoryManager` 类实现 `get_node_blobs` 方法。

### 评论
这是一个典型的“修复补丁”操作，它纠正了上一步的执行错误。通过将代码移动到正确的位置，我们将彻底解决 `TypeError`，并让测试套件恢复正常。

### 目标
1.  从 `tests/engine/test_engine_memory.py` 中删除无效的 `get_node_blobs` 函数定义。
2.  在 `tests/helpers.py` 文件中，为 `InMemoryHistoryManager` 类正确地添加 `get_node_blobs` 方法，并导入所需的 `Dict` 类型。

### 基本原理
将方法的实现放置在其所属类的定义内部是 Python 的基本语法要求。通过纠正文件和代码位置，我们将使 `InMemoryHistoryManager` 类符合 `HistoryReader` 接口的契约，从而消除 `TypeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 清理 `test_engine_memory.py` 中的错误代码

首先，我们移除被错误放置的函数。

~~~~~act
patch_file
tests/engine/test_engine_memory.py
~~~~~
~~~~~python
    engine = Engine(root_dir=tmp_path, db=db, reader=history_manager, writer=history_manager)
    return engine


    def get_node_blobs(self, commit_hash: str) -> Dict[str, bytes]:
        """获取一个节点内所有文件的原始二进制内容，以字典形式返回 {filename: content_bytes}。"""
        # For memory backend, this can be implemented if needed, otherwise return empty.
        return {}


class TestEngineWithMemoryBackend:
~~~~~
~~~~~python
    engine = Engine(root_dir=tmp_path, db=db, reader=history_manager, writer=history_manager)
    return engine


class TestEngineWithMemoryBackend:
~~~~~

#### Acts 2: 在 `tests/helpers.py` 中正确实现接口

现在，我们在 `InMemoryHistoryManager` 的定义处添加所需的方法和类型导入。

~~~~~act
patch_file
tests/helpers.py
~~~~~
~~~~~python
from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader, HistoryWriter
~~~~~
~~~~~python
from typing import Dict
from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader, HistoryWriter
~~~~~

~~~~~act
patch_file
tests/helpers.py
~~~~~
~~~~~python
    def __init__(self, db: InMemoryDB):
        self.db = db  # The db holds the single source of truth for nodes

    def load_all_nodes(self) -> List[QuipuNode]:
        return list(self.db.nodes.values())
~~~~~
~~~~~python
    def __init__(self, db: InMemoryDB):
        self.db = db  # The db holds the single source of truth for nodes

    def load_all_nodes(self) -> List[QuipuNode]:
        return list(self.db.nodes.values())

    def get_node_blobs(self, commit_hash: str) -> Dict[str, bytes]:
        # Mock implementation, not needed for most tests.
        return {}

~~~~~

### 下一步建议
我们已经将修复应用到了正确的位置。现在请重新运行测试。预期所有测试都将通过，这将标志着我们对底层接口的重构和相关的测试修复工作已全部完成。
