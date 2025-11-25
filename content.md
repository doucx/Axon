# refactor 收束 CLI 逻辑 (CLI Convergence)

## 目标
将 `controller.py` 重命名为 `cli_controller.py`，并更新所有相关引用。此操作明确了该模块作为 CLI 胶水层的职责，完成了第一阶段逻辑解耦的最后一步。

## 基本原理
此操作属于 Quipu 重构计划的 **步骤 1.4**。
`controller.py` 是系统中唯一被允许同时依赖引擎层 (`eng_*`) 和运行时层 (`rt_*`) 的模块。通过添加 `cli_` 前缀，我们在命名上将其归类为 CLI 层的一部分，为后续物理迁移到 `packages/quipu-cli` 扫清障碍。

## 标签
 #refactor #cli #core

---

## Script

### Act 1: 重命名 Controller

将核心控制器文件重命名以反映其 CLI 胶水层的身份。

~~~~~act
move_file core/controller.py core/cli_controller.py
~~~~~

### Act 2: 更新 main.py 引用

修正 `main.py` 中对控制器的引用。

~~~~~act
replace main.py
~~~~~

~~~~~python
from core.controller import run_axon, find_project_root
~~~~~

~~~~~python
from core.cli_controller import run_axon, find_project_root
~~~~~

### Act 3: 更新 Head 和 Root 测试引用

修正 `tests/test_head_and_root.py` 中的引用。

~~~~~act
replace tests/test_head_and_root.py
~~~~~

~~~~~python
from core.controller import find_project_root
~~~~~

~~~~~python
from core.cli_controller import find_project_root
~~~~~

### Act 4: 更新幂等性测试引用

修正 `tests/test_idempotent_node.py` 中的引用。

~~~~~act
replace tests/test_idempotent_node.py
~~~~~

~~~~~python
from core.controller import run_axon
~~~~~

~~~~~python
from core.cli_controller import run_axon
~~~~~

### Act 5: 更新集成测试 V2 引用

修正 `tests/test_integration_v2.py` 中的引用。

~~~~~act
replace tests/test_integration_v2.py
~~~~~

~~~~~python
from core.controller import run_axon, AxonResult
~~~~~

~~~~~python
from core.cli_controller import run_axon, AxonResult
~~~~~

### Act 6: 更新插件测试引用

修正 `tests/test_plugins.py` 中的引用。

~~~~~act
replace tests/test_plugins.py
~~~~~

~~~~~python
from core.controller import find_project_root  # 从 Controller 导入辅助函数
~~~~~

~~~~~python
from core.cli_controller import find_project_root  # 从 Controller 导入辅助函数
~~~~~

### Act 7: 更新根目录不变性测试引用

修正 `tests/test_root_invariance.py` 中的引用。

~~~~~act
replace tests/test_root_invariance.py
~~~~~

~~~~~python
from core.controller import run_axon
~~~~~

~~~~~python
from core.cli_controller import run_axon
~~~~~

### Act 8: 验证 CLI 功能

运行 `test_integration_v2.py`，这是最依赖 Controller 逻辑的测试集。

~~~~~act
run_command
~~~~~

~~~~~bash
pytest tests/test_integration_v2.py
~~~~~