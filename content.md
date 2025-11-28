好的，我们已经完成了一次从性能瓶颈分析到架构重构的完整迭代。现在，我们将把所有这些成果——性能优化、架构改进以及所有相关的 Bug 修复——打包成一个单一的、高质量的 Git 提交。

## [COMMIT] fix(cli): 全面重构 TUI 以解决滚动卡顿和视觉伪影

### 用户需求
彻底解决 TUI 在快速滚动历史列表时遇到的严重性能问题和一系列视觉缺陷，包括 UI 卡顿、内容渲染延迟、旧内容残留 (Ghosting)、以及 Header 与光标位置不同步等问题，并将其底层实现重构为更健壮、可维护的架构。

### 评论
这是一次对 TUI 核心交互体验的全面重构。通过引入一个经过性能优化的显式状态机，我们不仅从根本上解决了高频事件导致的渲染瓶颈，还将原本分散、混乱的 UI 管理逻辑变得清晰、可预测。这次修改将 TUI 从一个功能原型，提升为了一个具备流畅、专业、响应迅速交互表现的健壮工具。

### 目标
1.  **实现极致流畅滚动**: 彻底解决了快速滚动时因 UI 阻塞导致的所有卡顿问题。
2.  **提供即时、一致的反馈**: 滚动时，Header 和摘要占位符能够实时、同步地更新。
3.  **消除所有视觉错误**:
    *   修复了切换节点时旧内容“一闪而过”的重影问题。
    *   修复了 TUI 启动时 Header 未能正确初始化的问题。
    *   修复了所有相关的 CSS 语法和逻辑错误。
4.  **建立健壮的架构**: 将内容视图的管理逻辑重构为一个显式的、高性能的有限状态机，极大地提升了代码的可读性和可维护性。
5.  **代码提交**: 将所有相关改进作为一个原子性提交，永久记录到版本历史中。

### 基本原理
本次优化的最终架构是一个**高性能状态机**，它区分了“状态进入”和“状态内更新”：
1.  **状态切换 (State Entry)**: 当从一个状态切换到另一个时（例如 `SHOWING_CONTENT` -> `LOADING`），状态机会执行所有必要的一次性、重量级设置（如修改 CSS 类、切换 `display` 属性）。
2.  **状态内更新 (Intra-State Update)**: 当在一个状态内接收到重复事件时（例如在 `LOADING` 状态下连续滚动），状态机仅调用一个轻量级的 `_update_loading_preview` 方法，该方法只更新 `Static` 组件的文本，避免了所有冗余的、昂贵的 UI 操作。

这个模式结合了状态机逻辑上的清晰性与针对性优化的性能，并辅以双组件（`Static`+`Markdown`）切换策略，确保了 Textual 的事件循环始终保持畅通。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high
#comp/cli #concept/ui #scope/core #scope/ux #scope/dx
#ai/brainstorm
#task/domain/ui #task/object/tui-refactor #task.action/performance-tuning #task/state/end #task/status/completed

---

### Script

#### Acts 1: 将所有相关的变更添加到暂存区

我们将把对 `tui.py` 和 `tui.css` 的所有修改都添加到 Git 的暂存区。

~~~~~act
git_add
packages/quipu-cli/src/quipu/cli/tui.py
packages/quipu-cli/src/quipu/cli/tui.css
~~~~~

#### Acts 2: 创建一个内容详尽的 Git 提交

最后，我们创建一个 Git 提交，详细记录这次重要的重构和优化。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(cli): overhaul TUI with performant state machine

This commit comprehensively refactors the TUI content view to fix severe performance issues and visual glitches during rapid scrolling, replacing the previous ad-hoc logic with a robust, performant finite state machine.

The key architectural change is a state machine that distinguishes between "State Entry" and "Intra-State Update":
- On state entry (e.g., transitioning from SHOWING_CONTENT to LOADING), heavy, one-time UI setup is performed (toggling CSS classes, widget visibility).
- For intra-state updates (e.g., continuous scrolling within the LOADING state), only a lightweight `_update_loading_preview` function is called to refresh text in Static widgets, avoiding all redundant, expensive operations.

This new architecture resolves a cascade of issues:
- **Performance**: Eliminates UI lag during fast scrolling by preventing redundant UI setup and leveraging a lightweight Static widget for high-frequency updates.
- **Ghosting**: Fixes visual artifacts where stale content would flash by explicitly clearing the Markdown widget when it's hidden.
- **State Sync**: Ensures the header bar updates in real-time with the cursor.
- **Initialization**: Corrects the initial state of the header on app startup.
- **Maintainability**: Centralizes all view logic into a single `_set_state` method, making the component's behavior predictable and easier to reason about.
- **Bugs**: Fixes a CSS syntax error and a stray decorator bug introduced during intermediate refactoring steps.
~~~~~
