好的，我们继续执行重构计划。现在进入第六阶段，处理核心的执行命令 `run` 和 `axon`。这两个命令是 `Quipu` 的主要入口，统一它们的输出行为对于提供一致的用户体验至关重要。

为了实现彻底的解耦，我将对 `QuipuResult` 接口进行一次小的、内部兼容的扩展，使其能够携带结构化的消息数据，而不仅仅是预格式化的字符串。

## [WIP] refactor: 将 `run` 和 `axon` 命令的输出迁移到 MessageBus

### 用户需求
根据 `MessageBus` 重构计划，需要将 `quipu run` 和 `quipu axon` 命令的所有用户界面输出从硬编码的 `typer.secho/echo` 调用迁移到标准化的 `MessageBus` 服务。这包括命令执行过程中的错误、警告、成功信息以及 `--list-acts` 的输出。同时，需要更新相关的测试用例，使其验证语义消息调用，而不是具体的输出字符串。

### 评论
这次重构触及了 `Quipu` 的核心工作流。通过将 `run` 和 `axon` 命令的输出逻辑迁移到 `MessageBus`，我们不仅统一了 UI，还改进了 `controller` 和 `cli` 之间的通信契约，使其更加清晰和健壮。更新交互式测试用例将是确保此次重构成功的关键，特别是对于用户取消操作等不友好路径的验证。

### 目标
1.  在 `locales/zh/cli.json` 中添加 `run` 和 `axon` 命令所需的所有消息模板。
2.  扩展 `quipu.interfaces.result.QuipuResult` 数据类，增加一个 `msg_kwargs` 字段以传递结构化数据。
3.  重构 `quipu.cli.controller.run_quipu` 函数，使其返回的 `QuipuResult` 中包含消息 ID (`message`) 和消息参数 (`msg_kwargs`)。
4.  重构 `quipu.cli.commands.run.py` 和 `axon.py`，用 `bus` 调用替换所有 `typer` 输出。
5.  重构 `tests/cli/test_cli_interaction.py` 和 `tests/cli/test_unfriendly_paths.py`，使用 `mock` 来验证 `bus` 的调用。

### 基本原理
我们将首先扩展核心接口 `QuipuResult`，使其能够携带除消息 ID 之外的动态参数。然后，我们修改 `controller` 层的 `run_quipu` 函数，让它利用这个新接口返回结构化的结果。接着，在 `cli` 层的 `run.py` 和 `axon.py` 中，我们将所有硬编码的 `typer` 调用替换为对 `MessageBus` 的语义调用。最后，我们重写受影响的测试用例，用对 `mock_bus` 的断言替换掉对 `stderr` 字符串的脆弱断言，从而完成整个重构闭环。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/runtime #comp/interfaces #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/cli #task/object/message-bus #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 扩展核心接口 `QuipuResult`

我们在 `quipu-interfaces` 包中为 `QuipuResult` 添加一个新字段，用于传递消息模板的参数。

```````act
patch_file
packages/quipu-interfaces/src/quipu/interfaces/result.py
```````
```````python
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class QuipuResult:
    """
    Quipu 业务逻辑执行结果的标准容器。
    用于在 Controller 和 Shell 之间传递状态，避免直接抛出 SystemExit。
    """

    success: bool
    exit_code: int
    message: str = ""
    data: Any = None
    error: Optional[Exception] = None
```````
```````python
from dataclasses import dataclass, field
from typing import Optional, Any, Dict


@dataclass
class QuipuResult:
    """
    Quipu 业务逻辑执行结果的标准容器。
    用于在 Controller 和 Shell 之间传递状态，避免直接抛出 SystemExit。
    """

    success: bool
    exit_code: int
    message: str = ""  # Will hold the message ID for the bus
    data: Any = None
    error: Optional[Exception] = None
    msg_kwargs: Dict[str, Any] = field(default_factory=dict)
```````

#### Acts 2: 定义 `run` 和 `axon` 的消息模板

我们在 `locales/zh/cli.json` 中添加所有需要的消息。

