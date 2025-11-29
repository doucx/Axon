分析正确。测试失败是因为 `quipu run` 在执行包含文件写入的操作时，通常会产生两个节点：一个是捕获工作区变更（新创建的 Plan 文件）的 **Capture Node**，另一个是记录执行过程的 **Plan Node**。

由于 `GitDB` 的实现为每个节点都创建了一个独立的 `refs/quipu/local/heads/` 引用，所以 `heads_after - heads_before` 会包含两个哈希值。

为了修复这个问题，我们需要在 `create_node` 中添加逻辑，从这组新哈希中识别出我们真正关心的那个 **Plan Node**。我们可以通过检查提交信息（Commit Message）来实现这一点，因为 Plan Node 的摘要通常包含我们传入的指令内容（例如 "echo 'content'"）。

## [WIP] fix(tests): 增强 `create_node` 以处理 Capture 和 Plan 双节点场景

### 用户需求
修复 `tests/integration/test_sync_modes.py` 中的断言错误 `AssertionError: Expected 1 new head, but found 2`。

### 评论
这是一个测试辅助函数的逻辑完善。它承认了 Quipu 引擎“捕获漂移”这一核心行为的副作用（即产生额外的 Capture 节点），并通过智能筛选（检查提交信息）来锁定测试真正关注的 Plan 节点。这使得测试既符合系统实际行为，又保持了验证逻辑的准确性。

### 目标
1.  修改 `create_node` 函数。
2.  允许 `new_heads` 的数量为 1 或 2。
3.  如果数量为 2，遍历这些哈希，检查其 `git log` 提交信息。
4.  返回提交信息中包含所执行指令内容（`echo '{content}'`）的那个哈希。

### 基本原理
Capture 节点的提交信息通常是自动生成的差异摘要（如 `Capture: A node_from_b.md`），而 Plan 节点的提交信息则来源于 Plan 内容本身（如 `echo 'node_from_b'`）。通过匹配内容字符串，我们可以明确区分两者，并返回 Plan 节点的哈希用于后续断言。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/sync #task/object/test-helpers #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 增强 `create_node` 辅助函数

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python
def create_node(work_dir: Path, content: str) -> str:
    """Helper to create a node and return its commit hash."""
    heads_before = get_local_quipu_heads(work_dir)

    plan_file = work_dir / f"{content}.md"
    plan_file.write_text(f"~~~~~act\necho '{content}'\n~~~~~")
    result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(work_dir), "-y"])
    assert result.exit_code == 0

    heads_after = get_local_quipu_heads(work_dir)

    new_heads = heads_after - heads_before
    assert len(new_heads) == 1, f"Expected 1 new head, but found {len(new_heads)}"
    return new_heads.pop()
~~~~~
~~~~~python
def create_node(work_dir: Path, content: str) -> str:
    """Helper to create a node and return its commit hash."""
    heads_before = get_local_quipu_heads(work_dir)

    plan_file = work_dir / f"{content}.md"
    plan_file.write_text(f"~~~~~act\necho '{content}'\n~~~~~")
    result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(work_dir), "-y"])
    assert result.exit_code == 0

    heads_after = get_local_quipu_heads(work_dir)
    new_heads = heads_after - heads_before

    if not new_heads:
        raise AssertionError("No new Quipu nodes created.")

    # If only 1 node created, return it.
    if len(new_heads) == 1:
        return new_heads.pop()

    # If 2 nodes created (Capture + Plan), identify the Plan node by its message.
    # The Plan node summary should contain the echoed content.
    for head in new_heads:
        msg = run_git_command(work_dir, ["log", "-1", "--format=%B", head])
        if f"echo '{content}'" in msg:
            return head

    raise AssertionError(
        f"Could not identify Plan node among {len(new_heads)} new heads: {new_heads}"
    )
~~~~~

### 下一步建议
现在 `create_node` 能够正确处理 Quipu 的“双节点”创建行为了。请再次运行测试。一旦所有测试通过，我们将进行最终的提交。
