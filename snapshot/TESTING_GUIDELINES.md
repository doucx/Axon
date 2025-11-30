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