```````act
patch_file
locales/zh/cli.json
```````
```````json
  "navigation.forward.atEnd": "⚠️  已到达访问历史的终点。",
  "navigation.forward.error": "❌ 前进操作失败: {error}",
  "workspace.save.success": "📸 快照已保存: {short_hash}{msg_suffix}",
  "workspace.save.noChanges": "✅ 工作区状态未发生变化，无需创建快照。",
  "workspace.save.error": "❌ 创建快照失败: {error}",
```````
```````json
  "navigation.forward.atEnd": "⚠️  已到达访问历史的终点。",
  "navigation.forward.error": "❌ 前进操作失败: {error}",
  "run.success": "✨ 执行成功",
  "run.error.cancelled": "🚫 操作已取消: {error}",
  "run.error.execution": "❌ 操作失败: {error}",
  "run.error.system": "系统错误: {error}",
  "run.warning.noInput": "⚠️  提示: 未提供输入，且当前目录下未找到默认文件 '{filename}'。",
  "run.info.usageHint": "\n用法示例:\n  quipu run my_plan.md\n  echo '...' | quipu run",
  "run.error.ambiguousCommand": "💡 提示: 你是不是想执行 'quipu {command}' 命令？",
  "run.listActs.ui.header": "\n📋 可用的 Quipu 指令列表:\n",
  "run.listActs.ui.actItem": "🔹 {name}",
  "run.result.message": "\n{message}",
  "axon.success": "\n✨ Axon 执行完成。",
  "axon.info.starting": "Axon 启动 | 源: {source} | 工作区: {work_dir}",
  "axon.warning.noInput": "⚠️  提示: 未提供输入 (文件或管道)，且未找到默认文件。",
  "axon.warning.noStatements": "⚠️  未解析到任何有效指令 (Parser: {parser})。",
  "axon.error.executionFailed": "\n❌ 执行失败: {error}",
  "axon.listActs.ui.header": "\n📋 可用的 Axon 指令列表:\n",
  "axon.listActs.ui.actItem": "🔹 {name}",
  "workspace.save.success": "📸 快照已保存: {short_hash}{msg_suffix}",
  "workspace.save.noChanges": "✅ 工作区状态未发生变化，无需创建快照。",
  "workspace.save.error": "❌ 创建快照失败: {error}",
```````

#### Acts 3: 重构 `controller.py`

现在，我们更新 `run_quipu` 函数，使其返回结构化的 `QuipuResult`。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/controller.py
```````
```````python
        if not statements:
            return QuipuResult(
                success=False,
                exit_code=0,
                message=f"⚠️  使用 '{final_parser_name}' 解析器未找到任何有效的 'act' 操作块。",
            )

        # 3.2 Executor Setup
        executor = self._setup_executor()
```````
```````python
        if not statements:
            return QuipuResult(
                success=True,  # No failure, just nothing to do
                exit_code=0,
                message="axon.warning.noStatements",
                msg_kwargs={"parser": final_parser_name},
            )

        # 3.2 Executor Setup
        executor = self._setup_executor()
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/controller.py
```````
```````python
            summary_override=final_summary,
        )

        return QuipuResult(success=True, exit_code=0, message="✨ 执行成功")
```````
```````python
            summary_override=final_summary,
        )

        return QuipuResult(success=True, exit_code=0, message="run.success")
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/controller.py
```````
```````python
    except OperationCancelledError as e:
        logger.info(f"🚫 操作已取消: {e}")
        return QuipuResult(success=False, exit_code=2, message=f"🚫 操作已取消: {e}", error=e)

    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(success=False, exit_code=1, message=str(e), error=e)

    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(success=False, exit_code=1, message=f"系统错误: {e}", error=e)
    finally:
```````
```````python
    except OperationCancelledError as e:
        logger.info(f"🚫 操作已取消: {e}")
        return QuipuResult(success=False, exit_code=2, message="run.error.cancelled", msg_kwargs={"error": str(e)}, error=e)

    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e)

    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e)
    finally:
