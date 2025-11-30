好的，我们已经成功修复了 Bug 并添加了健壮的回归测试。现在，我们将把这些工作成果作为一个完整的逻辑单元，提交到版本控制中。

我将生成一个 `[COMMIT]` 计划，其中只包含 `git add` 和 `git commit` 操作。

## [COMMIT] fix(engine): 确保 save 命令正确使用 HEAD 指针作为父节点

### 用户需求
系统在执行 `quipu save`（即 `capture_drift`）操作时，必须将 `.quipu/HEAD` 文件指向的状态作为新快照的父节点。此前存在一个回归 Bug，该 Bug 会导致 `HEAD` 指针被忽略，并错误地回退到使用时间上最新的节点作为父节点，从而破坏历史图谱的拓扑结构。

### 评论
这是一个至关重要的核心逻辑修复。历史图谱的正确性和可靠性是 Quipu 系统的基石。本次修复，连同新增的、覆盖了非线性历史场景的回归测试，彻底解决了此问题，确保了 `save` 操作的原子性和历史的连续性。

### 目标
1.  已在 `engine/state_machine.py` 中修正 `capture_drift` 方法，通过正确的 Tree Hash 查找来定位父节点。
2.  已在 `tests/engine/test_head_tracking.py` 中添加了一个名为 `test_capture_drift_on_detached_head` 的回归测试，以确保此 Bug 不会再次出现。
3.  创建一个符合规范的 Git 提交，将这些变更永久记录下来。

### 基本原理
修复方案将错误的“哈希类型不匹配的字典查找”替换为正确的“遍历节点并比较 `output_tree`”的逻辑。新增的测试通过创建一个 `HEAD` 指针与最新节点不一致的“分离 HEAD”场景，来精确验证 `capture_drift` 是否严格遵循 `HEAD` 指针，从而保证了修复的健壮性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/state #concept/history #scope/core #ai/instruct #task/domain/storage #task/object/head-pointer #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交修复和测试

现在，我们将被修改的引擎代码和新的测试文件添加到暂存区，并创建一个详细的提交。

~~~~~act
git_add
packages/quipu-engine/src/pyquipu/engine/state_machine.py
tests/engine/test_head_tracking.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): ensure save command correctly uses HEAD for parentage

This commit fixes a critical regression bug where the `capture_drift`
method (the core of `quipu save`) failed to correctly identify the
parent node.

The root cause was an incorrect lookup logic that attempted to find a
Tree Hash (from the .quipu/HEAD file) within a dictionary keyed by
Commit Hashes. This lookup would always fail, causing the logic to
erroneously fall back to using the latest node by timestamp as the
parent, thus corrupting the graph topology in non-linear scenarios.

The fix replaces this flawed lookup with a proper iteration over the
history graph nodes, matching the node's `output_tree` with the HEAD's
Tree Hash.

Additionally, a robust regression test (`test_capture_drift_on_detached_head`)
has been added. It verifies the fix by creating a scenario where the HEAD
pointer and the latest node are different, ensuring that the parent is
chosen based on the HEAD pointer alone.
~~~~~

### 下一步建议
- **代码审查**: 既然核心的 HEAD 追踪逻辑已经得到修复和加强，我们可以考虑审查一下其他依赖 `HEAD` 的命令（如 `discard`），确保它们也使用了同样健壮的逻辑。
- **性能**: 对于非常大的历史图谱，遍历查找父节点可能会有性能开销。可以考虑在未来引入一个从 `output_tree` 到 `commit_hash` 的反向映射缓存来优化此查找过程。
