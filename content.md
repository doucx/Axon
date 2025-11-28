## fix 修复测试用例，使其适应新的模块化命令结构。

好的，我来修复这个测试失败。

### 错误分析
测试 `test_cli_no_input_shows_usage` 在 `tests/integration/test_cli_workflow.py` 中失败，原因是 `AttributeError`。该测试试图使用 `monkeypatch` 修改 `quipu.cli.main` 模块中的 `DEFAULT_ENTRY_FILE` 变量。

在我刚才执行的重构中，`run` 命令的逻辑及其对 `DEFAULT_ENTRY_FILE` 的使用，已经从 `main.py` 移至 `quipu/cli/commands/run.py`。因此，`main.py` 模块中不再存在这个属性，导致测试失败。

### 用户需求
修复测试用例，使其适应新的模块化命令结构。

### 评论
这是一个典型的重构后遗症。测试代码与实现代码紧密耦合，当实现发生变化时，测试也必须相应更新。修复这个问题很简单，只需要将 `monkeypatch` 的目标从旧的 `main` 模块改为新的 `run` 模块即可。

### 目标
修改 `tests/integration/test_cli_workflow.py` 中的 `test_cli_no_input_shows_usage` 函数，将 `monkeypatch.setattr` 的目标更正为 `quipu.cli.commands.run` 模块。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/ui #task/object/refactor #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正测试用例

我们将 `patch_file` 直接应用于出错的测试文件，定位到具体的函数并进行修正。

~~~~~act
patch_file
tests/integration/test_cli_workflow.py
~~~~~
~~~~~python
    def test_cli_no_input_shows_usage(self, monkeypatch, tmp_path):
        """测试无输入时显示用法"""
        # 1. 临时修改 main 模块中的默认入口文件引用，防止读取当前目录下的 o.md
        # 注意：必须 patch 'main' 模块，而不是 'config' 模块，因为 main 采用了 from import
        from quipu.cli import main

        monkeypatch.setattr(main, "DEFAULT_ENTRY_FILE", tmp_path / "non_existent.md")

        # 2. 同时确保 STDIN 不是 TTY，也不是管道（模拟纯交互式空运行）
        # CliRunner 默认就是这种状态，但为了保险起见，我们什么都不输入

        result = runner.invoke(app, ["run"])  # 无参数，无管道

        assert result.exit_code == 0
        assert "用法示例" in result.stderr
~~~~~
~~~~~python
    def test_cli_no_input_shows_usage(self, monkeypatch, tmp_path):
        """测试无输入时显示用法"""
        # 1. 临时修改 run 命令模块中的默认入口文件引用，防止读取当前目录下的 o.md
        # 注意：必须 patch 'run' 模块，因为该模块通过 'from ... import' 引入了常量
        from quipu.cli.commands import run

        monkeypatch.setattr(run, "DEFAULT_ENTRY_FILE", tmp_path / "non_existent.md")

        # 2. 同时确保 STDIN 不是 TTY，也不是管道（模拟纯交互式空运行）
        result = runner.invoke(app, ["run"])  # 无参数，无管道

        assert result.exit_code == 0
        assert "用法示例" in result.stderr
~~~~~

### 下一步建议
测试用例已修复。现在可以重新运行测试套件，以确保所有测试都能通过。