```````

#### Acts 4: 重构 `axon.py`

这是一个直接的替换过程。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
```````
```````python
import typer
from quipu.acts import register_core_acts
from quipu.interfaces.exceptions import ExecutionError
from quipu.runtime.executor import Executor
from quipu.runtime.parser import detect_best_parser, get_parser

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import confirmation_handler_for_executor
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager
```````
```````python
import typer
from quipu.acts import register_core_acts
from quipu.interfaces.exceptions import ExecutionError
from quipu.runtime.executor import Executor
from quipu.runtime.parser import detect_best_parser, get_parser

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import confirmation_handler_for_executor
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager
from quipu.common.messaging import bus
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
```````
```````python
        # 4. 处理 --list-acts
        if list_acts:
            typer.secho("\n📋 可用的 Axon 指令列表:\n", fg=typer.colors.GREEN, bold=True, err=True)
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"{indented_doc}\n")
            ctx.exit(0)
```````
```````python
        # 4. 处理 --list-acts
        if list_acts:
            bus.info("axon.listActs.ui.header")
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                bus.info("axon.listActs.ui.actItem", name=name)
                bus.data(f"{indented_doc}\n")
            ctx.exit(0)
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
```````
```````python
        source_desc = ""
        if file:
            if not file.exists():
                typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
```````
```````python
        source_desc = ""
        if file:
            if not file.exists():
                bus.error("common.error.fileNotFound", path=file)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
```````
```````python
        if not content.strip():
            typer.secho("⚠️  提示: 未提供输入 (文件或管道)，且未找到默认文件。", fg=typer.colors.YELLOW, err=True)
            ctx.exit(0)

        logger.info(f"Axon 启动 | 源: {source_desc} | 工作区: {work_dir}")
```````
```````python
        if not content.strip():
            bus.warning("axon.warning.noInput")
            ctx.exit(0)

        logger.info(f"Axon 启动 | 源: {source_desc} | 工作区: {work_dir}")
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
```````
```````python
            statements = parser.parse(content)

            if not statements:
                typer.secho(
                    f"⚠️  未解析到任何有效指令 (Parser: {final_parser_name})。", fg=typer.colors.YELLOW, err=True
                )
                ctx.exit(0)

            # 7. 执行
            executor.execute(statements)
            typer.secho("\n✨ Axon 执行完成。", fg=typer.colors.GREEN, err=True)

        except ExecutionError as e:
            typer.secho(f"\n❌ 执行失败: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
        except ValueError as e:
            logger.error(f"无效的参数或配置: {e}", exc_info=True)
            typer.secho(f"\n❌ 无效的参数或配置: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
        except Exception as e:
            logger.error(f"未预期的系统错误: {e}", exc_info=True)
            typer.secho(f"\n❌ 系统错误: {e}", fg=typer.colors.RED, err=True)
            ctx.exit(1)
```````
```````python
            statements = parser.parse(content)

            if not statements:
                bus.warning("axon.warning.noStatements", parser=final_parser_name)
                ctx.exit(0)

            # 7. 执行
            executor.execute(statements)
            bus.success("axon.success")

        except ExecutionError as e:
            bus.error("axon.error.executionFailed", error=str(e))
            ctx.exit(1)
        except ValueError as e:
            logger.error(f"无效的参数或配置: {e}", exc_info=True)
            bus.error("common.error.invalidConfig", error=str(e))
            ctx.exit(1)
        except Exception as e:
            logger.error(f"未预期的系统错误: {e}", exc_info=True)
            bus.error("common.error.generic", error=str(e))
            ctx.exit(1)
```````

#### Acts 5: 重构 `run.py`

同样地，我们对 `run.py` 进行替换。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/run.py
```````
```````python
import typer
from quipu.runtime.executor import Executor

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import run_quipu
from ..logger_config import setup_logging
```````
```````python
import typer
from quipu.runtime.executor import Executor

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..controller import run_quipu
from ..logger_config import setup_logging
from quipu.common.messaging import bus
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/run.py
```````
```````python
        if list_acts:
            executor = Executor(root_dir=Path("."), yolo=True)
            from quipu.acts import register_core_acts

            register_core_acts(executor)
            typer.secho("\n📋 可用的 Quipu 指令列表:\n", fg=typer.colors.GREEN, bold=True, err=True)
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True)
                typer.echo(f"{indented_doc}\n")
            ctx.exit(0)
```````
```````python
        if list_acts:
            executor = Executor(root_dir=Path("."), yolo=True)
            from quipu.acts import register_core_acts

            register_core_acts(executor)
            bus.info("run.listActs.ui.header")
            acts = executor.get_registered_acts()
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                bus.info("run.listActs.ui.actItem", name=name)
                bus.data(f"{indented_doc}\n")
            ctx.exit(0)
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/run.py
```````
```````python
        content = ""
        source_desc = ""
        if file:
            if not file.exists():
                typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
            if not file.is_file():
                typer.secho(f"❌ 错误: 路径不是文件: {file}", fg=typer.colors.RED, err=True)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
