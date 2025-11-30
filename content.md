好的，我分析了这四个 `integration` 测试的失败原因。它们都指向同一个根本问题：在 CI 环境中，用于测试的临时 Git 仓库没有配置作者信息（`user.name` 和 `user.email`），导致 `git commit-tree` 操作失败。

这个问题可以通过修改创建这些临时仓库的测试代码和 `fixture` 来解决，确保在 `git init` 之后立即为每个仓库配置一个默认的用户身份。

以下是修复这个问题的完整计划。

## [WIP] fix(tests): 为集成测试中的临时 Git 仓库配置身份

### 错误分析
所有四个失败的集成测试 (`test_cli_workflow`, `test_idempotent_node`, `test_workspace_invariance`, `test_workspace_isolation`) 都在 CI 环境中因 `Author identity unknown` 错误而崩溃。

根本原因是，这些测试在 `tmp_path` 中通过 `subprocess.run(["git", "init"], ...)` 创建了临时的 Git 仓库，但并未随后配置 `user.name` 和 `user.email`。当 Quipu 引擎尝试使用 Git 底层命令 `commit-tree` 创建历史节点时，由于缺少作者信息，Git 命令失败，导致整个测试用例崩溃。

这个问题在开发者的本地机器上可能不会出现，因为本地通常有全局的 Git 配置。但在一个干净的 CI/CD runner 环境中，这个配置是缺失的，从而暴露了测试设置的不完备性。

### 用户需求
修复所有失败的集成测试，确保它们在任何环境中都能稳定运行，不依赖于全局 Git 配置。

### 评论
这是一个典型的 CI 环境问题，修复它能显著提升测试套件的健壮性和可移植性。通过在测试的 `fixture` 和设置代码中显式配置 Git 身份，我们能确保测试的确定性，使其与运行环境解耦。

### 目标
1.  定位所有创建了临时 Git 仓库但未配置用户身份的测试用例和 `fixture`。
2.  通过 `patch_file` 操作，在每个 `git init` 之后，添加设置 `user.email` 和 `user.name` 的命令。
3.  确保所有受影响的测试文件都被修正。

### 基本原理
我们将对四个相关文件中的测试设置代码进行精确修改。对于每个被 `git init` 初始化的临时仓库，我们都将立即执行 `git config user.email "test@quipu.dev"` 和 `git config user.name "Quipu Test"`。这将为 Git 的提交操作提供必要的作者信息，从而解决 `commit-tree` 命令失败的问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/ci-stability #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修正 `test_cli_workflow.py`

为 `test_cli_file_input` 测试用例中临时创建的 Git 仓库添加身份配置。

~~~~~act
patch_file
tests/integration/test_cli_workflow.py
~~~~~
~~~~~python
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(tmp_path), "--yolo"])
~~~~~
~~~~~python
        import subprocess
    
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

        # 设置 user 避免 commit 报错
        subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=tmp_path, check=True)
    
        result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(tmp_path), "--yolo"])
~~~~~

#### Acts 2: 修正 `test_idempotent_node.py`

为 `test_idempotent_plan_creation` 测试用例中创建的 `workspace` 添加身份配置。

~~~~~act
patch_file
tests/integration/test_idempotent_node.py
~~~~~
~~~~~python
        import subprocess

        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

        # 2. 先执行一个会产生变更的操作 (State A)
~~~~~
~~~~~python
        import subprocess

        subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=workspace, check=True)

        # 2. 先执行一个会产生变更的操作 (State A)
~~~~~

#### Acts 3: 修正 `test_workspace_invariance.py`

为 `project_with_subdir` fixture 中创建的 `project_root` 仓库添加身份配置。

~~~~~act
patch_file
tests/integration/test_workspace_invariance.py
~~~~~
~~~~~python
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)

    # 2. 创建子目录和 Plan 文件
~~~~~
~~~~~python
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    # 设置 user 避免 commit 报错
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=root, check=True)

    # 2. 创建子目录和 Plan 文件
~~~~~

#### Acts 4: 修正 `test_workspace_isolation.py`

为 `nested_git_project` fixture 中创建的两个嵌套仓库 (`host_project` 和 `work_dir`) 分别添加身份配置。

~~~~~act
patch_file
tests/integration/test_workspace_isolation.py
~~~~~
~~~~~python
    host_project = tmp_path / "host_project"
    host_project.mkdir()
    subprocess.run(["git", "init"], cwd=host_project, check=True, capture_output=True)

    work_dir = host_project / "work_dir"
~~~~~
~~~~~python
    host_project = tmp_path / "host_project"
    host_project.mkdir()
    subprocess.run(["git", "init"], cwd=host_project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=host_project, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=host_project, check=True)

    work_dir = host_project / "work_dir"
~~~~~

~~~~~act
patch_file
tests/integration/test_workspace_isolation.py
~~~~~
~~~~~python
    # 为了测试隔离性（不污染 host_project），work_dir 必须自己是一个独立的仓库。
    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)

    return host_project, work_dir
~~~~~
~~~~~python
    # 为了测试隔离性（不污染 host_project），work_dir 必须自己是一个独立的仓库。
    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=work_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=work_dir, check=True)

    return host_project, work_dir
~~~~~

### 下一步建议
- **执行计划**: 在你确认后，我将执行此计划来修复所有文件。
- **重新运行测试**: 执行完毕后，应重新运行 `pytest tests/integration/` 以验证所有失败的测试用例现在都已通过。
- **提交变更**: 验证通过后，我会生成一个 `[COMMIT]` 计划来将这些修复持久化到版本控制中。
