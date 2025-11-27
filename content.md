### refactor: 适配逻辑与表现层以遵循明确的 API 契约

#### 用户需求
在数据模型 (`QuipuNode`) 和数据访问层 (`HistoryReader`) 的 API 契约更新后，上层的业务逻辑 (`ViewModel`)、用户界面 (`TUI`) 和命令行入口 (`CLI`) 仍在使用旧的、模糊的标识符和方法。这导致了大量的 `TypeError` 和 `AttributeError`。我们需要全面适配这些上层模块，使其正确使用新的 API。

#### 评论
这是重构的收尾阶段，旨在使整个调用链恢复一致和健康。通过将明确的标识符 (`commit_hash`, `output_tree_hash`) 贯穿始终，并适配新的方法签名，我们将彻底修复 UI 的可达性 bug，并使代码的意图更加清晰，易于维护。

#### 目标
-   重构 `GraphViewModel` 以使用新的 `get_ancestor_output_trees` 方法和显式命名的哈希。
-   更新 `QuipuUiApp` (TUI) 以正确地与 `GraphViewModel` 交互，并直接从 `QuipuNode` 对象中获取 `commit_hash`。
-   清理 `main.py` 中的 CLI 命令，将所有模糊的 `hash` 变量重命名，以反映其真实类型。
-   修正上一阶段中 `QuipuNode` 占位符实例化时遗漏的 `summary` 字段。

#### 基本原理
我们继续遵循“自下而上”的策略。数据层和接口已经稳定，现在我们将这种稳定性传递到业务逻辑层和表现层。通过在整个应用中强制使用显式命名，我们消除了所有依赖猜测和隐式契约的代码，从而完成本次架构健康度提升。

#### 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #comp/engine #concept/history #scope/core #scope/ux
#ai/instruct
#task/domain/storage #task/object/api-contract #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: (修正) 完善 `GitObjectHistoryWriter` 中的占位符节点

在进入第三阶段之前，我们先修正第二阶段中一个微小但重要的遗漏：为父节点占位符提供 `summary` 字段，以符合 `QuipuNode` 的构造函数。

`````act
patch_file
`````
`````path
packages/quipu-engine/src/quipu/core/git_object_storage.py
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
`````python
            node.parent = QuipuNode(
                commit_hash=parent_commit,
                input_tree="",  # Placeholder
                output_tree=input_tree,  # Use parent's output_tree which is our input_tree
                timestamp=datetime.fromtimestamp(0),  # Placeholder, not critical here
                filename=Path(f".quipu/git_objects/{parent_commit}"),
                node_type="unknown",
                content="",
                summary="",  # Placeholder
            )
`````
