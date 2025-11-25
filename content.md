# feat: 定义历史记录读写抽象接口

## 用户需求
当前，历史记录的读取和写入逻辑紧密耦合在 `quipu-engine` 的 `Engine` 类中。这使得在不同的存储后端（例如，从当前的文件系统切换到未来的 Git 对象存储）之间进行切换变得困难。为了实现解耦，需要定义一套标准的、抽象的读写接口。

## 评论
这是存储层改造计划的第一步，也是最关键的一步。通过定义清晰的接口，我们引入了策略模式，为后续无缝替换存储实现（从文件系统到 Git 对象）奠定了基础，同时不影响 `Engine` 的核心业务逻辑。

## 目标
在 `quipu-interfaces` 包中创建一个新的模块，用于定义两个抽象基类：`HistoryReader` 和 `HistoryWriter`。这些接口将作为所有历史记录存储实现的“契约”，明确规定了读取和创建历史节点所需的核心方法。

## 基本原理
本计划遵循“面向接口编程”和“依赖注入”的设计原则。我们首先定义“做什么”（接口），再实现“怎么做”（具体类）。将这些核心接口放在 `quipu-interfaces` 包中是合适的，因为它们是模块间通信的基础契约，`quipu-engine` 将会依赖并使用这些接口，而不是任何具体的实现。

## 标签
#comp/interfaces #comp/engine #concept/history #scope/api

---

## Script

### Acts 1: 创建存储接口定义文件

在 `quipu-interfaces` 包中创建 `storage.py` 文件，并定义 `HistoryReader` 和 `HistoryWriter` 两个抽象基类。

~~~~~act
write_file
~~~~~

~~~~~path
packages/quipu-interfaces/src/quipu/core/storage.py
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
        """
        pass


class HistoryWriter(ABC):
    """
    一个抽象接口，用于向历史存储后端写入一个新节点。
    """

    @abstractmethod
    def create_node(
        self,
        node_type: str,
        input_tree: str,
        output_tree: str,
        content: str,
        **kwargs: Any,
    ) -> QuipuNode:
        """
        在存储后端创建并持久化一个新的历史节点。

        Args:
            node_type: 节点的类型，例如 'plan' 或 'capture'。
            input_tree: 输入状态树的哈希。
            output_tree: 输出状态树的哈希。
            content: 节点的主要内容 (例如，Markdown 格式的计划) 。
            **kwargs: 针对特定节点类型的附加元数据，
                      例如 'capture' 节点的 'message'。

        Returns:
            新创建的 QuipuNode 实例。
        """
        pass
~~~~~