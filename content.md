分析正确。测试仍然失败，这表明我们通过检查提交信息来识别 Plan 节点的逻辑存在偏差。

错误分析

**问题定位**:
在 `create_node` 中，我们试图通过查找 `echo '{content}'` 字符串来识别 Plan 节点。然而，`quipu-engine` 生成的默认摘要逻辑可能并没有将 `act` 块中的具体参数（如 `echo` 的内容）直接作为 Plan 节点的 `Summary`。

Plan 节点的摘要生成逻辑主要依赖：
1.  Markdown 文件中的标题（`# Title`）。
2.  如果没有标题，则取第一行。
3.  如果第一行是 Act 指令，则可能只是简略显示。

在测试用例中，我们生成的 Plan 文件内容是：
```markdown
~~~~~act
echo 'content'
~~~~~
```
这个 Plan 没有标题，也没有描述性的第一行。因此，它的 Summary 很可能只是 "Plan executed" 或者 "echo..."，而不包含完整的 `'content'` 字符串。

相反，**Capture 节点** 是用来记录工作区变更的。由于我们在运行 `quipu run` 之前创建了 `plan_file`，所以 Capture 节点会记录这个新文件的添加。其摘要类似于 `Capture: A b_node_to_keep.md`。

**解决方案**:
我们可以利用这两个节点在语义上的区别来识别它们：
1.  **Capture 节点**：其摘要通常包含 "Capture:" 字样。
2.  **Plan 节点**：它是我们真正想要执行的操作记录。

我们可以简单地通过**排除法**来识别 Plan 节点：如果一个节点不是 Capture 节点，那它就是 Plan 节点。或者更稳健地，我们可以给测试用的 Plan 文件加上一个显式的标题，这样我们就能 100% 确定 Plan 节点的摘要内容了。

## [WIP] fix(tests): 为测试用的 Plan 文件添加标题以稳定摘要匹配

### 用户需求
修复 `tests/integration/test_sync_modes.py` 中的断言错误。

### 评论
与其猜测 Quipu 的默认摘要生成逻辑，不如显式地控制它。通过在生成的测试 Plan 文件中添加一个 Markdown 标题，我们可以强制 Quipu 使用这个标题作为节点的摘要。这使得在测试中识别 Plan 节点变得微不足道且极其可靠。

### 目标
1.  修改 `create_node` 函数。
2.  在生成的 Plan 文件内容中，添加一个 `# Plan: {content}` 标题。
3.  更新节点识别逻辑：查找提交信息中包含 `Plan: {content}` 的节点。

### 基本原理
Quipu 的 `GitObjectHistoryWriter` 优先使用 Markdown 内容中的第一个标题作为节点摘要。利用这一特性，我们可以精确控制生成的 Plan 节点的元数据，从而在测试中轻松定位它。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/sync #task/object/test-helpers #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 增强 `create_node`，添加显式标题

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
~~~~~python
def create_node(work_dir: Path, content: str) -> str:
    """Helper to create a node and return its commit hash."""
    heads_before = get_local_quipu_heads(work_dir)

    # [FIX] Add an explicit title to the plan to ensure predictable node summary.
    plan_title = f"Plan for {content}"
    plan_file = work_dir / f"{content}.md"
    plan_file.write_text(f"# {plan_title}\n\n~~~~~act\necho '{content}'\n~~~~~")
    
    result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(work_dir), "-y"])
    assert result.exit_code == 0

    heads_after = get_local_quipu_heads(work_dir)
    new_heads = heads_after - heads_before

    if not new_heads:
        raise AssertionError("No new Quipu nodes created.")

    # If only 1 node created, return it.
    if len(new_heads) == 1:
        return new_heads.pop()

    # If 2 nodes created (Capture + Plan), identify the Plan node by checking if
    # the explicit title is present in the commit message.
    for head in new_heads:
        msg = run_git_command(work_dir, ["log", "-1", "--format=%B", head])
        if plan_title in msg:
            return head

    raise AssertionError(
        f"Could not identify Plan node among {len(new_heads)} new heads: {new_heads}"
    )
~~~~~

### 下一步建议
这种方法消除了所有的猜测。现在测试应该非常稳健了。请再次运行测试。一旦确认通过，我们将合并这些改动。
