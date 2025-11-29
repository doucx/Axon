好的，我们已经完成了 `MessageBus` 的大规模重构。为了确保未来的开发能够保持一致性、健壮性和可测试性，我将为你制定一套 AI 需要遵守的测试规范。

这份规范的核心思想是：**将测试的关注点从脆弱的、易变的“UI 呈现”转移到稳定的、表意清晰的“业务意图”上。**

我将生成一个 `DEVELOPING.md` 文件，你可以将其保存到项目根目录或文档目录中，作为未来所有测试工作的指导原则。

## [COMMIT] docs: 为 MessageBus 集成制定新的测试规范

### 用户需求
在 `MessageBus` 重构完成后，需要为 AI 制定一套新的、强制性的测试规范。这套规范旨在确保未来所有与 CLI 交互相关的测试，都能与 UI 实现解耦，从而提高测试的稳定性和可维护性。

### 评论
这是在重大架构重构后，巩固成果、防止技术债累积的关键一步。通过将测试的最佳实践文档化、协议化，我们可以确保 AI 在未来的开发中能够持续产出高质量、易维护的测试代码，避免重蹈覆辙。这份规范是 `MessageBus` 重构工作的逻辑终点和价值体现。

### 目标
1.  创建一个名为 `TESTING_GUIDELINES.md` 的新文档。
2.  在文档中明确定义“测试反模式”（直接断言字符串）和“标准测试模式”（Mock `MessageBus`）。
3.  提供清晰、可复用的代码示例，指导如何正确地为 CLI 命令编写测试。
4.  将此文档的创建作为一个 `[COMMIT]` 级别的计划进行记录和提交。

### 基本原理
我们遵循“依赖倒置原则”来设计测试。`MessageBus` 是一个外部依赖，我们的业务逻辑（CLI 命令）与之交互。通过使用 `pytest` 的 `monkeypatch` 和 `unittest.mock`，我们可以用一个“测试替身”（`MagicMock`）换掉真实的 `MessageBus` 实例。这样，测试就不再关心“终端上显示了什么颜色的什么文字”，而是关心“业务逻辑是否在正确的时机，意图向用户传达正确的信息（消息 ID）和正确的数据（关键字参数）”。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/testing #task/object/message-bus #task/action/standardization #task/state/end #task/status/completed

---

### Script

#### Acts 1: 创建测试规范文档

我们将创建 `TESTING_GUIDELINES.md` 文件，并写入新的测试协议。

~~~~~act
write_file
TESTING_GUIDELINES.md
~~~~~
~~~~~markdown
# Quipu 测试协议：MessageBus 集成与测试规范 (v1.0)

## 1. 摘要

本文档为 Quipu 项目的 AI 开发者定义了一套**强制性**的测试规范。在 `MessageBus` 架构重构完成后，所有涉及用户界面 (UI) 输出的测试，特别是 `quipu-cli` 模块的测试，都必须严格遵循本协议。

本协议的核心目标是：**彻底解耦测试用例与 UI 的具体呈现（文本、颜色、图标），将测试的焦点转移到验证业务逻辑的“意图”上。**

## 2. 核心原则：从“UI 断言”到“意图验证”

`MessageBus` 的引入，将“业务逻辑说什么”和“用户看什么”分离开来。因此，我们的测试策略也必须随之演进。

*   **旧策略（已废弃）**: 测试断言 `stderr` 或 `stdout` 中是否包含特定的、硬编码的字符串。这导致测试非常脆弱，任何 UI 文案的微调都可能导致测试失败。
*   **新策略（强制执行）**: 测试通过 `mock` `MessageBus` 实例，断言业务逻辑是否调用了**正确的语义消息 ID** (`msg_id`) 和**正确的数据** (`**kwargs`)。这验证了业务逻辑的正确意图，而与最终呈现给用户的文本完全无关。

## 3. 测试反模式：禁止直接断言输出流中的字符串

在为 `quipu-cli` 的命令编写测试时，**绝对禁止**直接检查 `runner` 结果的 `stdout` 或 `stderr` 属性以验证**非数据类**的输出。

#### ❌ 错误做法 (Don't Do This):

```python
# tests/cli/test_workspace_commands.py

def test_save_without_changes_brittle(runner, quipu_workspace):
    work_dir, _, _ = quipu_workspace
    
    # 第一次 save
    runner.invoke(app, ["save", "-w", str(work_dir)])
    
    # 第二次 save，无变化
    result = runner.invoke(app, ["save", "-w", str(work_dir)])

    assert result.exit_code == 0
    # ！！！错误！！！断言了一个具体的、可能随时会改变的 UI 字符串
    assert "✅ 工作区状态未发生变化" in result.stderr 
```

