好的，我们将修改集成测试 `test_workspace_commands.py` 中的 `test_discard_interactive_abort` 用例，使用 `monkeypatch` 模拟 `click.getchar` 的字符按键返回值，彻底避免测试在终端中卡死。

## [WIP] fix(cli): 修复 test_discard_interactive_abort 在交互式终端下的挂起测试问题

### 错误分析

1. **终端字符设备阻塞**：`prompt_for_confirmation` 内部使用了 `click.getchar()` 来捕获交互键盘按键。在 Unix 系统上，`click.getchar()` 会优先从物理字符设备 `/dev/tty` 读取字符。
2. **`CliRunner` 模拟局限**：`CliRunner(..., input="n")` 仅充当了 `sys.stdin` 的虚拟重定向管道，无法拦截直接针对 `/dev/tty` 的低级 I/O 读取。当测试在终端环境执行（如 `qtest`）时，`click.getchar()` 绕过了 `CliRunner` 的模拟管道，直接阻塞等待真正的键盘按键，导致测试程序挂起。按下 `Ctrl+C` 后引发 `SystemExit(130)`，测试因返回值断言不符而失败。

### 用户需求
使 `test_discard_interactive_abort` 测试用例能够非阻塞地在各种测试环境（特别是带终端支持的 `qtest` 环境）中稳定快速执行。

### 评论
这是一个提升测试可靠性与开发者体验 (DX) 的修补。通过在单元测试层接管按键函数，确保测试套件完全自动化，不受交互式硬件设备的影响。

### 目标
1. 修改 `test_workspace_commands.py` 中的 `test_discard_interactive_abort` 测试函数。
2. 使用 `monkeypatch.setattr("click.getchar", lambda echo=False: "n")` 模拟按键逻辑。
3. 移除 `CliRunner.invoke` 中的 `input="n"` 参数。

### 基本原理
通过 `monkeypatch` 直接拦截 `click.getchar` 函数调用，使其在被触发时直接返回 `"n"`，既模拟了用户拒绝操作的交互行为，又彻底避免了与真实的 `/dev/tty` 发生阻塞交互。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/testing #task/object/workspace-commands-test #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修改 test_discard_interactive_abort 测试用例

~~~~~act
patch_file
packages/pyquipu-cli/tests/integration/test_workspace_commands.py
~~~~~
~~~~~python.old
def test_discard_interactive_abort(runner, quipu_workspace, monkeypatch):
    work_dir, _, engine = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.workspace.bus", mock_bus)

    (work_dir / "file.txt").write_text("v1")
    engine.capture_drift(engine.git_db.get_tree_hash())
    (work_dir / "file.txt").write_text("v2")

    result = runner.invoke(app, ["discard", "-w", str(work_dir)], input="n")

    assert result.exit_code == 1
    mock_bus.warning.assert_called_once_with(L.common.prompt.cancel)
    assert (work_dir / "file.txt").read_text() == "v2"
~~~~~
~~~~~python.new
def test_discard_interactive_abort(runner, quipu_workspace, monkeypatch):
    work_dir, _, engine = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.workspace.bus", mock_bus)
    monkeypatch.setattr("click.getchar", lambda echo=False: "n")

    (work_dir / "file.txt").write_text("v1")
    engine.capture_drift(engine.git_db.get_tree_hash())
    (work_dir / "file.txt").write_text("v2")

    result = runner.invoke(app, ["discard", "-w", str(work_dir)])

    assert result.exit_code == 1
    mock_bus.warning.assert_called_once_with(L.common.prompt.cancel)
    assert (work_dir / "file.txt").read_text() == "v2"
~~~~~

### 下一步建议
1. 执行本 Plan 以更新测试文件。
2. 重新在终端执行 `qtest packages/pyquipu-cli/tests/integration/test_workspace_commands.py` 验证修复结果。
