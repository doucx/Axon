from needle.pointer import L
from unittest.mock import MagicMock

from quipu.cli.main import app
from typer.testing import CliRunner


def test_run_command_with_piped_input_and_confirmation(runner: CliRunner, quipu_workspace, monkeypatch):
    work_dir, _, _ = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.run.bus", mock_bus)
    output_file = work_dir / "output.txt"

    # Plan 内容: 执行一个 shell 命令
    plan_content = f"""
```act
run_command
```
```text
echo "Success" > {output_file.name}
```
"""

    # 在 CI 环境下，click.getchar 无法读取管道输入。
    # 使用 -y (YOLO) 标志绕过交互式确认是集成测试的最佳实践。
    result = runner.invoke(app, ["run", "-w", str(work_dir), "-y"], input=plan_content)

    assert result.exit_code == 0
    mock_bus.success.assert_called_once_with(L.run.success)
    assert output_file.exists(), "The command did not create the output file."
    assert output_file.read_text().strip() == "Success"
