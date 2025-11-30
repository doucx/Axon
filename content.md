好的，我来分析并制定一个计划，为 `quipu log` 命令添加类似 `quipu export` 的筛选功能。

这是一个很好的功能增强，可以显著提高 `quipu log` 命令的实用性，使其在处理大型历史记录时更加高效。

### 用户需求
核心需求是为 `quipu log` 命令增加 `--limit`, `--since`, 和 `--until` 这三个筛选参数，使其行为与 `quipu export` 命令在数据筛选方面保持一致。

### 评论
这是一个重要的功能对齐，可以提升 Quipu CLI 的一致性和用户体验。通过复用现有的筛选逻辑，我们可以用较低的成本实现这个功能。

### 影响分析
1.  **代码修改**:
    *   `packages/quipu-cli/src/pyquipu/cli/commands/query.py`: 这是 `log` 命令的实现文件，需要在这里为其函数签名添加新的 `typer.Option` 参数，并集成筛选逻辑。
    *   `packages/quipu-cli/src/pyquipu/cli/commands/export.py`: 当前的筛选逻辑 (`_filter_nodes` 函数) 在这个文件中。为了复用，最佳实践是将其提取到一个共享的帮助文件中。
    *   `packages/quipu-cli/src/pyquipu/cli/commands/helpers.py`: 这是存放共享帮助函数的理想位置。我们将把 `_filter_nodes` 函数移动到这里。

2.  **测试**:
    *   `tests/cli/test_query_commands.py`: 需要为 `log` 命令添加新的测试用例，以验证筛选功能的正确性，包括：
        *   `--limit` 是否正确限制了输出数量。
        *   `--since` 和 `--until` 是否正确地按时间过滤了节点。
        *   组合使用筛选参数时的行为。
        *   提供无效时间戳时是否能正确报错。

3.  **用户文档 (隐式)**:
    *   由于我们使用 `typer`，命令的 `--help` 输出会自动更新，无需手动修改文档。

### 目标
1.  将 `export.py` 中的 `_filter_nodes` 函数重构并移动到 `helpers.py` 中，使其成为一个可共享的工具函数。
2.  更新 `export.py` 以使用重构后的共享函数。
3.  修改 `query.py` 中的 `log` 命令，为其添加 `--limit`, `--since`, 和 `--until` 参数。
4.  在 `log` 命令中调用共享的筛选函数来处理节点列表。
5.  添加新的单元测试来覆盖 `log` 命令的筛选功能。

### 基本原理
我们将遵循“不要重复自己” (DRY) 的原则。通过将通用的节点筛选逻辑提取到 `helpers.py`，我们不仅可以轻松地将其应用于 `log` 命令，还能为未来可能需要此功能的其他命令提供便利。`log` 命令的修改将遵循 `export` 命令的模式，包括参数定义和错误处理，以确保 CLI 的一致性。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #comp/tests #concept/ui #scope/ux #ai/instruct #task/domain/cli #task/object/log-command #task/action/enhancement #task/state/begin

---

### Script

#### Acts 1: 重构筛选逻辑到共享帮助文件

首先，我们将 `_filter_nodes` 函数从 `export.py` 移动到 `helpers.py`，并更新 `export.py` 的导入。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/helpers.py
~~~~~
~~~~~python
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional

import typer
from pyquipu.common.messaging import bus
from pyquipu.engine.state_machine import Engine
from pyquipu.interfaces.models import QuipuNode

from ..factory import create_engine
from ..logger_config import setup_logging
~~~~~
~~~~~python
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

import typer
from pyquipu.common.messaging import bus
from pyquipu.engine.state_machine import Engine
from pyquipu.interfaces.models import QuipuNode

