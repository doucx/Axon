好的，测试已通过。现在我们将把这些修复作为一个完整的逻辑单元进行提交。

我将生成一个 `[COMMIT]` 计划，其中包含 `git add` 和 `git commit` 指令，以将这些重要的修复持久化到版本历史中。

## [COMMIT] fix: 修正 export 测试因节点覆盖和状态不隔离导致的失败

### 用户需求
修复 `quipu export` 命令的测试用例，这些测试因 `Engine` 核心中的节点覆盖缺陷和测试用例本身的状态不隔离问题而失败。

### 评论
这是一个关键的修复，它不仅解决了测试问题，还纠正了 `quipu-engine` 核心设计中一个可能导致数据丢失的缺陷。通过使用 `commit_hash` 作为唯一标识符，我们确保了历史记录的完整性和准确性。将测试用例拆分是保证测试可靠性的标准实践。

### 目标
1.  已修改 `quipu-engine` 的 `state_machine.py`，将 `history_graph` 的键从 `output_tree` 更改为 `commit_hash`。
2.  已更新 `quipu-cli` 中的 `workspace.py`、`navigation.py` 和 `helpers.py` 以适应 `Engine` 的新数据结构。
3.  已将 `tests/cli/test_export_command.py` 中的 `test_export_options` 拆分为两个独立的、状态隔离的测试函数。

### 基本原理
每个 Quipu 节点代表一个独特的历史事件，由其 `commit_hash` 唯一标识。文件系统的状态 (`output_tree`) 可能会在不同事件后保持不变（幂等操作），因此不适合作为唯一键。通过将 `Engine` 的核心数据结构与事件的唯一标识符绑定，我们确保了历史记录的无损性。测试的原子性和隔离性是保证其结果可信的基础，每个测试应在独立的、可预测的环境中运行。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/cli #comp/tests #concept/state #concept/history #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有相关的修复

我们将把所有修改过的文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
~~~~~
~~~~~text
packages/quipu-engine/src/quipu/engine/state_machine.py
packages/quipu-cli/src/quipu/cli/commands/navigation.py
packages/quipu-cli/src/quipu/cli/commands/helpers.py
packages/quipu-cli/src/quipu/cli/commands/workspace.py
tests/cli/test_export_command.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): use commit_hash as unique key for history nodes

Previously, the Engine's `history_graph` used `output_tree` as its dictionary key. This created a critical bug where idempotent nodes (nodes with the same input and output tree hash) would overwrite their parent nodes in the graph, leading to data loss in history-dependent operations like `quipu export`.

This commit changes the primary key for `history_graph` to `commit_hash`, which is guaranteed to be unique for every historical event, thus ensuring the integrity of the history graph.

Additionally, this commit:
- Updates all CLI commands in `navigation`, `workspace`, and `helpers` that relied on the old `output_tree`-keyed structure.
- Fixes the failing tests in `test_export_command.py` by splitting a composite test into two isolated tests, preventing state pollution.
~~~~~

### 下一步建议
- **全面回归测试**: 既然已经对 `Engine` 的核心数据结构进行了修改，建议运行完整的项目测试套件，以确保没有引入未被当前测试覆盖的回归问题。
- **继续开发**: 我们可以继续处理下一个开发任务。
