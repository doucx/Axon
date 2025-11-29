好的，我将执行重构计划的第四阶段：迁移 `cache` 命令的输出逻辑到 `MessageBus`，并更新其测试用例。

这个过程将遵循 “红-绿-重构” 的模式：首先更新测试使其失败（因为旧代码不再符合预期），然后修改业务代码让测试通过，最后确保一切都符合规范。通过 `MessageBus` 的抽象，我们可以在一个计划中同时完成这两步。

## [WIP] refactor: 将 `cache` 命令的输出迁移到 MessageBus

### 用户需求
根据 `MessageBus` 重构计划，需要将 `quipu cache` 子命令 (`sync`, `rebuild`) 的所有用户界面输出从硬编码的 `typer.secho` 调用，迁移到标准化的 `MessageBus` 服务。同时，更新相关的测试用例，使其不再依赖具体的输出字符串，而是验证正确的语义消息是否被调用。

### 评论
这次重构将文件系统交互命令 `cache` 纳入了 `MessageBus` 的统一管理之下。这不仅提升了代码的可维护性和可测试性，也为后续可能的国际化做好了准备。同时，更新测试用例是确保此次重构正确性的关键步骤。

### 目标
1.  在 `locales/zh/cli.json` 中添加 `cache` 命令所需的所有消息模板。
2.  修改 `packages/quipu-cli/src/quipu/cli/commands/cache.py`，用 `bus` 调用替换所有 `typer.secho` 调用。
3.  重写 `tests/cli/test_cache_commands.py`，使用 `unittest.mock` 注入一个 `mock_bus`，并断言其方法调用，而不是检查 `stderr` 的字符串内容。

### 基本原理
我们采用“分层”的重构策略。首先，在 `locales` 资源层定义好所有需要的消息。然后，在 `cli` 命令的实现层，将表示逻辑 (`typer.secho`) 替换为语义调用 (`bus.info`, `bus.success` 等)。最后，在测试层，我们利用 `monkeypatch` 将 `bus` 实例替换为一个 `MagicMock` 对象，从而将测试的关注点从脆弱的 UI 文本转移到稳定的业务意图上。

### 标签
#intent/refine #flow/ready #priority/medium #comp/cli #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/message-bus #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 定义消息模板

首先，我们在 `locales/zh/cli.json` 中为 `cache` 命令定义所有需要的消息。

```````act
patch_file
locales/zh/cli.json
```````
```````json
  "show.error.fileNotInNode": "❌ 错误: 在节点内未找到文件 '{filename}'。",
  "show.info.availableFiles": "可用文件: {file_list}"
}",
  "common.prompt.cancel": "\n🚫 操作已取消。",
  "workspace.save.success": "📸 快照已保存: {short_hash}{msg_suffix}",
  "workspace.save.noChanges": "✅ 工作区状态未发生变化，无需创建快照。",
```````
```````json
  "show.error.fileNotInNode": "❌ 错误: 在节点内未找到文件 '{filename}'。",
  "show.info.availableFiles": "可用文件: {file_list}"
}",
  "common.prompt.cancel": "\n🚫 操作已取消。",
  "cache.sync.info.hydrating": "💧 正在执行增量数据补水...",
  "cache.sync.success": "✅ 数据同步完成。",
  "cache.sync.error": "❌ 数据同步失败: {error}",
  "cache.rebuild.info.dbNotFound": "🤷 数据库文件不存在，将直接创建。无需重建。",
  "cache.rebuild.info.deleting": "🗑️  旧数据库已删除。",
  "cache.rebuild.error.deleteFailed": "❌ 删除旧数据库失败: {error}",
  "workspace.save.success": "📸 快照已保存: {short_hash}{msg_suffix}",
  "workspace.save.noChanges": "✅ 工作区状态未发生变化，无需创建快照。",
```````

#### Acts 2: 重构 `cache.py` 命令实现

现在，我们修改 `cache.py` 文件，引入 `MessageBus` 并替换掉所有的 `typer.secho` 调用。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/cache.py
```````
```````python
import typer

from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..ui_utils import prompt_for_confirmation
```````
```````python
import typer