```````
```````python
        content = ""
        source_desc = ""
        if file:
            if not file.exists():
                bus.error("common.error.fileNotFound", path=file)
                ctx.exit(1)
            if not file.is_file():
                bus.error("common.error.pathNotFile", path=file)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/run.py
```````
```````python
        if file and not file.exists() and file.name in ["log", "checkout", "sync", "init", "ui", "find"]:
            typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED, err=True)
            typer.secho(f"💡 提示: 你是不是想执行 'quipu {file.name}' 命令？", fg=typer.colors.YELLOW, err=True)
            ctx.exit(1)
        if not content.strip():
            if not file:
                typer.secho(
                    f"⚠️  提示: 未提供输入，且当前目录下未找到默认文件 '{DEFAULT_ENTRY_FILE.name}'。",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                typer.echo("\n用法示例:", err=True)
                typer.echo("  quipu run my_plan.md", err=True)
                typer.echo("  echo '...' | quipu run", err=True)
                ctx.exit(0)

        logger.info(f"已加载指令源: {source_desc}")
        logger.info(f"工作区根目录: {work_dir}")
        if yolo:
            logger.warning("⚠️  YOLO 模式已开启：将自动确认所有修改。")
        result = run_quipu(content=content, work_dir=work_dir, parser_name=parser_name, yolo=yolo)
        if result.message:
            color = typer.colors.GREEN if result.success else typer.colors.RED
            typer.secho(f"\n{result.message}", fg=color, err=True)
        if result.data:
            typer.echo(result.data)
        ctx.exit(result.exit_code)
```````
```````python
        if file and not file.exists() and file.name in ["log", "checkout", "sync", "init", "ui", "find"]:
            bus.error("common.error.fileNotFound", path=file)
            bus.warning("run.error.ambiguousCommand", command=file.name)
            ctx.exit(1)
        if not content.strip():
            if not file:
                bus.warning("run.warning.noInput", filename=DEFAULT_ENTRY_FILE.name)
                bus.info("run.info.usageHint")
                ctx.exit(0)

        logger.info(f"已加载指令源: {source_desc}")
        logger.info(f"工作区根目录: {work_dir}")
        if yolo:
            bus.warning("run.warning.yoloEnabled")
        result = run_quipu(content=content, work_dir=work_dir, parser_name=parser_name, yolo=yolo)

        if result.message:
            kwargs = result.msg_kwargs or {}
            if result.exit_code == 2:  # OperationCancelledError
                bus.warning(result.message, **kwargs)
            elif not result.success:
                bus.error(result.message, **kwargs)
            else:
                bus.success(result.message, **kwargs)

        if result.data:
            bus.data(result.data)
        ctx.exit(result.exit_code)
```````

#### Acts 6: 重构测试用例

最后，我们重写 `test_unfriendly_paths.py` 中的 `run` 命令相关测试。

```````act
patch_file
tests/cli/test_unfriendly_paths.py
```````
```````python
def test_run_command_user_cancellation(runner: CliRunner, quipu_workspace, monkeypatch):
    """
    不友好路径测试: 验证当用户输入 'n' 时，`run` 操作会被正确取消。
    """
    work_dir, _, _ = quipu_workspace
    output_file = work_dir / "output.txt"
    assert not output_file.exists()

    plan_content = f"""
```act
run_command
```
```text
echo "Should not run" > {output_file.name}
```
"""

    def mock_getchar_n(echo):
        click.echo("n", err=True)
        return "n"

    monkeypatch.setattr(click, "getchar", mock_getchar_n)

    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content)

    assert result.exit_code == 2, f"CLI command should have been cancelled. Stderr:\n{result.stderr}"
    assert "操作已取消" in result.stderr
    assert not output_file.exists()
```````
```````python
def test_run_command_user_cancellation(runner: CliRunner, quipu_workspace, monkeypatch):
    """
    不友好路径测试: 验证当用户输入 'n' 时，`run` 操作会被正确取消。
    """
    work_dir, _, _ = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.run.bus", mock_bus)
    output_file = work_dir / "output.txt"
    assert not output_file.exists()

    plan_content = f"""
```act
run_command
```
```text
echo "Should not run" > {output_file.name}
```
"""

    def mock_getchar_n(echo):
        click.echo("n", err=True)
        return "n"

    monkeypatch.setattr(click, "getchar", mock_getchar_n)

    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content)

    assert result.exit_code == 2
    mock_bus.warning.assert_called_once_with("run.error.cancelled", error=mock.ANY)
    assert not output_file.exists()