from ..factory import create_engine
from ..logger_config import setup_logging
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/helpers.py
~~~~~
~~~~~python
def _execute_visit(ctx: typer.Context, engine: Engine, target_hash: str, msg_id: str, **kwargs):
    """辅助函数：执行 engine.visit 并处理结果"""
    bus.info(msg_id, **kwargs)
    try:
        engine.visit(target_hash)
        bus.success("navigation.success.visit", short_hash=target_hash[:7])
    except Exception as e:
        logger.error(f"导航操作失败 (目标哈希: {target_hash[:12]})", exc_info=True)
        bus.error("navigation.error.generic", error=str(e))
        ctx.exit(1)
~~~~~
~~~~~python
def _execute_visit(ctx: typer.Context, engine: Engine, target_hash: str, msg_id: str, **kwargs):
    """辅助函数：执行 engine.visit 并处理结果"""
    bus.info(msg_id, **kwargs)
    try:
        engine.visit(target_hash)
        bus.success("navigation.success.visit", short_hash=target_hash[:7])
    except Exception as e:
        logger.error(f"导航操作失败 (目标哈希: {target_hash[:12]})", exc_info=True)
        bus.error("navigation.error.generic", error=str(e))
        ctx.exit(1)


def filter_nodes(
    nodes: List[QuipuNode], limit: Optional[int], since: Optional[str], until: Optional[str]
) -> List[QuipuNode]:
    """根据时间戳和数量过滤节点列表。"""
    filtered = nodes
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace(" ", "T"))
            filtered = [n for n in filtered if n.timestamp >= since_dt]
        except ValueError:
            raise typer.BadParameter("无效的 'since' 时间戳格式。请使用 'YYYY-MM-DD HH:MM'。")
    if until:
        try:
            until_dt = datetime.fromisoformat(until.replace(" ", "T"))
            filtered = [n for n in filtered if n.timestamp <= until_dt]
        except ValueError:
            raise typer.BadParameter("无效的 'until' 时间戳格式。请使用 'YYYY-MM-DD HH:MM'。")
    if limit is not None and limit > 0:
        # 筛选是在排序后（最新的在前）进行的，所以 limit 是取最新的 N 个
        filtered = filtered[:limit]
    return list(reversed(filtered))
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/export.py
~~~~~
~~~~~python
from ..ui_utils import prompt_for_confirmation
from .helpers import engine_context

logger = logging.getLogger(__name__)
~~~~~
~~~~~python
from ..ui_utils import prompt_for_confirmation
from .helpers import engine_context, filter_nodes

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/export.py
~~~~~
~~~~~python
def _filter_nodes(
    nodes: List[QuipuNode], limit: Optional[int], since: Optional[str], until: Optional[str]
) -> List[QuipuNode]:
    """根据时间戳和数量过滤节点列表。"""
    filtered = nodes
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace(" ", "T"))
            filtered = [n for n in filtered if n.timestamp >= since_dt]
        except ValueError:
            raise typer.BadParameter("无效的 'since' 时间戳格式。请使用 'YYYY-MM-DD HH:MM'。")
    if until:
        try:
            until_dt = datetime.fromisoformat(until.replace(" ", "T"))
            filtered = [n for n in filtered if n.timestamp <= until_dt]
        except ValueError:
            raise typer.BadParameter("无效的 'until' 时间戳格式。请使用 'YYYY-MM-DD HH:MM'。")
    if limit is not None and limit > 0:
        filtered = filtered[:limit]
    return list(reversed(filtered))
~~~~~
~~~~~python
# This function has been moved to helpers.py
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/export.py
~~~~~
~~~~~python
            all_nodes = sorted(engine.history_graph.values(), key=lambda n: n.timestamp, reverse=True)
            try:
                nodes_to_export = _filter_nodes(all_nodes, limit, since, until)
            except typer.BadParameter as e:
                bus.error("export.error.badParam", error=str(e))
                ctx.exit(1)
~~~~~
~~~~~python
            all_nodes = sorted(engine.history_graph.values(), key=lambda n: n.timestamp, reverse=True)
            try:
                # Note: The original list is already sorted newest-first for limit to work correctly.
                # filter_nodes now reverses the final list to get chronological order for export.
                nodes_to_export = filter_nodes(all_nodes, limit, since, until)
            except typer.BadParameter as e:
                bus.error("export.error.badParam", error=str(e))
                ctx.exit(1)
