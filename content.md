## [WIP] fix: 修复 Application 与 Integration 测试中的假设错误

### 错误分析
1.  **`tests/application/test_controller.py`**:
    *   **Patch 目标错误**: `pyquipu.application.controller` 模块直接导入并实例化了 `Executor` 类，而不是调用 `create_executor` 工厂函数。因此 `patch("...create_executor")` 抛出了 `AttributeError`。
    *   **逻辑假设错误**: `Controller` 源码中并未显式调用 `engine.align()`（这通常由 Factory 处理），但测试却断言了该调用。
    *   **Mock 配置缺失**: `_prepare_workspace` 方法依赖 `engine.git_db.get_tree_hash()` 和 `engine.current_node`，Mock 对象需要配置这些属性以避免逻辑错误。

2.  **`tests/integration/test_cli_workflow.py`**:
    *   **消息 ID 不匹配**: 实际代码使用的 Message ID 与测试预期的不一致。
        *   Discard: 预期 `workspace.error.noHistory`，实际 `workspace.discard.error.noHistory`。
        *   Checkout: 预期 `navigation.checkout.success.alreadyOnState`，实际 `navigation.checkout.info.noAction`。

### 用户需求
修正测试代码，使其与实际的实现细节保持一致，确保 CI 通过。

### 目标
1.  修改 `test_controller.py`：正确 Patch `Executor` 类，移除 `align` 断言，完善 Mock 配置。
2.  修改 `test_cli_workflow.py`：更新 Message ID 断言以匹配源码。

### 基本原理
测试必须反映真实的实现。当重构改变了实现细节（如类实例化方式、消息 ID）时，测试必须随之更新。使用 `patch` 类而不是函数可以正确拦截构造函数的调用。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #ai/instruct #task/domain/testing #task/object/test-suite #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 `test_controller.py`

修正 Patch 目标，配置 Mock Engine 属性，移除无效断言。

~~~~~act
write_file tests/application/test_controller.py
~~~~~
~~~~~python
from unittest.mock import ANY, MagicMock, patch

import pytest
from pyquipu.application.controller import run_quipu
from pyquipu.interfaces.exceptions import ExecutionError


class TestControllerUnit:
    """
    对 Application 层 Controller 的纯单元测试。
    使用 Mock 替代真实的 Engine 和 Runtime，仅验证编排逻辑。
    """

    def test_run_quipu_success(self, tmp_path, mock_engine, mock_runtime):
        """测试正常执行流程：应正确初始化组件并按顺序调用。"""
        
        plan_content = """
```act
echo
```
```text
hello
```
"""
        # 配置 Mock Engine 的状态以通过 _prepare_workspace 检查
        # 模拟当前是干净状态 (clean)
        mock_engine.git_db.get_tree_hash.return_value = "hash_123"
        mock_node = MagicMock()
        mock_node.output_tree = "hash_123"
        mock_engine.current_node = mock_node
        mock_engine.history_graph = { "hash_123": mock_node }

        # Patch 工厂函数和 Executor 类
        # 注意：controller 直接导入了 Executor 类，所以我们要 patch 这个类
        with patch("pyquipu.application.controller.create_engine", return_value=mock_engine) as mk_eng_fac, \
             patch("pyquipu.application.controller.Executor", return_value=mock_runtime) as mk_exec_cls:

            # 执行
            result = run_quipu(
                content=plan_content,
                work_dir=tmp_path,
                yolo=True,
                confirmation_handler=lambda *a: True
            )

            # 验证结果
            assert result.success is True
            assert result.exit_code == 0

            # 验证交互
            mk_eng_fac.assert_called_once_with(tmp_path)
            # Executor 类被实例化
            mk_exec_cls.assert_called_once()
            
            # 验证编排顺序
            # 1. _prepare_workspace 调用了 get_tree_hash
            mock_engine.git_db.get_tree_hash.assert_called()
            
            # 2. Executor 执行
            mock_runtime.execute.assert_called_once()
            
            # 3. 最后生成 Plan Node
            mock_engine.create_plan_node.assert_called_once()

    def test_run_quipu_execution_error(self, tmp_path, mock_engine, mock_runtime):
        """测试执行器抛出异常时的错误处理流程。"""
        plan_content = """
```act
fail_act
```
"""
        # 配置 Mock Engine
        mock_engine.git_db.get_tree_hash.return_value = "hash_123"
        mock_engine.current_node = MagicMock()
        mock_engine.current_node.output_tree = "hash_123"

        with patch("pyquipu.application.controller.create_engine", return_value=mock_engine), \
             patch("pyquipu.application.controller.Executor", return_value=mock_runtime):

            # 模拟 Runtime 抛出业务异常
            mock_runtime.execute.side_effect = ExecutionError("Task failed successfully")

            result = run_quipu(
                content=plan_content,
                work_dir=tmp_path,
                yolo=True,
                confirmation_handler=lambda *a: True
            )

            # 验证错误被捕获并封装到 Result 中
            assert result.success is False
            assert result.exit_code == 1
            assert result.message == "run.error.execution"
            assert isinstance(result.error, ExecutionError)
            assert "Task failed successfully" in str(result.error)

    def test_run_quipu_empty_plan(self, tmp_path, mock_engine, mock_runtime):
        """测试空计划的处理。"""
        plan_content = "Just some text, no acts."
        
        # 配置 Mock Engine
        mock_engine.git_db.get_tree_hash.return_value = "hash_123"
        mock_engine.current_node = MagicMock()
        mock_engine.current_node.output_tree = "hash_123"

        with patch("pyquipu.application.controller.create_engine", return_value=mock_engine), \
             patch("pyquipu.application.controller.Executor", return_value=mock_runtime):

            result = run_quipu(
                content=plan_content,
                work_dir=tmp_path,
                yolo=True,
                confirmation_handler=lambda *a: True
            )

            # 空计划通常不算失败，但也没有副作用
            assert result.success is True
            assert result.exit_code == 0
            assert result.message == "axon.warning.noStatements"
            
            # 验证没有调用 execute
            mock_runtime.execute.assert_not_called()
