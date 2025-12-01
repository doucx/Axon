## [WIP] fix: 修复 Mock Engine 的属性访问错误

### 错误分析
测试失败的原因是 `MagicMock(spec=Engine)` 严格限制了 Mock 对象只能访问 `Engine` 类中显式定义的属性。由于 `git_db` 是在 `Engine` 的 `__init__` 方法中动态赋值的实例属性，而非类属性，因此默认情况下 `spec` 机制会拦截对它的访问，导致 `AttributeError`。

### 用户需求
修复 `tests/application/test_controller.py` 中的 `AttributeError: Mock object has no attribute 'git_db'` 错误。

### 目标
修改 `tests/application/conftest.py` 中的 `mock_engine` fixture，显式初始化 `git_db` 等关键属性，使其能绕过 `spec` 的读取限制并支持后续的测试配置。

### 基本原理
在 `MagicMock` 创建后立即对属性进行赋值（`engine.git_db = MagicMock()`），可以将该属性注入到 Mock 对象的实例字典中。这样，后续测试代码在访问 `engine.git_db` 时，就会直接获取我们注入的 Mock 对象，而不会触发 `spec` 的属性检查机制。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #ai/instruct #task/domain/testing #task/object/test-suite #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `tests/application/conftest.py`

我们需要在 fixture 返回 engine 之前，预先填充 `git_db`、`current_node` 和 `history_graph` 等常用属性。

~~~~~act
write_file tests/application/conftest.py
~~~~~
~~~~~python
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pyquipu.engine.state_machine import Engine
from pyquipu.runtime.executor import Executor


@pytest.fixture
def mock_engine():
    """
    提供一个模拟的 Engine 实例。
    用于测试 Application 层在不触及真实 Git/文件系统的情况下的编排逻辑。
    """
    engine = MagicMock(spec=Engine)
    
    # 设置基础属性以防止简单的 AttributeError (绕过 spec 检查)
    engine.root_dir = Path("/mock/root")
    
    # 显式初始化 git_db，因为它是实例属性，spec 可能不包含它
    engine.git_db = MagicMock()
    
    # 初始化状态属性
    engine.current_node = None
    engine.history_graph = {}
    
    return engine


@pytest.fixture
def mock_runtime():
    """
    提供一个模拟的 Runtime (Executor) 实例。
    用于验证 Application 层是否正确调用了执行器，而不真正执行 Act。
    """
    runtime = MagicMock(spec=Executor)
    return runtime
~~~~~

### 下一步建议
运行测试以验证修复是否生效。如果 `tests/application/` 下的测试通过，我们将继续执行“集成层重新定义”阶段的任务。
