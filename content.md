好的，我们继续进行重构的第二阶段。

现在核心逻辑文件已经迁移，`pyquipu-cli` 包中的许多命令都处于“损坏”状态，因为它们的导入路径已经失效。本计划将逐一修复这些命令，使它们与新的 `pyquipu-application` 包正确集成。

## [WIP] fix: 修复 `cli` 包因重构造成的内部依赖损坏

### 用户需求
在核心逻辑迁移到 `pyquipu-application` 后，`pyquipu-cli` 包内部的多个命令文件（如 `helpers.py`, `axon.py`, `ui.py` 等）的 `import` 语句已经失效。需要更新这些文件的导入路径，使其指向新的 `pyquipu.application` 命名空间，并解决因此产生的依赖问题。

### 评论
这是重构过程中承上启下的关键一步。通过修复这些“损坏”的链接，我们将使 `cli` 包重新变得可执行，并验证新的分层架构是正确且有效的。这一步还将暴露出在迁移过程中可能被忽略的耦合点，并给我们机会去修复它们。

### 目标
1.  修复 `commands/helpers.py` 中对 `create_engine` 的导入。
2.  修复 `commands/axon.py` 中对 `PluginManager` 的导入，并为其提供一个 CLI 特有的确认处理器。
3.  修复 `commands/ui.py` 和 `commands/remote.py` 中的失效导入。
4.  为 `controller` 中新增的 `default_confirmation_handler` 添加对应的本地化消息文本。
5.  确保所有命令都已适配新的应用层架构。

### 基本原理
我们将对 `pyquipu-cli` 包内的多个文件进行一系列精确的 `patch_file` 操作。核心是遵循 Python 的模块解析规则，将所有旧的相对导入（如 `from ..factory`）更改为指向新 `application` 包的绝对导入（如 `from pyquipu.application.factory`）。对于 `axon.py` 中被解耦的 `confirmation_handler`，我们将复用 `run.py` 中为 CLI 实现的适配器，确保行为一致。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/build #scope/core #dx #ai/instruct #task/domain/architecture #task/object/core-application-layer #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `helpers.py` (这是修复大多数命令的关键)

`engine_context` 依赖于 `create_engine`，我们需要更新其来源。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/helpers.py
~~~~~
~~~~~python
from ..factory import create_engine
~~~~~
~~~~~python
from pyquipu.application.factory import create_engine
~~~~~

#### Acts 2: 修复无状态执行器 `axon.py`

`axon` 命令需要从 `application` 包导入 `PluginManager`，并需要一个独立的确认处理器。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/axon.py
~~~~~
~~~~~python
from ..controller import confirmation_handler_for_executor
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager
~~~~~
~~~~~python
from typing import List

from pyquipu.interfaces.exceptions import OperationCancelledError

from ..controller import confirmation_handler_for_cli
from ..logger_config import setup_logging
from ..plugin_manager import PluginManager
from ..ui_utils import prompt_for_confirmation


def confirmation_handler_for_executor(diff_lines: List[str], prompt: str) -> bool:
    """Adapter for the Executor's confirmation handler contract, specific to the CLI."""
    confirmed = prompt_for_confirmation(prompt=prompt, diff_lines=diff_lines, default=True)
    if not confirmed:
        raise OperationCancelledError("User cancelled the operation.")
    return True
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/axon.py
~~~~~
~~~~~python
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=confirmation_handler_for_executor,
        )
~~~~~
~~~~~python
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=confirmation_handler_for_cli,
        )
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/axon.py
~~~~~
~~~~~python
from ..plugin_manager import PluginManager
~~~~~
~~~~~python
from pyquipu.application.plugin_manager import PluginManager
~~~~~

#### Acts 3: 修复 `ui.py` 和 `remote.py`

这两个命令也需要更新其导入语句。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/ui.py
~~~~~
~~~~~python
from ..factory import create_engine
~~~~~
~~~~~python
from pyquipu.application.factory import create_engine
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/remote.py
~~~~~
~~~~~python
from ..utils import find_git_repository_root
~~~~~
~~~~~python
from pyquipu.application.utils import find_git_repository_root
~~~~~

#### Acts 4: 添加缺失的本地化消息

在 `controller.py` 中引入了一个新的 `default_confirmation_handler`，它会在没有提供处理器时发出警告。我们需要为这个警告添加消息文本。

~~~~~act
patch_file
packages/quipu-common/src/pyquipu/common/locales/zh/cli.json
~~~~~
~~~~~json
  "run.error.system": "系统错误: {error}",
~~~~~
~~~~~json
  "run.error.system": "系统错误: {error}",
  "run.error.noConfirmationHandler": "⚠️  警告: 未提供交互式确认处理器，操作已自动取消。",
~~~~~

#### Acts 5: 修复 `run.py` 中缺失的类型导入

上一步对 `run.py` 的重构引入了 `List` 类型提示，但忘记了导入它。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/run.py
~~~~~
~~~~~python
from pyquipu.application.controller import QuipuApplication
~~~~~
~~~~~python
from typing import List

from pyquipu.application.controller import QuipuApplication
~~~~~

### 下一步建议
我们已经完成了对 `pyquipu-cli` 包的修复。理论上，整个 CLI 的功能现在应该已经恢复正常，并且其架构也变得更加清晰和健壮。

**强烈建议下一步运行完整的测试套件**，以验证我们的重构是否成功，并确保没有引入任何回归错误。在确认所有测试通过后，我们可以将这次重构标记为 `[COMMIT]`，并准备开始 `pyquipu-webapi` 的开发工作。
