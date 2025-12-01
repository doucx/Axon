## [WIP] refactor: 将工作区测试转换为 CLI E2E 测试 (第四阶段)

### 用户需求
完成“集成层重新定义”阶段。目前 `tests/integration/` 下的 `test_workspace_invariance.py` 和 `test_workspace_isolation.py` 仍然直接调用 `run_quipu` 控制器函数。为了符合“集成测试应验证端到端 CLI 行为”的定义，我们需要将这两个测试重构为使用 `CliRunner` 调用 CLI 入口。

### 目标
1.  重构 `tests/integration/test_workspace_invariance.py`，使用 `CliRunner` 替代 `run_quipu`。
2.  重构 `tests/integration/test_workspace_isolation.py`，使用 `CliRunner` 替代 `run_quipu`。

### 基本原理
集成测试应尽可能模拟最终用户的真实使用方式。通过 CLI 入口 (`quipu run`) 进行测试，不仅验证了业务逻辑（控制器），还同时覆盖了参数解析、路径处理和错误展示层，提供了更完整的系统级保障。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #comp/cli #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 重构 `test_workspace_invariance.py`

将直接调用控制器的逻辑改为调用 `app`。

~~~~~act
write_file tests/integration/test_workspace_invariance.py
~~~~~
~~~~~python
import subprocess

import pytest
from pyquipu.cli.main import app


@pytest.fixture
def project_with_subdir(tmp_path):
    """
    创建一个标准的 Git 项目结构，包含一个子目录。
    root/
      .git/
      plan.md
      src/
        (empty)
    """
    # 1. 初始化项目根目录和 Git
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=root, check=True)

    # 2. 创建子目录和 Plan 文件
    subdir = root / "src"
    subdir.mkdir()

    plan_content = """
```act
write_file
```
```path
result.txt
```
```content
Success from subdir
```
"""
    (root / "plan.md").write_text(plan_content, "utf-8")

    return root, subdir


class TestRootInvariance:
    """
    测试 Quipu 的核心特性：根目录不变性。
    无论用户从项目的哪个子目录运行命令，Quipu 的行为都应该与在项目根目录运行时完全一致。
    """

    def test_run_from_subdir_maintains_root_context(self, runner, project_with_subdir):
        """
        验证：当通过 CLI 指定子目录为工作区时（模拟在子目录执行命令），
        Quipu 应能自动上溯发现项目根，并在根目录下正确记录历史，同时在 CWD 执行操作。
        """
        project_root, subdir = project_with_subdir
        plan_path = project_root / "plan.md"

        # 模拟命令: quipu run ../plan.md -w . (假设当前在 subdir)
        # 或者更直接地：quipu run /path/to/plan.md -w /path/to/subdir
        result = runner.invoke(
            app, 
            ["run", str(plan_path), "--work-dir", str(subdir), "-y"]
        )

        # 1. 验证 CLI 执行成功
        assert result.exit_code == 0, f"CLI execution failed: {result.stdout}"

        # 2. 验证文件操作发生在 subdir (CWD)
        # Executor 默认在传入的 work_dir 执行，这里传入的是 subdir
        expected_file = subdir / "result.txt"
        assert expected_file.exists(), "文件应该在子目录创建"
        assert expected_file.read_text("utf-8") == "Success from subdir"

        # 3. 验证 Engine 状态记录在 Project Root
        # 检查 .quipu 目录是否在 root 下创建
        assert (project_root / ".quipu").exists(), "历史记录目录应在项目根目录创建"
        assert (project_root / ".quipu" / "HEAD").exists()
        
        # 确保 subdir 下没有误创建 .quipu
        assert not (subdir / ".quipu").exists(), "子目录不应包含历史记录目录"
~~~~~

#### Acts 2: 重构 `test_workspace_isolation.py`

同样将其转换为 CLI 测试。

~~~~~act
write_file tests/integration/test_workspace_isolation.py
~~~~~
~~~~~python
import subprocess
from pathlib import Path

import pytest
from pyquipu.cli.main import app


@pytest.fixture
def nested_git_project(tmp_path: Path):
    """
    创建一个嵌套的 Git 项目结构来模拟隔离问题。
    Structure:
        host_project/
            .git/
            <-- .quipu should NOT be created here

            work_dir/
                .git/ <-- Nested repo
                <-- .quipu SHOULD be created here
    """
    host_project = tmp_path / "host_project"
    host_project.mkdir()
    subprocess.run(["git", "init"], cwd=host_project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=host_project, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=host_project, check=True)

    work_dir = host_project / "work_dir"
    work_dir.mkdir()
    # 初始化嵌套仓库
    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=work_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=work_dir, check=True)

    return host_project, work_dir


class TestWorkDirIsolation:
    def test_history_is_created_in_work_dir_not_host_project(self, runner, nested_git_project):
        """
        验证：当在子目录 work_dir 中运行 CLI 时，Quipu 的历史记录
        (.quipu) 必须在该子目录中创建，而不是在包含 .git 的父目录中。
        这确保了嵌套项目之间的隔离。
        """
        host_project, work_dir = nested_git_project

        # 创建一个临时计划文件
        plan_file = work_dir / "plan.md"
        plan_file.write_text("""
```act
write_file result.txt
```
```content
isolation test
```
""", encoding="utf-8")

        # 运行 CLI: quipu run plan.md -w work_dir
        result = runner.invoke(
            app, 
            ["run", str(plan_file), "--work-dir", str(work_dir), "-y"]
        )

        # --- Assertions ---

        assert result.exit_code == 0, f"CLI execution failed: {result.stdout}"

        # 1. 验证文件操作发生在 work_dir
        assert (work_dir / "result.txt").exists()
        assert not (host_project / "result.txt").exists()

        # 2. 验证历史记录 (.quipu) 创建在 work_dir
        assert (work_dir / ".quipu").is_dir()
        assert (work_dir / ".quipu" / "HEAD").exists()

        # 3. 验证宿主项目没有被污染
        assert not (host_project / ".quipu").exists()
~~~~~

### 下一步建议
所有阶段的任务已完成。建议运行所有测试（`pytest tests/`）进行最终验收，确认测试架构重构成功且未引入回归问题。
