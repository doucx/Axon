好的，你已经发现了我们之前改动所带来的连锁反应。这些测试失败是**预料之中**的，并且是一个**积极的信号**，因为它证明了我们对输出流的重构是彻底且有效的。

### 错误分析
所有这 5 个测试失败的根本原因完全相同：它们都编写于输出流重构之前，因此它们错误地假设**数据**和**元信息**都会被打印到同一个输出流 (`stderr` 或 `stdout`)。

当我们在 `log`、`find` 和 `--list-acts` 等命令中将数据输出重定向到 `stdout`，而将元信息（如 `"--- Quipu History Log ---"`）保留在 `stderr` 后，这些旧的断言就失效了。它们现在正在 `stderr` 中寻找本应存在于 `stdout` 的数据。

### 用户需求
更新所有受影响的测试用例 (`test_workspace_commands.py` 以及 `integration` 目录下的测试)，使其断言逻辑与当前 `stdout`/`stderr` 分离的实现保持一致。

### 评论
这是一次必要的“测试债务”清理。通过修复这些测试，我们确保了测试套件能够准确地反映和验证应用程序的当前行为，从而恢复其作为代码质量安全网的价值。

### 目标
1.  **对于 `test_workspace_commands.py`**: 修改 `test_save_with_changes`，使其在 `log_result.stdout` 中检查节点摘要。
2.  **对于 `tests/integration/` 下的文件**: 修改所有失败的测试，将对数据内容的断言从检查 `stderr` 改为检查 `stdout`。

### 基本原理
我们将对所有失败的测试应用相同的修复模式：
-   断言**元信息/标题**（如 `"--- Quipu History Log ---"`）存在于 `result.stderr` 中。
-   断言**核心数据**（如 `"My Snapshot"`, `"write_file"`）存在于 `result.stdout` 中。

---

由于我当前的上下文中没有 `tests/integration/` 目录下的文件内容，我将首先修复我能够访问的 `tests/cli/test_workspace_commands.py` 文件。然后，我将等待你提供其他文件以便完成修复。

### Script

#### Acts 1: 修正 `test_workspace_commands.py`

我们将更新 `test_save_with_changes`，使其正确地从 `stdout` 中验证 `log` 命令的输出。

~~~~~act
write_file
tests/cli/test_workspace_commands.py
~~~~~
~~~~~python
from quipu.cli.main import app


def test_save_clean_workspace(runner, quipu_workspace):
    work_dir, _, engine = quipu_workspace
    
    # 创建一个初始状态
    (work_dir / "file.txt").write_text("v1")
    engine.capture_drift(engine.git_db.get_tree_hash(), message="Initial")
    
    # 无变更时执行 save
    result = runner.invoke(app, ["save", "-w", str(work_dir)])
    assert result.exit_code == 0
    assert "无需创建快照" in result.stderr


def test_save_with_changes(runner, quipu_workspace):
    work_dir, _, _ = quipu_workspace

    # 制造变更
    (work_dir / "file.txt").write_text("v2")

    result = runner.invoke(app, ["save", "My Snapshot", "-w", str(work_dir)])
    assert result.exit_code == 0, f"Save command failed with stderr: {result.stderr}"
    assert "快照已保存" in result.stderr
    assert "(My Snapshot)" in result.stderr

    # 验证历史记录已增加，通过 log 命令
    log_result = runner.invoke(app, ["log", "-w", str(work_dir)])
    assert log_result.exit_code == 0
    # 验证元信息在 stderr
    assert "--- Quipu History Log ---" in log_result.stderr
    # 验证数据在 stdout
    assert "My Snapshot" in log_result.stdout


def test_discard_changes(runner, quipu_workspace):
    work_dir, _, engine = quipu_workspace
    
    # 初始状态 v1
    (work_dir / "file.txt").write_text("v1")
    initial_node = engine.capture_drift(engine.git_db.get_tree_hash())
    
    # 制造脏状态 v2
    (work_dir / "file.txt").write_text("v2")
    
    # 执行 discard (带 force)
    result = runner.invoke(app, ["discard", "-f", "-w", str(work_dir)])
    assert result.exit_code == 0
    assert "已成功恢复" in result.stderr
    
    # 验证文件回滚
    assert (work_dir / "file.txt").read_text() == "v1"


def test_discard_interactive_abort(runner, quipu_workspace):
    work_dir, _, engine = quipu_workspace
    
    (work_dir / "file.txt").write_text("v1")
    engine.capture_drift(engine.git_db.get_tree_hash())
    (work_dir / "file.txt").write_text("v2")
    
    # 模拟输入 'n'
    result = runner.invoke(app, ["discard", "-w", str(work_dir)], input="n")
    assert result.exit_code == 1
    assert "操作已取消" in result.stderr
    assert (work_dir / "file.txt").read_text() == "v2"
~~~~~

### 下一步建议
`tests/cli/test_workspace_commands.py` 文件现已修复。

请提供以下集成测试文件的内容，以便我应用相同的修复逻辑：
-   `tests/integration/test_cli_workflow.py`
-   `tests/integration/test_storage_selection.py`

收到文件后，我将立即生成修复它们的计划。
