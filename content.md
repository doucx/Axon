好的，我们已经成功完成了 `quipu-engine` 的消息迁移，并通过了测试。现在，我们将把这一阶段的成果固化为一个原子性的提交。

## [COMMIT] refactor(engine): 将 engine 模块的用户反馈迁移到 MessageBus

### 用户需求
将 `quipu-engine` 包中所有面向用户的 `logging` 调用迁移到 `MessageBus` 系统。这要求区分开发者诊断日志和用户反馈信息，并将后者集中到新的 `engine.json` 消息域中进行管理。

### 评论
这是对 `MessageBus` 架构的一次关键验证，证明了其解耦能力可以从应用层的 `cli` 延伸到核心的 `engine` 模块。通过这次重构，我们不仅统一了用户反馈的出口，还通过保留必要的开发者日志，在不牺牲可调试性的前提下提升了代码的整洁度和可测试性。

### 目标
1.  已创建 `locales/zh/engine.json` 文件来管理 `engine` 模块的消息。
2.  已将 `quipu-engine` 中所有面向用户的 `info`, `warning`, `error` 日志调用替换为对应的 `bus` 调用。
3.  已保留所有用于内部诊断的 `debug` 日志和底层错误日志。
4.  已更新相关测试，使用 `mock_bus` 进行验证。
5.  创建一个 Git 提交，将此项架构改进持久化。

### 基本原理
我们遵循关注点分离的原则，将用户界面（UI）的关注点（消息内容、格式）从 `engine` 的核心逻辑中剥离。`engine.json` 的创建实现了消息资源的物理隔离，而 `bus` 的使用则在代码层面实现了逻辑解耦。这使得 `engine` 模块只负责发出语义信号（如 `engine.state.success.aligned`），而不用关心这些信号最终如何呈现给用户。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/locales #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/message-bus #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

现在，我们将所有相关的修改添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
locales/zh/engine.json
packages/quipu-engine/src/quipu/engine/config.py
packages/quipu-engine/src/quipu/engine/git_db.py
packages/quipu-engine/src/quipu/engine/git_object_storage.py
packages/quipu-engine/src/quipu/engine/hydrator.py
packages/quipu-engine/src/quipu/engine/sqlite_db.py
packages/quipu-engine/src/quipu/engine/sqlite_storage.py
packages/quipu-engine/src/quipu/engine/state_machine.py
tests/engine/test_git_db.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): migrate user-facing logs to MessageBus

Replaces user-facing `logging` calls within the `quipu-engine` package with semantic `MessageBus` calls, standardizing all user feedback channels.

This commit completes Phase 3 of the MessageBus refactoring initiative. It carefully distinguishes between:
1.  User-facing feedback (info, warnings, errors), which is now emitted via the `bus`.
2.  Internal diagnostic logs for developers (`debug` level or low-level exceptions), which remain as `logging` calls.

Key changes:
- A new `locales/zh/engine.json` is created to house all engine-related user messages, decoupling them from other domains.
- All relevant source files in `quipu-engine` are updated to import and use the global `bus` instance.
- Tests are updated to mock the `bus` for verifying outputs, making them more robust and less reliant on specific string matching.
~~~~~

### 下一步建议
我们已经成功完成了 `MessageBus` 架构重构的三个核心阶段。整个系统的主要输出路径现在都已统一。

下一步是 **Phase 4: 清理与最终审查**。

我建议进行一次全局代码审查，专门查找项目中是否还残留有未被迁移的 `typer.secho`, `typer.echo` 或面向用户的 `print` 调用。完成这次审查后，整个 `MessageBus` 重构任务就可以宣告正式完成了。
