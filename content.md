根据你的分析，CI 环境下的失败主要源于：
1.  **断言冲突**：测试代码期望渲染后的中文，但 Mock Bus 返回的是消息 Key。
2.  **TTY 缺失**：`click.getchar()` 在非交互式环境下抛出异常，导致逻辑默认返回 `False` 并取消操作。

我将按照你的要求实施以下修改：
1.  **修复 `test_cli_interaction.py`**：将 `quipu run` 切换为使用 `-y` (YOLO) 标志，以绕过 CI 环境下的交互确认。
2.  **标准化断言**：对于你能提供的文件，确保断言使用的是 `L` 指针或 Key 字符串，而不是硬编码的中文。

## [WIP] fix(tests): 解决 CI 环境下的交互与断言冲突

### 错误分析

1.  **`test_run_command_with_piped_input_and_confirmation` 失败**：
    *   **原因**：该测试试图通过 `input` 管道模拟用户输入 `y\n`。然而，`ui_utils.py` 中的 `prompt_for_confirmation` 使用了 `click.getchar()`。在 GitHub Actions 环境中，没有 TTY 设备，`getchar()` 会抛出 `EOFError`。
    *   **后果**：代码捕获该异常并为了安全返回 `False`，导致操作被取消（Exit Code 2），断言 `exit_code == 0` 失败。
    
2.  **I18N 字符串匹配失败**：
    *   **原因**：测试中使用了 `assert "用法示例" in result.stderr` 这种硬编码断言。但在运行测试时，`mock_runtime_bus` 被激活，它会将 `L.run.info.usageHint` 这种指针直接转换为字符串 `run.info.usageHint` 返回。
    *   **后果**：渲染后的中文不再出现在输出中，导致字符串匹配断言失败。

### 用户需求

1.  修改测试断言，使其与 I18N 消息总线的 Mock 行为兼容。
2.  在集成测试中采用 `--yolo` 标志（方法 A），避免 TTY 依赖。

### 评论
使用 `--yolo` 是集成测试中最稳健的方法，因为它不仅解决了 CI 兼容性问题，还减少了对管道输入顺序的脆弱依赖。

### 目标

1.  在 `test_cli_interaction.py` 中移除管道输入 `y\n`，改用 `-y` 命令行参数。
2.  更新断言逻辑（由于提供的上下文文件中大部分已使用 `L` 或 Key，我们将重点确保 `test_cli_interaction.py` 的稳定性）。

### 基本原理
通过在命令行中显式声明 `-y`，`QuipuApplication` 会将 `yolo` 参数传递给 `Executor`，从而在执行 `Act` 时完全跳过 `request_confirmation` 逻辑，绕过对 `click.getchar()` 的调用。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/ci-compatibility #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 `test_cli_interaction.py` 中的交互逻辑

我们将移除手动模拟的 `user_input`，并在命令中添加 `-y` 标志。

~~~~~act
patch_file
packages/pyquipu-cli/tests/integration/test_cli_interaction.py
~~~~~
~~~~~python.old
    # 模拟用户输入 'y' 并按回车
    user_input = "y\n"

    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content + user_input)

    assert result.exit_code == 0
~~~~~
~~~~~python.new
    # 在 CI 环境下，click.getchar 无法读取管道输入。
    # 使用 -y (YOLO) 标志绕过交互式确认是集成测试的最佳实践。
    result = runner.invoke(app, ["run", "-w", str(work_dir), "-y"], input=plan_content)

    assert result.exit_code == 0
~~~~~

### 下一步建议

1.  **手动修复未包含的文件**：由于 `test_cli_workflow.py` 和 `test_sync_workflow.py` 不在当前上下文提供的文件列表中，你需要手动打开它们，将断言中的中文（如 `"用法示例"`、`"⬇️  正在拉取..."`）替换为对应的 Key 或 `L` 指针字符串（如 `"run.info.usageHint"`、`"sync.run.info.pulling"`）。
2.  **检查 `quipu sync` 测试**：确保在 `sync` 命令的集成测试中也使用了可绕过交互的参数（如果存在），或者通过 `monkeypatch` 模拟确认函数返回 `True`。
3.  **运行沙盒验证**：执行 `python3 verify_sandbox.py` 确保核心逻辑在模拟真实环境下依然保持正常。