```````

```````act
patch_file
tests/cli/test_unfriendly_paths.py
```````
```````python
def test_run_command_in_non_interactive_env(runner: CliRunner, quipu_workspace, monkeypatch):
    """
    不友好路径测试: 验证在非交互式环境 (无法 getchar) 中，`run` 操作会自动中止。
    """
    work_dir, _, _ = quipu_workspace
    output_file = work_dir / "output.txt"
    assert not output_file.exists()

    plan_content = f"""
```act
run_command
```
```text
echo "Should not run" > {output_file.name}
```
"""

    def mock_getchar_fail(echo):
        raise EOFError("Simulating non-interactive environment")

    monkeypatch.setattr(click, "getchar", mock_getchar_fail)
    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content)

    assert result.exit_code == 2
    assert "操作已取消" in result.stderr
    assert "(non-interactive)" in result.stderr
    assert not output_file.exists()
```````
```````python
from unittest import mock

def test_run_command_in_non_interactive_env(runner: CliRunner, quipu_workspace, monkeypatch):
    """
    不友好路径测试: 验证在非交互式环境 (无法 getchar) 中，`run` 操作会自动中止。
    """
    work_dir, _, _ = quipu_workspace
    mock_bus = MagicMock()
    monkeypatch.setattr("quipu.cli.commands.run.bus", mock_bus)
    output_file = work_dir / "output.txt"
    assert not output_file.exists()

    plan_content = f"""
```act
run_command
```
```text
echo "Should not run" > {output_file.name}
```
"""

    def mock_getchar_fail(echo):
        raise EOFError("Simulating non-interactive environment")

    monkeypatch.setattr(click, "getchar", mock_getchar_fail)
    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content)

    assert result.exit_code == 2
    mock_bus.warning.assert_called_once_with("run.error.cancelled", error=mock.ANY)
    assert not output_file.exists()
```````

```````act
patch_file
tests/cli/test_cli_interaction.py
```````
```````python
import pytest
from typer.testing import CliRunner
from quipu.cli.main import app


def test_run_command_with_piped_input_and_confirmation(runner: CliRunner, quipu_workspace):
    """
    测试核心场景: 通过管道输入 plan，并对需要确认的 act (run_command) 进行交互。
    """
    work_dir, _, _ = quipu_workspace
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

    # 模拟用户输入 'y' 并按回车
    user_input = "y\n"

    # 使用 runner.invoke 的 input 参数来模拟 `echo "{plan_content}" | quipu run`
    # 注意：CliRunner 的 input 模拟的是 stdin，这正是我们需要的
    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content + user_input)

    assert result.exit_code == 0, f"CLI command failed with stderr:\n{result.stderr}"
    assert "✨ 执行成功" in result.stderr
    assert output_file.exists(), "The command did not create the output file."
    assert output_file.read_text().strip() == "Success"
```````
```````python
import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock
from quipu.cli.main import app


def test_run_command_with_piped_input_and_confirmation(runner: CliRunner, quipu_workspace, monkeypatch):
    """
    测试核心场景: 通过管道输入 plan，并对需要确认的 act (run_command) 进行交互。
    """
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

    # 模拟用户输入 'y' 并按回车
    user_input = "y\n"

    result = runner.invoke(app, ["run", "-w", str(work_dir)], input=plan_content + user_input)

    assert result.exit_code == 0
    mock_bus.success.assert_called_once_with("run.success")
    assert output_file.exists(), "The command did not create the output file."
    assert output_file.read_text().strip() == "Success"
```````

### 下一步建议
我们已经成功地将核心的 `run` 和 `axon` 命令迁移到了 `MessageBus` 架构，并改进了 `QuipuResult` 接口，使得整个执行流程的内外通信更加清晰。

重构任务已接近尾声。下一步是处理最后一批独立的、功能性的命令：**`remote`、`export` 和 `ui`**。完成这些命令的迁移后，整个 `quipu-cli` 的用户输出层将实现完全的统一和解耦。
