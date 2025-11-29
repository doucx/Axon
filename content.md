好的，既然测试已通过，我将生成一个 `[COMMIT]` 计划来将我们刚才完成的所有日志和错误处理改进持久化到版本历史中。

这个计划将汇总我们之前的所有修改：重命名环境变量、在所有通用异常捕获中添加堆栈跟踪日志，以及修复 TUI 日志记录行为。

## [COMMIT] chore(cli): 增强日志记录与错误处理

### 用户需求
1.  将控制日志级别的环境变量从 `LOG_LEVEL` 更改为项目专有的 `QUIPU_LOG_LEVEL`。
2.  在捕获通用 `Exception` 的代码块中，记录完整的错误堆栈跟踪信息以方便调试。
3.  修复 `quipu ui` 命令无条件生成 `tui.debug.log` 文件的问题，使其行为遵循 `QUIPU_LOG_LEVEL` 的全局配置。

### 评论
这是一次关键的工程实践改进。通过标准化日志行为、提供详细的错误上下文和使用专有配置，我们显著提升了 Quipu CLI 的健壮性、可维护性和开发者体验。这些改动使得追踪和调试问题变得更加高效。

### 目标
1.  已将日志级别环境变量更新为 `QUIPU_LOG_LEVEL`。
2.  已在 `axon`, `cache`, `navigation`, `workspace` 等命令的通用异常处理器中通过 `exc_info=True` 添加了堆栈跟踪日志。
3.  已修改 `quipu ui` 命令，使其仅在 `QUIPU_LOG_LEVEL=DEBUG` 时才创建文件日志，否则使用标准的 `stderr` 输出。
4.  已在引擎工厂等关键路径添加了额外的调试日志。

### 基本原理
我们通过将日志配置逻辑集中化，并在命令层级根据全局配置进行决策，实现了行为的一致性。利用 Python `logging` 模块的 `exc_info=True` 参数，可以在不中断现有错误处理流程的情况下，极大地丰富错误日志的上下文信息。此系列修改遵循了命令行工具设计的最佳实践。

### 标签
#intent/refine #intent/fix #flow/ready #priority/medium #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/logging-error-handling #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有相关的代码变更

现在，我们将所有修改过的文件添加到 Git 暂存区，并创建一个内容详尽的提交来完成这次重构任务。

~~~~~act
git_add
~~~~~
~~~~~text
packages/quipu-cli/src/quipu/cli/config.py
packages/quipu-cli/src/quipu/cli/factory.py
packages/quipu-cli/src/quipu/cli/commands/axon.py
packages/quipu-cli/src/quipu/cli/commands/cache.py
packages/quipu-cli/src/quipu/cli/commands/helpers.py
packages/quipu-cli/src/quipu/cli/commands/navigation.py
packages/quipu-cli/src/quipu/cli/commands/workspace.py
packages/quipu-cli/src/quipu/cli/commands/ui.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
chore(cli): enhance logging and error handling

This commit introduces several improvements to the logging and error handling mechanisms within the Quipu CLI to enhance robustness and debuggability.

Key changes include:

1.  **Environment Variable Renaming**: The log level environment variable has been renamed from `LOG_LEVEL` to the project-specific `QUIPU_LOG_LEVEL` to prevent conflicts with other tools.

2.  **Detailed Error Logging**: All broad `except Exception` blocks now log the full exception traceback using `logger.error(..., exc_info=True)`. This provides crucial context for debugging unexpected errors.

3.  **Conditional TUI Logging**: The `quipu ui` command no longer unconditionally creates a `tui.debug.log` file. It now respects the global `QUIPU_LOG_LEVEL` configuration, only enabling file-based DEBUG logging when explicitly requested. In all other cases, it logs to stderr, consistent with other commands.

4.  **Added Debug Information**: Supplementary DEBUG-level logs have been added to key pathways, such as the engine factory, to provide better visibility into the application's internal state during debugging sessions.
~~~~~

### 下一步建议
我们已经成功地将日志和错误处理的改进合并到了代码库中。接下来，我们可以继续处理下一个开发任务。如果你有新的想法或需要修复其他问题，请告诉我。
