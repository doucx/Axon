分析正确。测试失败暴露了一个在 Python 测试中非常经典且微妙的 `monkeypatch` 陷阱。

### 错误分析

**根本原因**: 测试失败的核心在于 `monkeypatch` 的目标不正确。当 `quipu-runtime` 下的各个模块 (如 `acts/basic.py`, `runtime/executor.py`) 启动时，它们会执行 `from quipu.common.messaging import bus`。这个操作会在每个模块自己的命名空间里创建一个对原始 `bus` 对象的**本地引用**。

我们在 `tests/runtime/conftest.py` 中的 `mock_runtime_bus` fixture 尝试通过 `monkeypatch.setattr("quipu.common.messaging.bus", m_bus)` 来替换 `bus`。这确实成功地替换了 `quipu.common.messaging` 模块中的 `bus` 对象，但**它无法影响那些已经创建了本地引用的其他模块**。因此，被测试的代码仍在调用原始的、未被 mock 的 `bus` 对象，导致我们的 `MagicMock` 实例从未被调用，从而引发 `AssertionError: expected call not found`。

**次要原因**: 在 `tests/runtime/acts/test_read.py` 的 `test_search_scoped_path` 测试中，存在一个错误的 `assert False` 占位符，这是我在上一步生成代码时的疏忽。

### 解决方案

1.  **修正 Monkeypatch 目标**: 我们必须在每个被测试模块的命名空间中**分别**替换 `bus` 对象。最干净的方法是在 `tests/runtime/conftest.py` 的 `mock_runtime_bus` fixture 中，定义一个所有需要 patch 的模块列表，然后循环应用 `monkeypatch`。这样，无论哪个测试运行，都能确保它所依赖的模块使用的是我们注入的 `MagicMock` 实例。

2.  **修复损坏的测试**: 移除 `test_search_scoped_path` 中的 `assert False`，并替换为正确的断言逻辑。

## [WIP] fix: 修正 runtime 测试中的 monkeypatch 目标

### 用户需求
修复 `quipu-runtime` 测试套件中的 12 个失败的测试用例。

### 评论
这次修复是一个很好的实践，它加深了对 Python 模块导入和 `pytest` `monkeypatch` 机制的理解。通过在 `conftest.py` 中建立一个集中式的、多目标的 patch fixture，我们不仅解决了当前的 bug，还为未来 `runtime` 模块的扩展建立了一个健壮的测试基础。

### 目标
1.  修改 `tests/runtime/conftest.py`，使其能够正确地 patch `quipu-runtime` 所有子模块中的 `bus` 实例。
2.  修正 `tests/runtime/acts/test_read.py` 中 `test_search_scoped_path` 的断言逻辑。
3.  确保所有 `runtime` 测试都能通过。

### 基本原理
利用 `pytest` 的 `monkeypatch` fixture，我们将 `bus` 对象在其被查找的位置（即各个 `acts/*.py` 和 `runtime/*.py` 模块）替换为一个 `unittest.mock.MagicMock` 实例。这样，所有对 `bus` 的调用都会被这个 mock 对象捕获，我们就可以在测试中对这些调用进行断言，从而验证业务逻辑的正确性，而无需关心实际的输出内容。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/runtime #scope/dx #ai/instruct #task/domain/testing #task/object/monkeypatch #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `conftest.py` 的 Monkeypatch 逻辑

这是最关键的修复。我们将更新 `mock_runtime_bus` fixture 以 patch 所有正确的目标。

~~~~~act
write_file
tests/runtime/conftest.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from quipu.runtime.executor import Executor
from quipu.acts.basic import register as register_basic_acts


@pytest.fixture(autouse=True)
def mock_runtime_bus(monkeypatch):
    """
    自动 patch 所有 runtime 模块中导入的 'bus' 实例。

    这是解决 'from ... import ...' 语句导致的 patch 问题的关键。
    我们必须在每个使用 'bus' 的模块的命名空间中替换它。
    """
    m_bus = MagicMock()
    patch_targets = [
        "quipu.runtime.executor.bus",
        "quipu.runtime.plugin_loader.bus",
        "quipu.acts.basic.bus",
        "quipu.acts.check.bus",
        "quipu.acts.git.bus",
        "quipu.acts.memory.bus",
        "quipu.acts.read.bus",
        "quipu.acts.refactor.bus",
        "quipu.acts.shell.bus",
    ]
    for target in patch_targets:
        monkeypatch.setattr(target, m_bus, raising=False)  # raising=False 避免模块不存在时报错
    return m_bus


@pytest.fixture
def executor(tmp_path: Path) -> Executor:
    """
    为运行时测试提供一个隔离的 Executor 实例。
    - 在独立的临时目录 (tmp_path) 中运行。
    - 自动注册基础 acts。
    - 默认以非交互模式 (yolo=True) 运行。
    """
    # yolo=True 避免在测试中出现交互式提示，这对于非 CLI 测试至关重要
    instance = Executor(root_dir=tmp_path, yolo=True)
    # 自动注册基础指令，因为大多数测试都依赖它们
    register_basic_acts(instance)
    return instance


@pytest.fixture
def isolated_vault(executor: Executor) -> Path:
    """
    提供 Executor 实例的根工作目录。
    这是一个便利性的 fixture，用于需要直接操作文件系统的测试。
    """
    return executor.root_dir
~~~~~

#### Acts 2: 修复 `test_read.py` 中的损坏测试

现在，修正 `test_search_scoped_path` 中的断言逻辑。

~~~~~act
patch_file
tests/runtime/acts/test_read.py
~~~~~
~~~~~python
    def test_search_scoped_path(self, executor: Executor, isolated_vault: Path, monkeypatch, mock_runtime_bus):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        (isolated_vault / "target.txt").write_text("target_function", encoding="utf-8")
        src_dir = isolated_vault / "src"
        src_dir.mkdir()
        (src_dir / "inner.txt").write_text("target_function", encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["target_function", "--path", "src"])

        assert mock_runtime_bus.data.called
        stdout = mock_runtime_bus.data.call_args[0][0]

        # After the fix, the path should be relative to the root
        assert str(Path("src") / "inner.txt") in stdout
        assert str(isolated_vault / "target.txt") not in stdout
        assert "target.txt:1:target_function" not in stdout
~~~~~
~~~~~python
    def test_search_scoped_path(self, executor: Executor, isolated_vault: Path, monkeypatch, mock_runtime_bus):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        (isolated_vault / "target.txt").write_text("target_function", encoding="utf-8")
        src_dir = isolated_vault / "src"
        src_dir.mkdir()
        (src_dir / "inner.txt").write_text("target_function", encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["target_function", "--path", "src"])

        assert mock_runtime_bus.data.called
        stdout = mock_runtime_bus.data.call_args[0][0]

        # After the fix, the path should be relative to the root
        assert str(Path("src") / "inner.txt") in stdout
        assert "target.txt" not in stdout
~~~~~

### 下一步建议
我们已经应用了核心修复。现在应该重新运行 `pytest tests/runtime/` 以验证所有测试是否都已通过。如果全部通过，`quipu-runtime` 到 `MessageBus` 的迁移工作就正式完成了。
