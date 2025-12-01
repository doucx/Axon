## [WIP] fix: 修复集成测试中残留的旧工厂导入路径

### 用户需求
在运行测试时，`tests/integration/test_cli_workflow.py` 中的 `populated_workspace` fixture 仍然尝试导入已移动的 `pyquipu.cli.factory`，导致 `ModuleNotFoundError`。需要将其更新为新的 `pyquipu.application.factory` 路径。

### 目标
1.  修正 `tests/integration/test_cli_workflow.py` 中 `populated_workspace` fixture 内的导入语句。

### 基本原理
这是重构后的清理工作，确保测试代码与新的架构一致。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/refine #task/domain/testing #task/object/test-suite #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 `tests/integration/test_cli_workflow.py`

~~~~~act
patch_file tests/integration/test_cli_workflow.py
~~~~~
~~~~~python
    @pytest.fixture
    def populated_workspace(self, workspace):
        """
        Create a workspace with two distinct, non-overlapping history nodes.
        State A contains only a.txt.
        State B contains only b.txt.
        This fixture is backend-agnostic.
        """
        from pyquipu.cli.factory import create_engine

        # State A: Create a.txt
        plan_a = "```act\nwrite_file a.txt\n```\n```content\nState A\n```"
~~~~~
~~~~~python
    @pytest.fixture
    def populated_workspace(self, workspace):
        """
        Create a workspace with two distinct, non-overlapping history nodes.
        State A contains only a.txt.
        State B contains only b.txt.
        This fixture is backend-agnostic.
        """
        from pyquipu.application.factory import create_engine

        # State A: Create a.txt
        plan_a = "```act\nwrite_file a.txt\n```\n```content\nState A\n```"
~~~~~

### 下一步建议
请再次运行测试。如果全部通过，我们就可以着手创建 `pyquipu-webapi` 包了。
