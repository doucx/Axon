好的，我们已经成功完成了 `pyquipu-application` 包的提取和重构，并且所有测试都已通过。现在是时候将这些重要的架构改进固化到版本历史中了。

我将生成一个 `[COMMIT]` 计划来完成这次提交。

## [COMMIT] refactor(architecture): Extract core logic into pyquipu-application package

### 用户需求
将 `pyquipu-cli` 中与 UI 无关的核心业务逻辑提取到一个新的、可复用的 `pyquipu-application` 包中。此举旨在消除表现层与业务逻辑的耦合，为未来创建 `pyquipu-webapi` 等其他前端接口提供一个干净、独立的业务逻辑层。

### 评论
这是一次 foundational 的架构重构。通过这次提取，我们建立了一个清晰、单向的依赖流：`frontends (cli, webapi)` -> `application` -> `engine/runtime`。这不仅遵循了 DRY 和单一职责原则，还极大地提升了核心逻辑的可测试性和整个系统的可扩展性。

### 目标
1.  成功创建 `pyquipu-application` 包，并作为核心业务逻辑的容器。
2.  将 `controller`, `factory`, `plugin_manager`, 和 `utils` 模块从 CLI 迁移至新包。
3.  通过依赖注入（`confirmation_handler`）彻底解耦核心逻辑与 `Typer` 等 CLI UI 框架。
4.  更新 `pyquipu-cli` 包，使其成为 `pyquipu-application` 的一个纯粹客户端。
5.  修复所有因路径和 API 签名变更而中断的测试，确保 CI 流程恢复正常。
6.  将这一系列重构工作作为一个原子性的、有意义的提交记录到版本历史中。

### 基本原理
我们采取了“直接创建，一次性迁移”的策略。通过物理上分离代码到新的包，我们强制性地解决了模块间的非法依赖。测试驱动的修复过程确保了在重连 CLI 的过程中没有引入回归。最终，我们得到了一个更加健壮和模块化的系统架构。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/application #comp/build #comp/tests #scope/core #scope/api #task/domain/core #task/object/package-structure #task/action/creation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交所有重构变更

我们将暂存所有已修改和新创建的文件，并创建一个内容详尽的提交来记录这次架构重构。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(architecture): Extract core logic into pyquipu-application

This commit introduces a new `pyquipu-application` package to house the core business logic, decoupling it from the `pyquipu-cli` presentation layer.

Key changes:
- Created the `pyquipu-application` package, which now contains the `QuipuApplication` controller, the `create_engine` factory, the plugin manager, and utility functions.
- The `QuipuApplication` controller is now UI-agnostic. UI-specific dependencies like `typer` for user confirmation have been removed and replaced with a dependency-injected `confirmation_handler`.
- `pyquipu-cli` now depends on `pyquipu-application` and acts as a pure client, responsible only for parsing command-line arguments and rendering output.
- All affected tests across the engine, runtime, and integration suites have been updated to reflect the new module paths and API signatures.

This refactoring establishes a clear, unidirectional dependency flow and enables the reuse of the core application logic for future frontends, such as the planned `pyquipu-webapi`.
~~~~~

### 下一步建议
架构重构已经完成并提交。现在，我们可以正式开始 `pyquipu-webapi` 的开发了。第一步将是创建 `packages/quipu-webapi` 的包结构，并让它依赖于我们刚刚创建的 `pyquipu-application`。
