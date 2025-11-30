import time
from unittest.mock import MagicMock

from pyquipu.cli.main import app
from tests.helpers import EMPTY_TREE_HASH, create_plan_node_with_change


def test_log_with_limit(runner, engine_instance, monkeypatch):
    """验证 --limit 参数是否生效。"""
    mock_bus = MagicMock()
    monkeypatch.setattr("pyquipu.cli.commands.query.bus", mock_bus)
    work_dir = engine_instance.root_dir

    # 创建 3 个节点
    h1 = create_plan_node_with_change(engine_instance, EMPTY_TREE_HASH, "f1.txt", "v1", "Node 1")
    time.sleep(0.01)
    h2 = create_plan_node_with_change(engine_instance, h1, "f2.txt", "v2", "Node 2")
    time.sleep(0.01)
    create_plan_node_with_change(engine_instance, h2, "f3.txt", "v3", "Node 3")

    result = runner.invoke(app, ["log", "-w", str(work_dir), "--limit", "2"])
    assert result.exit_code == 0
    assert "Node 3" in result.stdout
    assert "Node 2" in result.stdout
    assert "Node 1" not in result.stdout
    mock_bus.info.assert_called_with("query.log.ui.header")


def test_log_with_since(runner, engine_instance, monkeypatch):
    """验证 --since 参数是否生效。"""
    mock_bus = MagicMock()
    monkeypatch.setattr("pyquipu.cli.commands.query.bus", mock_bus)
    work_dir = engine_instance.root_dir

    h1 = create_plan_node_with_change(engine_instance, EMPTY_TREE_HASH, "f1.txt", "v1", "Node 1")
    time.sleep(0.02)
    cutoff_time = time.time()
    time.sleep(0.02)
    h2 = create_plan_node_with_change(engine_instance, h1, "f2.txt", "v2", "Node 2")
    create_plan_node_with_change(engine_instance, h2, "f3.txt", "v3", "Node 3")

    from datetime import datetime

    since_str = datetime.fromtimestamp(cutoff_time).strftime("%Y-%m-%d %H:%M:%S")
    result = runner.invoke(app, ["log", "-w", str(work_dir), "--since", since_str])

    assert result.exit_code == 0
    assert "Node 3" in result.stdout
    assert "Node 2" in result.stdout
    assert "Node 1" not in result.stdout


def test_log_no_results(runner, engine_instance, monkeypatch):
    """验证没有匹配项时是否正确提示。"""
    mock_bus = MagicMock()
    monkeypatch.setattr("pyquipu.cli.commands.query.bus", mock_bus)
    work_dir = engine_instance.root_dir
    create_plan_node_with_change(engine_instance, EMPTY_TREE_HASH, "f1.txt", "v1", "Node 1")

    result = runner.invoke(app, ["log", "-w", str(work_dir), "--limit", "0"])

    assert result.exit_code == 0
    assert result.stdout == ""
    mock_bus.info.assert_called_with("query.info.noResults")


def test_log_bad_date_format(runner, git_workspace, monkeypatch):
    """验证无效的日期格式是否会报错。"""
    mock_bus = MagicMock()
    monkeypatch.setattr("pyquipu.cli.commands.query.bus", mock_bus)

    result = runner.invoke(app, ["log", "-w", str(git_workspace), "--since", "not-a-date"])

    assert result.exit_code == 1
    mock_bus.error.assert_called_once()
    args, kwargs = mock_bus.error.call_args
    assert args[0] == "export.error.badParam"
    assert "无效的 'since' 时间戳格式" in kwargs["error"]