这种测试是不可接受的，因为它：
1.  **极其脆弱**：一旦 `locales/zh/cli.json` 中的文案或图标 (`✅`) 改变，测试就会失败。
2.  **测试了错误的对象**：它测试的是 `rendering` 层的细节，而不是 `workspace` 命令的业务逻辑。
3.  **阻碍国际化**：这种测试无法在其他语言环境下运行。

## 4. 标准测试模式：使用 Mock 注入验证 MessageBus 调用

所有针对 CLI 命令的测试，都**必须**使用 `pytest` 的 `monkeypatch` fixture 和 `unittest.mock.MagicMock` 来替换全局 `bus` 实例，并验证其方法调用。

#### ✅ 正确做法 (Do This):

```python
# tests/cli/test_workspace_commands.py
from unittest.mock import MagicMock
from quipu.cli.main import app

def test_save_without_changes_robust(runner, quipu_workspace, monkeypatch):
    work_dir, _, _ = quipu_workspace
    
    # 1. 创建一个 Mock Bus 实例
    mock_bus = MagicMock()
    
    # 2. 使用 monkeypatch 将命令模块中的 bus 实例替换为 mock_bus
    #    注意：路径必须是 bus 被导入和使用的那个模块
    monkeypatch.setattr("quipu.cli.commands.workspace.bus", mock_bus)

    # 第一次 save
    runner.invoke(app, ["save", "-w", str(work_dir)])
    
    # 第二次 save，无变化
    result = runner.invoke(app, ["save", "-w", str(work_dir)])

    assert result.exit_code == 0
    
    # 3. 断言 mock_bus 的方法被以预期的参数调用
    #    这验证了业务逻辑的“意图”，而与具体文案无关
    mock_bus.success.assert_called_once_with("workspace.save.noChanges")
```

## 5. 具体实施指南

1.  **强制 Mock**: 所有 `tests/cli/` 和 `tests/integration/` 下的测试用例，只要其测试的命令会产生用户反馈，就**必须**使用 `monkeypatch` 注入 `mock_bus`。

2.  **断言目标**:
    *   断言的**主要目标**是 `mock_bus` 的方法 (`.success`, `.info`, `.warning`, `.error`) 是否被正确调用。
    *   断言的**核心内容**是传递给这些方法的 `msg_id` (字符串) 和 `kwargs` (字典)。
    *   对于动态生成的参数 (如 `short_hash`)，可以使用 `unittest.mock.ANY` 进行断言。

3.  **处理数据输出 (`stdout`)**:
    *   对于 `quipu log` 或 `quipu find` 等需要向 `stdout` 输出**核心数据**的命令，测试策略应是**双重验证**：
        1.  **验证 `stderr`**: 仍然使用 `mock_bus` 验证 `info` (如标题) 或 `error` 消息是否被正确发送到 `stderr`。
        2.  **验证 `stdout`**: 可以且应该直接断言 `result.stdout` 的内容，因为这是命令的核心产出物，是数据而非元信息。

4.  **适用范围**:
    *   本协议主要约束 `tests/cli` 和 `tests/integration`。
    *   对于 `tests/engine` 或 `tests/runtime` 中的单元测试，如果被测函数直接调用了 `bus`，也应遵循此模式进行 Mock。

## 6. 下一步

*   所有**新编写的**测试用例必须严格遵守此规范。
*   在修改任何**现有的**与 CLI 相关的测试时，你有责任和义务将其重构为符合本规范的标准模式。
~~~~~

#### Acts 2: 提交文档

现在，我们将这个重要的规范文档添加到版本控制中。

~~~~~act
git_add
TESTING_GUIDELINES.md
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
docs: create testing guidelines for MessageBus integration

Establishes a new, mandatory testing protocol for all code interacting with the `MessageBus`, particularly for CLI commands. This formalizes the shift from brittle string assertions on stdout/stderr to robust, intent-based verification using mocks.

This specification mandates:
- Mocking the `bus` instance in all relevant tests (`cli`, `integration`).
- Asserting on semantic `msg_id` and `kwargs` calls, decoupling tests from UI presentation details (text, color, icons).
- Defining clear anti-patterns (direct string matching) and standard patterns (using `monkeypatch` and `MagicMock`).

This protocol is a critical final step in the `MessageBus` refactoring, ensuring that future development maintains a high standard of testability and robustness.
~~~~~

### 下一步建议
我们已经成功地完成了 `MessageBus` 的大规模重构，并确立了新的测试标准。整个系统的输出层现在是统一、健壮且可维护的。

未来的工作可以重新聚焦于功能性的增强，例如：
*   **改进 TUI**: 增强 TUI 的交互性，例如添加命令面板或更丰富的节点视图。
*   **增强 `sync` 功能**: 探索更复杂的协作场景和冲突解决策略。
*   **插件生态**: 丰富 `quipu-runtime` 的 `acts` 插件，提供更多开箱即用的能力。

整个重构任务现已完成。