from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..ui_utils import prompt_for_confirmation
from quipu.common.messaging import bus
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/cache.py
```````
```````python
    """
    将 Git 历史增量同步到 SQLite 缓存。
    """
    typer.secho("💧 正在执行增量数据补水...", fg=typer.colors.BLUE, err=True)
    try:
        with engine_context(work_dir):
            pass
        typer.secho("✅ 数据同步完成。", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        logger.error("数据同步失败", exc_info=True)
        typer.secho(f"❌ 数据同步失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)
```````
```````python
    """
    将 Git 历史增量同步到 SQLite 缓存。
    """
    bus.info("cache.sync.info.hydrating")
    try:
        with engine_context(work_dir):
            pass
        bus.success("cache.sync.success")
    except Exception as e:
        logger.error("数据同步失败", exc_info=True)
        bus.error("cache.sync.error", error=str(e))
        ctx.exit(1)
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/cache.py
```````
```````python
    """
    强制全量重建 SQLite 缓存。
    """
    setup_logging()
    db_path = work_dir.resolve() / ".quipu" / "history.sqlite"
    if not db_path.exists():
        typer.secho("🤷 数据库文件不存在，将直接创建。无需重建。", fg=typer.colors.YELLOW, err=True)
        cache_sync(ctx, work_dir)
        return

    if not force:
        prompt = f"🚨 即将删除并重建数据库 {db_path}。\n此操作不可逆。是否继续？"
        if not prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    try:
        db_path.unlink()
        typer.secho("🗑️  旧数据库已删除。", err=True)
    except (OSError, PermissionError) as e:
        logger.error(f"删除旧数据库文件 '{db_path}' 失败", exc_info=True)
        typer.secho(f"❌ 删除旧数据库失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)

    cache_sync(ctx, work_dir)
```````
```````python
    """
    强制全量重建 SQLite 缓存。
    """
    setup_logging()
    db_path = work_dir.resolve() / ".quipu" / "history.sqlite"
    if not db_path.exists():
        bus.warning("cache.rebuild.info.dbNotFound")
        cache_sync(ctx, work_dir)
        return

    if not force:
        prompt = f"🚨 即将删除并重建数据库 {db_path}。\n此操作不可逆。是否继续？"
        if not prompt_for_confirmation(prompt, default=False):
            bus.warning("common.prompt.cancel")
            raise typer.Abort()

    try:
        db_path.unlink()
        bus.info("cache.rebuild.info.deleting")
    except (OSError, PermissionError) as e:
        logger.error(f"删除旧数据库文件 '{db_path}' 失败", exc_info=True)
        bus.error("cache.rebuild.error.deleteFailed", error=str(e))
        ctx.exit(1)

    cache_sync(ctx, work_dir)
```````

#### Acts 3: 重构测试用例

最后，我们重写 `test_cache_commands.py`，使其与 UI 实现解耦，专注于测试业务逻辑是否调用了正确的语义消息。

```````act
write_file
tests/cli/test_cache_commands.py
```````
```````python
from unittest.mock import MagicMock
from quipu.cli.main import app


def test_cache_sync(runner, quipu_workspace, monkeypatch):
    work_dir, _, _ = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.cache.bus", mock_bus)

    result = runner.invoke(app, ["cache", "sync", "-w", str(work_dir)])

    assert result.exit_code == 0
    mock_bus.info.assert_called_once_with("cache.sync.info.hydrating")
    mock_bus.success.assert_called_once_with("cache.sync.success")


def test_cache_rebuild_no_db(runner, quipu_workspace, monkeypatch):
    work_dir, _, _ = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.cache.bus", mock_bus)

    result = runner.invoke(app, ["cache", "rebuild", "-w", str(work_dir)])

    assert result.exit_code == 0
    mock_bus.warning.assert_called_once_with("cache.rebuild.info.dbNotFound")
    mock_bus.info.assert_called_once_with("cache.sync.info.hydrating")
    mock_bus.success.assert_called_once_with("cache.sync.success")
```````

### 下一步建议
我们已经成功地将 `cache` 命令迁移到了 `MessageBus` 架构下。接下来的逻辑步骤是处理下一个交互更复杂的命令模块：**核心导航命令 (`navigation`)**。这包括 `checkout`、`undo`、`redo` 等，它们包含了更多的用户交互和状态反馈，是 `MessageBus` 应用的绝佳场景。
