好的，代码修改和测试重构均已完成。现在，我将生成一个 `[COMMIT]` 计划来固化这些变更。

这个计划不仅会执行 Git 提交操作，还会详细说明我们刚刚完成的**重构流程**，并为下一步工作提供清晰的指引。

## [COMMIT] refactor(cli): 将 workspace 命令迁移到 MessageBus

### 用户需求
将 `quipu workspace` 子命令（`save` 和 `discard`）的输出逻辑从硬编码的 `typer.secho` 调用迁移到新建立的 `MessageBus` 系统。同时，更新相关测试用例，使其通过模拟 `MessageBus` 来验证业务逻辑意图，而不是匹配脆弱的输出字符串。

### 评论
这是一个关键的里程碑。通过这次试点重构，我们不仅改进了 `workspace` 命令本身，更重要的是验证了 `MessageBus` 架构的可行性，并建立了一套可复制的、用于将业务逻辑与 UI 呈现解耦的标准化流程。这套流程将极大地提升后续重构工作的效率和质量。

### 目标
1.  **基础设施落地**：在 `quipu-common` 中成功创建并集成了 `MessageBus` 系统的核心实现。
2.  **命令重构**：`workspace.py` 已完全使用 `bus` 实例进行用户消息输出，代码更清晰，意图更明确。
3.  **内容外部化**：所有相关的消息文本都已提取到 `locales/zh/cli.json` 中，为国际化做好了准备。
4.  **测试现代化**：`test_workspace_commands.py` 已重构，通过模拟 `MessageBus`，测试用例现在变得健壮、可维护，并且与 UI 实现完全解耦。

### 基本原理
我们刚刚完成的流程，其核心是**依赖倒置原则**在 CLI 应用和测试中的一次经典实践。

1.  **在应用层**：我们将“输出消息”这个具体的实现细节（`typer.secho`）抽象成了一个接口 (`MessageBus`)。`workspace.py` 不再关心消息如何显示，只关心**要传达什么语义**（例如 `bus.success("workspace.save.success", ...)`）。
2.  **在测试层**：我们利用 `pytest` 的 `monkeypatch` 工具，在测试运行时将 `MessageBus` 的真实实例替换为一个**模拟对象 (`MagicMock`)**。这使得我们的测试能够拦截并检查对 `bus` 的调用。
3.  **断言的转变**：我们的断言从 `assert "快照已保存" in result.stderr`（**检查表现**）转变为 `mock_bus.success.assert_called_once_with("workspace.save.success", ...)`（**验证意图**）。这使得测试不再因文案、颜色或图标的调整而失败，变得极其稳固。

这个流程证明了我们可以系统性地消除代码中的“表示层”耦合，使核心逻辑更纯粹，测试更可靠。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/common #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/message-bus #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 将所有相关的变更添加到暂存区

我们将所有新建和修改的文件一次性添加到 Git 的暂存区，准备提交。

~~~~~act
git_add
packages/quipu-common/src/quipu/common/messaging/__init__.py
packages/quipu-common/src/quipu/common/messaging/bus.py
packages/quipu-common/src/quipu/common/messaging/messages.py
packages/quipu-common/pyproject.toml
locales/zh/cli.json
packages/quipu-cli/src/quipu/cli/commands/workspace.py
tests/cli/test_workspace_commands.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们创建一个符合 Conventional Commits 规范的提交，永久记录这次重构。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(cli): migrate workspace commands to MessageBus

Implements the first phase of the MessageBus architecture adoption.

This commit introduces the core MessageBus infrastructure in `quipu-common` and refactors the `quipu save` and `quipu discard` commands to use it for all user-facing output.

Key changes:
- A new `MessageBus` system is created in `quipu.common.messaging` to centralize and semanticize CLI output.
- All user-facing strings from `workspace.py` have been extracted to `locales/zh/cli.json`.
- The corresponding tests in `test_workspace_commands.py` have been updated to use mocking (`unittest.mock`), asserting against bus method calls instead of fragile string matching on stderr.

This change significantly improves maintainability, test robustness, and prepares the CLI for future internationalization.
~~~~~

### 下一步建议
试点非常成功。我们已经建立并验证了一套行之有效的重构模式。

现在，我建议我们继续沿着这条路走下去，将这个模式应用到其他命令模块。一个好的起点是那些**只读的、逻辑相对简单**的命令，例如 `query` 和 `show`。这将是一次低风险、高回报的操作，可以进一步巩固我们的新架构。

如果你同意，请指示我开始重构 `query` 和 `show` 命令。
