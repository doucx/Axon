你发现的问题非常准确。

`tui.debug.log` 之所以默认开启，是因为 `ui` 命令的设计初衷是为了方便调试，因此它绕过了全局的日志级别配置，直接调用了一个专门用于文件日志的函数 `configure_file_logging`，该函数内部**硬编码了 `logging.DEBUG` 级别**。

这导致无论 `QUIPU_LOG_LEVEL` 设置成什么，只要运行 `quipu ui`，就会强制以 `DEBUG` 级别向文件写入日志。这显然是不理想的默认行为。

我将修改这个逻辑，使其遵循全局配置：只有当 `QUIPU_LOG_LEVEL` 明确设置为 `DEBUG` 时，`quipu ui` 才会启用文件日志记录。在其他情况下（如默认的 `INFO`），它将和其他命令一样，将日志输出到 `stderr`。

## [WIP] fix: TUI 日志应遵循全局日志级别配置

### 错误分析
`quipu ui` 命令在其实现文件 (`commands/ui.py`) 中，无条件地调用了 `configure_file_logging` 函数。这个函数在 `logger_config.py` 中被定义为强制设置日志级别为 `DEBUG` 并将输出重定向到 `tui.debug.log` 文件。

这种实现方式覆盖了由 `QUIPU_LOG_LEVEL` 环境变量控制的全局日志级别设置，导致即使用户配置了 `INFO` 级别，TUI 依然会创建并写入大量的调试日志，造成了不必要的磁盘 I/O 和混乱。

### 用户需求
修改 `quipu ui` 命令的行为，使其：
1.  仅在 `QUIPU_LOG_LEVEL` 环境变量被设置为 `DEBUG` 时，才激活文件日志记录 (`tui.debug.log`)。
2.  在所有其他日志级别下 (例如 `INFO`, `WARNING`, `ERROR`)，其日志行为应与其他 CLI 命令保持一致，即将日志输出到标准错误流 (`stderr`)。

### 评论
这是一个重要的可用性修复。让所有命令的日志行为保持一致并尊重用户的全局配置，是良好 CLI 设计的基础。此修改将使 TUI 的行为更加可预测，并避免了在常规使用中产生不必要的日志文件。

### 目标
1.  在 `commands/ui.py` 中导入 `LOG_LEVEL` 配置变量和标准的 `setup_logging` 函数。
2.  在 `ui` 命令的入口处添加条件逻辑：检查 `LOG_LEVEL` 的值。
3.  如果 `LOG_LEVEL` 是 `DEBUG`，则调用 `configure_file_logging`。
4.  否则，调用 `setup_logging`，以启用标准的 `stderr` 日志记录。

### 基本原理
我们将决策逻辑从 `logger_config.py` 上移到命令的调用方 `ui.py`。`configure_file_logging` 函数将继续作为专门的调试日志设置工具，但调用它的权力现在取决于全局配置。通过在 `ui` 命令中根据 `LOG_LEVEL` 变量的值选择调用 `configure_file_logging` 还是 `setup_logging`，我们确保了 TUI 的日志行为与整个应用的其他部分保持一致，同时保留了在需要时轻松开启详细文件调试的能力。

### 标签
#intent/fix #flow/ready #priority/medium #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/logging-error-handling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `ui.py` 的逻辑

我们将修改 `ui.py`，引入条件判断来决定使用哪种日志配置。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~
~~~~~python
from .helpers import engine_context, _execute_visit
from ..config import DEFAULT_WORK_DIR
from ..factory import create_engine
from ..logger_config import configure_file_logging
~~~~~
~~~~~python
from .helpers import engine_context, _execute_visit
from ..config import DEFAULT_WORK_DIR, LOG_LEVEL
from ..factory import create_engine
from ..logger_config import configure_file_logging, setup_logging
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~
~~~~~python
        log_file = work_dir / ".quipu" / "tui.debug.log"
        configure_file_logging(log_file)
        logging.info("Starting Quipu UI command...")
~~~~~
~~~~~python
        if LOG_LEVEL == "DEBUG":
            log_file = work_dir / ".quipu" / "tui.debug.log"
            configure_file_logging(log_file)
        else:
            setup_logging()  # Use standard stderr logging for INFO level and above

        logging.info("Starting Quipu UI command...")
~~~~~

### 下一步建议
我们已经修正了 TUI 的日志记录逻辑。为了验证修复效果，请按照以下步骤操作：

1.  **清理环境**: 首先，删除现有的日志文件：`rm .quipu/tui.debug.log`。
2.  **测试默认行为**: 直接运行 `quipu ui`。预期结果是程序正常启动，但 **不会** 在 `.quipu/` 目录下创建 `tui.debug.log` 文件。
3.  **测试调试行为**: 使用 `QUIPU_LOG_LEVEL=DEBUG quipu ui` 命令启动。预期结果是程序启动，并且 **会** 创建并写入 `tui.debug.log` 文件。

如果上述测试均符合预期，我们就可以将这些日志相关的改进作为一个完整的单元进行提交。
