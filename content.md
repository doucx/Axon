好的，我们开始执行代码迁移。

这个过程将分为几个原子化的步骤：首先移动文件，然后修复因移动而产生的依赖关系和耦合问题。

## [WIP] refactor: 将核心逻辑迁移到 `pyquipu-application`

### 用户需求
将 `controller.py`, `factory.py`, `plugin_manager.py` 和 `utils.py` 从 `pyquipu-cli` 包迁移到新创建的 `pyquipu-application` 包中，并修复由此引起的模块间依赖关系。

### 评论
这是实现架构解耦的核心执行步骤。通过这次迁移，`pyquipu-cli` 将演变为一个纯粹的“表现层”，其所有核心业务逻辑都委托给新的 `pyquipu-application` 包处理。这为未来添加 `pyquipu-webapi` 等其他入口打下了坚实的基础。

### 目标
1.  将四个核心逻辑文件物理移动到 `pyquipu-application` 的 `src` 目录。
2.  更新被移动文件内部的导入语句，以反映其新的命名空间。
3.  重构 `QuipuApplication` 控制器，通过依赖注入的方式解耦其与 `cli` 特有的 UI 工具 (`ui_utils`) 的绑定。
4.  更新 `pyquipu-cli` 中的命令，使其调用新的 `pyquipu-application` 包中的逻辑。

### 基本原理
我们采用“移动-修复”的策略。首先通过 `move_file` 操作完成文件的物理迁移。然后，通过一系列精准的 `patch_file` 操作来重构代码：首先修复新包内部的相对导入路径，接着修改 `QuipuApplication` 的构造函数以接受一个可调用对象 (`confirmation_handler`)，最后更新 `pyquipu-cli` 包的 `import` 语句，使其指向新的 `pyquipu.application` 命名空间。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/build #scope/core #dx #ai/instruct #task/domain/architecture #task/object/core-application-layer #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 物理移动核心逻辑文件

我们将 `controller`, `factory`, `plugin_manager`, 和 `utils` 从 `cli` 移动到 `application` 包。

~~~~~act
move_file
packages/quipu-cli/src/pyquipu/cli/utils.py
packages/quipu-application/src/pyquipu/application/utils.py
~~~~~

~~~~~act
move_file
packages/quipu-cli/src/pyquipu/cli/plugin_manager.py
packages/quipu-application/src/pyquipu/application/plugin_manager.py
~~~~~

~~~~~act
move_file
packages/quipu-cli/src/pyquipu/cli/factory.py
packages/quipu-application/src/pyquipu/application/factory.py
~~~~~

~~~~~act
move_file
packages/quipu-cli/src/pyquipu/cli/controller.py
packages/quipu-application/src/pyquipu/application/controller.py
~~~~~

#### Acts 2: 修复 `application` 包内部的导入路径

现在文件已经移动，我们需要更新它们内部的 `import` 语句。

~~~~~act
patch_file
packages/quipu-application/src/pyquipu/application/factory.py
~~~~~
~~~~~python
from .utils import find_git_repository_root
~~~~~
~~~~~python
from pyquipu.application.utils import find_git_repository_root
~~~~~

~~~~~act
patch_file
packages/quipu-application/src/pyquipu/application/plugin_manager.py
~~~~~
~~~~~python
from .utils import find_git_repository_root
~~~~~
~~~~~python
from pyquipu.application.utils import find_git_repository_root
~~~~~

~~~~~act
patch_file
packages/quipu-application/src/pyquipu/application/controller.py
~~~~~
~~~~~python
from .factory import create_engine
from .plugin_manager import PluginManager
from .ui_utils import prompt_for_confirmation
~~~~~
~~~~~python
from pyquipu.application.factory import create_engine
from pyquipu.application.plugin_manager import PluginManager
from pyquipu.common.messaging import bus
~~~~~

#### Acts 3: 解耦 `QuipuApplication` 与 CLI 的 UI 依赖

我们将修改 `QuipuApplication` 以接受一个外部的 `confirmation_handler`，而不是直接调用 `cli` 的 `ui_utils`。

~~~~~act
patch_file
packages/quipu-application/src/pyquipu/application/controller.py
~~~~~
~~~~~python
def confirmation_handler_for_executor(diff_lines: List[str], prompt: str) -> bool:
    """
    为 Executor 的确认处理器契约提供的适配器。
    它调用统一的提示器，并在用户取消时抛出异常。
    对于 'run' 操作，默认行为是继续，除非用户按下 'n'。
    """
    # 原始逻辑是 `char.lower() != "n"`，这相当于默认为 True
    confirmed = prompt_for_confirmation(prompt=prompt, diff_lines=diff_lines, default=True)
    if not confirmed:
        raise OperationCancelledError("User cancelled the operation.")
    # 执行器的处理器不使用布尔返回值，它依赖于异常。
    # 但为保持契约一致性，我们返回 True。
    return True