~~~~~

#### Acts 2: 增强 `log` 命令

现在我们将筛选功能添加到 `log` 命令中。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/query.py
~~~~~
~~~~~python
from ..config import DEFAULT_WORK_DIR
from .helpers import engine_context


def _nodes_to_json_str(nodes: List[QuipuNode]) -> str:
~~~~~
~~~~~python
from ..config import DEFAULT_WORK_DIR
from .helpers import engine_context, filter_nodes


def _nodes_to_json_str(nodes: List[QuipuNode]) -> str:
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/query.py
~~~~~
~~~~~python
    def log(
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        json_output: Annotated[bool, typer.Option("--json", help="以 JSON 格式输出结果。")] = False,
    ):
        """
        显示 Quipu 历史图谱日志。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph

            if not graph:
                if json_output:
                    bus.data("[]")
                else:
                    bus.info("query.info.emptyHistory")
                raise typer.Exit(0)

            nodes = sorted(graph.values(), key=lambda n: n.timestamp, reverse=True)

            if json_output:
                bus.data(_nodes_to_json_str(nodes))
                raise typer.Exit(0)

            bus.info("query.log.ui.header")
            for node in nodes:
                ts = node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                tag = f"[{node.node_type.upper()}]"
                summary = node.summary
                # Note: Coloring is a presentation detail handled by renderer, or omitted for data.
                # Here we pass the uncolored data string to the bus.
                data_line = f"{ts} {tag:<9} {node.short_hash} - {summary}"
                bus.data(data_line)
~~~~~
~~~~~python
    def log(
        ctx: typer.Context,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        json_output: Annotated[bool, typer.Option("--json", help="以 JSON 格式输出结果。")] = False,
        limit: Annotated[Optional[int], typer.Option("--limit", "-n", help="限制最新节点数量")] = None,
        since: Annotated[Optional[str], typer.Option("--since", help="起始时间戳 (YYYY-MM-DD HH:MM)")] = None,
        until: Annotated[Optional[str], typer.Option("--until", help="截止时间戳 (YYYY-MM-DD HH:MM)")] = None,
    ):
        """
        显示 Quipu 历史图谱日志。
        """
        with engine_context(work_dir) as engine:
            graph = engine.history_graph

            if not graph:
                if json_output:
                    bus.data("[]")
                else:
                    bus.info("query.info.emptyHistory")
                ctx.exit(0)

            all_nodes = sorted(graph.values(), key=lambda n: n.timestamp, reverse=True)

            try:
                # filter_nodes returns a chronologically reversed list, so we reverse it back for log's newest-first display
                nodes_to_display = list(reversed(filter_nodes(all_nodes, limit, since, until)))
            except typer.BadParameter as e:
                bus.error("export.error.badParam", error=str(e))
                ctx.exit(1)

            if not nodes_to_display:
                if json_output:
                    bus.data("[]")
                else:
                    bus.info("query.info.noResults")
                ctx.exit(0)

            if json_output:
                bus.data(_nodes_to_json_str(nodes_to_display))
                ctx.exit(0)

            bus.info("query.log.ui.header")
            for node in nodes_to_display:
                ts = node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                tag = f"[{node.node_type.upper()}]"
                summary = node.summary
                data_line = f"{ts} {tag:<9} {node.short_hash} - {summary}"
                bus.data(data_line)
~~~~~

#### Acts 3: 添加测试用例

最后，我们为新功能添加专门的测试。

~~~~~act
write_file
tests/cli/test_log_filtering.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
我们已经完成了 `log` 命令的功能增强和测试添加。下一步，我将生成一个 `[COMMIT]` 计划，来将这些修改作为一个完整的逻辑单元提交到版本控制中。
