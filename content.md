这是一个**非常好的信号**！

这 9 个新失败的用例证明：我们的 **`raw` 语言模式已经在你的本地测试环境中完美生效了**。之前因为本地输出了中文（例如“快照已保存”）而侥幸通过的断言，现在全部统一输出成了稳定的 Key 标识符（例如 `workspace.save.success`），从而在本地暴露了出来。

这正是我们追求的**高一致性状态**：本地和远端 CI 现在都在完全相同的 `raw` 模式下运行。我们现在只需要将这最后 9 个硬编码的中文断言替换为它们对应的 Key 标识符即可。

我将生成一个计划来执行此操作：
1.  **直接修改 `test_cli_workflow.py`**（内容已在上下文中）。
2.  **读取并分析 `test_storage_selection.py` 和 `test_sync_modes.py`** 的内容，以便在下一轮中精确替换它们。

## [WIP] fix(tests): 统一剩余集成测试的 I18N 断言为 Key 标识符

### 用户需求

将剩余测试用例中硬编码的中文翻译文本替换为对应的原始 Key，以适配全局 `raw` 测试语言模式。

### 目标

1.  修改 `test_cli_workflow.py` 中的 `test_cli_list_acts` 断言。
2.  读取 `test_storage_selection.py` 和 `test_sync_modes.py` 的内容，定位并替换硬编码的中文。

### 标签
#intent/refine #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/i18n-raw-mode #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 `test_cli_workflow.py` 中的 `list-acts` 断言

在 `raw` 模式下，由于不加载翻译模板，`name` 参数（即 `"write_file"`）不会被格式化进最终的字符串中，而是直接输出未填充的 Key 标识符 `run.listActs.ui.actItem`。我们将断言修改为匹配该 Key。

~~~~~act
patch_file
tests/integration/test_cli_workflow.py
~~~~~
~~~~~python.old
    def test_cli_list_acts(self):
        """测试 --list-acts"""
        # --list-acts 是 'run' 命令的一个选项
        result = runner.invoke(app, ["run", "--list-acts"])
        assert result.exit_code == 0
        assert "run.listActs.ui.header" in result.stderr
        assert "write_file" in result.stdout
~~~~~
~~~~~python.new
    def test_cli_list_acts(self):
        """测试 --list-acts"""
        # --list-acts 是 'run' 命令的一个选项
        result = runner.invoke(app, ["run", "--list-acts"])
        assert result.exit_code == 0
        assert "run.listActs.ui.header" in result.stderr
        # 在 raw 模式下，输出将是原始的 Key 标识符
        assert "run.listActs.ui.actItem" in result.stdout
~~~~~

#### Acts 2: 读取剩余失败测试文件进行分析

我们需要读取这两个文件的内容，以便下一轮进行精确的代码替换。

~~~~~act
read_file
tests/integration/test_storage_selection.py
~~~~~

~~~~~act
read_file
tests/integration/test_sync_modes.py
~~~~~

### 下一步建议

收到你确认这两个文件的内容后，我将立刻生成精确的 `patch_file` 指令，彻底消灭这最后的 8 个失败断言，让本地与远端 CI 的测试状态全部回归全绿（100% Pass）。