~~~~~

#### Acts 2: 修正 `test_cli_workflow.py`

更新消息 ID 断言以匹配源码实现。

~~~~~act
patch_file tests/integration/test_cli_workflow.py
~~~~~
~~~~~
    def test_cli_discard_no_history(self, workspace):
        """测试 `discard` 命令在没有历史记录时的行为"""
        from unittest.mock import MagicMock
        mock_bus = MagicMock()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pyquipu.cli.commands.workspace.bus", mock_bus)
            result = runner.invoke(app, ["discard", "-f", "-w", str(workspace)])
            assert result.exit_code == 1
            mock_bus.error.assert_called_with("workspace.error.noHistory")
~~~~~
~~~~~python
    def test_cli_discard_no_history(self, workspace):
        """测试 `discard` 命令在没有历史记录时的行为"""
        from unittest.mock import MagicMock
        mock_bus = MagicMock()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pyquipu.cli.commands.workspace.bus", mock_bus)
            result = runner.invoke(app, ["discard", "-f", "-w", str(workspace)])
            assert result.exit_code == 1
            mock_bus.error.assert_called_with("workspace.discard.error.noHistory")
~~~~~

~~~~~act
patch_file tests/integration/test_cli_workflow.py
~~~~~
~~~~~
    def test_cli_checkout_already_on_state(self, populated_workspace):
        """Test checking out to the current state does nothing."""
        workspace, _, hash_b = populated_workspace

        from unittest.mock import MagicMock
        mock_bus = MagicMock()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pyquipu.cli.commands.navigation.bus", mock_bus)
            
            result = runner.invoke(app, ["checkout", hash_b[:8], "--work-dir", str(workspace), "--force"])

            assert result.exit_code == 0
            mock_bus.success.assert_called_with("navigation.checkout.success.alreadyOnState")
~~~~~
~~~~~python
    def test_cli_checkout_already_on_state(self, populated_workspace):
        """Test checking out to the current state does nothing."""
        workspace, _, hash_b = populated_workspace

        from unittest.mock import MagicMock
        mock_bus = MagicMock()
        with pytest.MonkeyPatch.context() as m:
            m.setattr("pyquipu.cli.commands.navigation.bus", mock_bus)
            
            result = runner.invoke(app, ["checkout", hash_b[:8], "--work-dir", str(workspace), "--force"])

            assert result.exit_code == 0
            mock_bus.success.assert_called_with("navigation.checkout.info.noAction", short_hash=ANY)
~~~~~

### 下一步建议
运行测试确认修复有效。如果全绿，则立即进入 **第三阶段：引擎层净化**，清理 `tests/engine/sqlite/test_writer.py` 和 `tests/integration/test_idempotent_node.py` 中的不当依赖。