class QuipuApplication:
    """
    封装了 Quipu 核心业务流程的高层应用对象。
    负责协调 Engine, Parser, Executor。
    """

    def __init__(self, work_dir: Path, yolo: bool = False):
        self.work_dir = work_dir
        self.yolo = yolo
        self.engine: Engine = create_engine(work_dir)
        logger.info(f"Operation boundary set to: {self.work_dir}")
~~~~~
~~~~~python
from typing import Callable, List, Optional

# ... (other imports)

ConfirmationHandler = Callable[[List[str], str], bool]


def default_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
    """A default handler that always cancels to prevent accidental changes."""
    bus.warning("run.error.noConfirmationHandler")
    return False


class QuipuApplication:
    """
    封装了 Quipu 核心业务流程的高层应用对象。
    负责协调 Engine, Parser, Executor。
    """

    def __init__(
        self,
        work_dir: Path,
        yolo: bool = False,
        confirmation_handler: Optional[ConfirmationHandler] = None,
    ):
        self.work_dir = work_dir
        self.yolo = yolo
        self.engine: Engine = create_engine(work_dir)
        self.confirmation_handler = confirmation_handler or default_confirmation_handler
        logger.info(f"Operation boundary set to: {self.work_dir}")
~~~~~

~~~~~act
patch_file
packages/quipu-application/src/pyquipu/application/controller.py
~~~~~
~~~~~python
    def _setup_executor(self) -> Executor:
        """创建、配置并返回一个 Executor 实例，并注入 UI 依赖。"""

        executor = Executor(
            root_dir=self.work_dir,
            yolo=self.yolo,
            confirmation_handler=confirmation_handler_for_executor,
        )
~~~~~
~~~~~python
    def _setup_executor(self) -> Executor:
        """创建、配置并返回一个 Executor 实例，并注入 UI 依赖。"""

        executor = Executor(
            root_dir=self.work_dir,
            yolo=self.yolo,
            confirmation_handler=self.confirmation_handler,
        )
~~~~~

#### Acts 4: 更新 `pyquipu-cli` 的 `run` 命令以使用新架构

最后，我们更新 `run.py`，让它调用 `pyquipu-application` 中的逻辑，并向其注入 CLI 特有的确认处理器。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/run.py
~~~~~
~~~~~python
from ..controller import run_quipu
~~~~~
~~~~~python
from pyquipu.application.controller import QuipuApplication
from pyquipu.interfaces.exceptions import OperationCancelledError, ExecutionError as CoreExecutionError
from pyquipu.interfaces.result import QuipuResult
from ..ui_utils import prompt_for_confirmation


def confirmation_handler_for_cli(diff_lines: List[str], prompt: str) -> bool:
    """
    Adapter for the Executor's confirmation handler contract, specific to the CLI.
    """
    confirmed = prompt_for_confirmation(prompt=prompt, diff_lines=diff_lines, default=True)
    if not confirmed:
        raise OperationCancelledError("User cancelled the operation.")
    return True


def run_quipu(content: str, work_dir: Path, parser_name: str = "auto", yolo: bool = False) -> QuipuResult:
    """
    Wrapper for the core Quipu business logic.
    """
    app = None
    try:
        app = QuipuApplication(
            work_dir=work_dir,
            yolo=yolo,
            confirmation_handler=confirmation_handler_for_cli,
        )
        return app.run(content=content, parser_name=parser_name)

    except OperationCancelledError as e:
        logger.info(f"🚫 操作已取消: {e}")
        return QuipuResult(
            success=False, exit_code=2, message="run.error.cancelled", msg_kwargs={"error": str(e)}, error=e
        )
    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
    finally:
        if app and hasattr(app, "engine") and app.engine:
            app.engine.close()
~~~~~

### 下一步建议
我们已经成功地将核心业务逻辑迁移到了 `pyquipu-application` 包中。然而，这次重构影响了多个模块，`axon.py`, `ui.py`, `workspace.py` 等命令文件中的导入和调用方式也需要更新，以适应新的架构。

下一步，我们将全面修复 `pyquipu-cli` 中所有剩余的、因本次重构而损坏的命令。

