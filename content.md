好的，所有测试都已通过。`quipu-runtime` 到 `MessageBus` 的迁移工作已经成功完成。现在我们将把这一系列的工作作为一个逻辑单元进行提交。

## [COMMIT] refactor(runtime): 将 quipu-runtime 的输出迁移到 MessageBus

### 用户需求
将 `quipu-runtime` 模块（包括 `Executor`，`PluginLoader` 和所有 `Acts`）中所有面向用户的 `logging` 和 `print` 调用，全部迁移到 `quipu-common` 中定义的 `MessageBus` 服务。同时，更新 `tests/runtime` 下的所有测试用例，使其通过 `monkeypatch` 注入 `mock_bus` 进行验证，与 UI 输出解耦。

### 评论
这次重构是 `MessageBus` 计划的核心部分，它统一了 `Quipu` 执行层的输出规范。这不仅提升了代码的可维护性和可测试性，也为未来支持国际化、结构化日志等高级功能奠定了坚实的基础。通过修复 `monkeypatch` 的目标问题，我们也加固了测试套件的健壮性。

### 目标
1.  已在 `packages/quipu-runtime/pyproject.toml` 中添加了对 `quipu-common` 的依赖。
2.  已在 `locales/zh/cli.json` 中添加了所有 Runtime 相关的消息 ID 和模板。
3.  已将 `quipu-runtime` 源代码中所有面向用户的输出替换为 `bus` 调用。
4.  已重构 `tests/runtime` 的测试用例，使用 `mock_bus` 进行断言。
5.  创建一个 Git 提交，将这个完整的重构工作持久化。

### 基本原理
通过将 `quipu-runtime` 的输出层抽象为 `MessageBus`，我们实现了业务逻辑（执行 `Acts`）与用户呈现（打印到控制台）的彻底分离。测试现在验证的是“系统意图发出什么消息”（`bus.success.assert_called_with(...)`），而不是“系统实际打印了什么字符串”，这使得测试对 UI 文案的修改免疫，从而更加稳定和可靠。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/message-bus #task/action/migration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有变更

我们将把所有相关的修改（`quipu-runtime` 源代码、测试代码、`locales` 资源文件以及 `pyproject.toml`）添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/quipu-runtime/pyproject.toml
packages/quipu-runtime/src/quipu/runtime/executor.py
packages/quipu-runtime/src/quipu/runtime/plugin_loader.py
packages/quipu-runtime/src/quipu/acts/basic.py
packages/quipu-runtime/src/quipu/acts/check.py
packages/quipu-runtime/src/quipu/acts/git.py
packages/quipu-runtime/src/quipu/acts/memory.py
packages/quipu-runtime/src/quipu/acts/read.py
packages/quipu-runtime/src/quipu/acts/refactor.py
packages/quipu-runtime/src/quipu/acts/shell.py
locales/zh/cli.json
tests/runtime/conftest.py
tests/runtime/acts/test_check.py
tests/runtime/acts/test_git.py
tests/runtime/acts/test_read.py
tests/runtime/test_plugin_loader.py
tests/runtime/test_plugin_resilience.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): migrate quipu-runtime output to MessageBus

This commit completes a major refactoring to migrate all user-facing
output in the `quipu-runtime` package from `logging` and `print` to the
centralized `MessageBus` service.

Key changes include:
- Added `quipu-common` dependency to `quipu-runtime`.
- Replaced all relevant `logging` calls in `Executor`, `PluginLoader`,
  and all `Acts` with semantic `bus` calls (e.g., `bus.success`,
  `bus.info`).
- Refactored the entire `tests/runtime` suite to use a `mock_bus`
  injected via a multi-target `monkeypatch` in `conftest.py`. This
  decouples tests from UI strings and validates semantic intent.
- Defined all necessary message IDs and templates in `locales/zh/cli.json`.

This change standardizes the output of the execution layer, improves
testability, and lays the groundwork for i18n and structured logging.
~~~~~

### 下一步建议
我们已经成功完成了 `quipu-cli` 和 `quipu-runtime` 两个核心包向 `MessageBus` 的迁移。下一步的逻辑重点是 **Phase 3: 迁移 `quipu-engine`**。

这个阶段需要更加谨慎，因为 `engine` 中的日志更多是面向开发者的调试信息。我们需要仔细甄别哪些 `logging` 调用应该保留（用于调试），哪些是真正需要暴露给用户的警告或错误信息，应该被迁移。

如果你同意，我们可以开始分析 `quipu-engine` 的代码，并制定迁移计划。
