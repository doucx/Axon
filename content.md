好的，所有测试都已通过。我们现在将这个重构和测试增强任务作为一个完整的逻辑单元进行提交。

## [COMMIT] refactor(runtime): 使用 MessageBus 并提高 Act 测试覆盖率

### 用户需求
1.  将 `quipu-runtime` 中所有 Act 的硬编码错误消息迁移到 `MessageBus` 系统。
2.  为 `refactor`, `shell`, `memory` 等低覆盖率模块补充单元测试。
3.  确保所有相关测试都断言语义化的 `msg_id` 而非具体的 UI 文本。

### 评论
这次重构是一次重要的技术债务偿还。它不仅使 Act 模块的代码更清晰、更易于国际化，还通过规范化的测试模式，极大地增强了测试套件的健壮性和可维护性。任何未来的 UI 文案调整都不会再破坏单元测试。

### 目标
1.  已将所有 `pyquipu.acts` 子模块中的 `ctx.fail("...")` 硬编码字符串替换为 `bus.get(...)` 调用。
2.  已创建新的 `acts.json` 资源文件来存放所有 Act 相关的消息。
3.  已为 `refactor`, `shell`, `memory` 模块创建了新的测试文件，覆盖了核心成功与失败路径。
4.  已更新所有受影响的现有测试，使其断言 `msg_id`，并修复了在此过程中发现的两个 Bug (shell 异常处理范围、误删的文档字符串)。
5.  创建一个 Git 提交，固化所有这些改进。

### 基本原理
通过将 UI 字符串与业务逻辑彻底解耦，我们遵循了软件工程的最佳实践。测试通过 Mock `MessageBus` 来验证业务逻辑的“意图”（即它尝试发送哪个 `msg_id`），而不是它“呈现的样子”（具体的文本）。这使得代码和测试都更加稳固和面向未来。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/runtime #comp/tests #scope/dx #task/domain/testing #task/object/acts #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有变更

我们将本次重构涉及的所有新文件和修改过的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/quipu-common/src/pyquipu/common/locales/zh/acts.json
packages/quipu-runtime/src/pyquipu/acts/
tests/runtime/conftest.py
tests/runtime/acts/
tests/runtime/test_parser_and_basic_acts.py
~~~~~

#### Acts 2: 提交变更

现在，我们创建一个内容详尽的提交，记录下本次重构的完整上下文和价值。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): use MessageBus for acts and increase test coverage

This commit refactors the entire `pyquipu.acts` module to eliminate hardcoded error strings and significantly improves test coverage and robustness.

Key changes include:

1.  **MessageBus Integration**: Replaced all hardcoded error strings in `ctx.fail("...")` calls with the `MessageBus` system (`bus.get("msg_id")`). This decouples business logic from UI text, improving maintainability and enabling future i18n.

2.  **New Locale File**: Created `acts.json` to centralize all user-facing messages from the runtime acts module.

3.  **Increased Test Coverage**: Added new test files (`test_refactor.py`, `test_shell.py`, `test_memory.py`) with comprehensive unit tests for previously low-coverage modules.

4.  **Robust Test Assertions**: Updated all relevant tests to assert against semantic `msg_id`s instead of fragile, hardcoded UI strings by mocking `bus.get`.

5.  **Bug Fixes**:
    - Fixed an overly broad exception catch in `acts/shell.py` that was masking the true cause of failures.
    - Restored all act docstrings that were accidentally removed, fixing the `quipu run --list-acts` command.
~~~~~
