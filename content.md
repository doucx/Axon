好的，这是一个影响深远且非常有价值的重构。集中化 Fixture 能极大提升测试代码库的健康度和可维护性。

我将生成一个计划，分步完成这项重构任务。

## [WIP] refactor: 集中化测试 Fixture 以消除冗余

### 用户需求
根据分析，当前测试套件中存在多个功能重复的 fixture，用于搭建包含 Git 仓库和 Quipu Engine 实例的测试环境。需要将这些重复的逻辑统一到一个位于根目录 `tests/conftest.py` 的权威 fixture 中，以遵循 DRY (Don't Repeat Yourself) 原则。

### 评论
这是一个基础性且高回报的重构。它不仅能减少大量重复代码，更重要的是建立了一个“单一事实来源”，确保了测试环境的一致性。未来对 Engine 初始化逻辑的任何修改都只需要在一个地方进行，大大降低了维护成本。

### 目标
1.  在 `tests/` 目录下创建一个新的 `conftest.py` 文件。
2.  在该文件中定义两个核心的、可共享的 fixture：`git_workspace` (提供一个初始化的 Git 仓库路径) 和 `engine_instance` (提供一个功能完备的 Engine 实例)。
3.  重构 `tests/cli/conftest.py`，使其 `quipu_workspace` fixture 依赖于新的 `engine_instance`。
4.  重构 `tests/engine/test_engine.py`，移除其本地的 `engine_setup` fixture，并让所有测试直接使用 `engine_instance`。
5.  重构 `tests/cli/test_navigation_commands.py`，使其本地的 `nav_workspace` fixture 依赖于新的 `engine_instance`。
6.  确保所有受影响的测试用例在重构后依然能够通过。

### 基本原理
通过将核心 Fixture 定义在顶层的 `tests/conftest.py` 文件中，Pytest 的 Fixture 发现机制会自动使其对整个 `tests` 目录下的所有测试文件可见。这允许我们移除各个子目录中重复的定义，并以依赖注入的方式在需要时使用这些共享的 Fixture，从而实现代码的集中化管理和复用。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/fixtures #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建根级 `conftest.py` 并定义核心 Fixtures

这是本次重构的核心。我们将创建 `tests/conftest.py` 并定义 `git_workspace` 和 `engine_instance`。

~~~~~act
write_file
tests/conftest.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path

from quipu.engine.state_machine import Engine
from quipu.engine.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.engine.git_db import GitDB
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """提供一个可复用的 CliRunner 实例。"""
    return CliRunner()


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    """
    提供一个已初始化 Git 的干净工作区路径。
    这是最基础的环境 fixture。
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)
    return repo_path


@pytest.fixture
def engine_instance(git_workspace: Path) -> Engine:
    """
    提供一个绑定到 git_workspace 的、功能完备的 Engine 实例。
    这是最常用的 fixture，用于所有需要 Engine 核心逻辑的测试。
    """
    git_db = GitDB(git_workspace)
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)
    engine = Engine(root_dir=git_workspace, db=git_db, reader=reader, writer=writer)
    return engine
~~~~~

#### Acts 2: 简化 `tests/cli/conftest.py`

现在，我们将 `tests/cli/conftest.py` 中重复的逻辑移除，使其依赖新创建的 `engine_instance`。为了保持对现有测试的兼容性，`quipu_workspace` 的返回值结构不变。

~~~~~act
patch_file
tests/cli/conftest.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path
from typer.testing import CliRunner

from quipu.engine.state_machine import Engine
from quipu.engine.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.engine.git_db import GitDB


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def quipu_workspace(tmp_path):
    """
    创建一个包含 Git 仓库并初始化了 Quipu Engine 的测试环境。
    返回: (work_dir_path, git_db, engine)
    """
    work_dir = tmp_path / "ws"
    work_dir.mkdir()

    # 初始化 Git
    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=work_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=work_dir, check=True)

    # 初始化 Engine 组件
    git_db = GitDB(work_dir)
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)
    engine = Engine(work_dir, db=git_db, reader=reader, writer=writer)

    return work_dir, git_db, engine
~~~~~
~~~~~python
import pytest
from quipu.engine.state_machine import Engine

# runner fixture is now in the root conftest.py, so it's removed from here.

@pytest.fixture
def quipu_workspace(engine_instance: Engine):
    """
    为 CLI 测试提供 Engine 实例及其工作目录，保持原有返回结构以兼容现有测试。
    返回: (work_dir_path, git_db, engine)
    """
    return engine_instance.root_dir, engine_instance.git_db, engine_instance
~~~~~

#### Acts 3: 重构 `tests/engine/test_engine.py`

我们将移除此文件中的 `engine_setup` fixture，并更新所有使用它的测试函数，让它们直接接收 `engine_instance`。

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
@pytest.fixture
def engine_setup(tmp_path):
    """
    创建一个包含 Git 仓库和 Engine 实例的测试环境。
    默认使用新的 GitObject 存储后端。
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)

    git_db = GitDB(repo_path)
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)
    engine = Engine(repo_path, db=git_db, reader=reader, writer=writer)

    return engine, repo_path


def test_align_orphan_state(engine_setup):
    """
    测试场景：在一个没有历史记录的项目中运行时，
    引擎应能正确识别为 "ORPHAN" 状态 (适用于两种后端)。
    """
    engine, repo_path = engine_setup
~~~~~
~~~~~python
def test_align_orphan_state(engine_instance: Engine):
    """
    测试场景：在一个没有历史记录的项目中运行时，
    引擎应能正确识别为 "ORPHAN" 状态 (适用于两种后端)。
    """
    engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
def test_capture_drift_git_object(engine_setup):
    """
    测试场景 (GitObject Backend)：当工作区处于 DIRTY 状态时，引擎应能成功捕获变化，
    创建一个新的 Capture 节点，并更新 Git 引用。
    """
    engine, repo_path = engine_setup
~~~~~
~~~~~python
def test_capture_drift_git_object(engine_instance: Engine):
    """
    测试场景 (GitObject Backend)：当工作区处于 DIRTY 状态时，引擎应能成功捕获变化，
    创建一个新的 Capture 节点，并更新 Git 引用。
    """
    engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
class TestEngineFindNodes:
    @pytest.fixture
    def populated_engine(self, engine_setup):
        import time

        engine, repo_path = engine_setup
~~~~~
~~~~~python
class TestEngineFindNodes:
    @pytest.fixture
    def populated_engine(self, engine_instance: Engine):
        import time

        engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
class TestPersistentIgnores:
    def test_sync_creates_file_if_not_exists(self, engine_setup):
        """测试：如果 exclude 文件不存在，应能根据默认配置创建它。"""
        engine, repo_path = engine_setup
~~~~~
~~~~~python
class TestPersistentIgnores:
    def test_sync_creates_file_if_not_exists(self, engine_instance: Engine):
        """测试：如果 exclude 文件不存在，应能根据默认配置创建它。"""
        engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
    def test_sync_appends_to_existing_file(self, engine_setup):
        """测试：如果 exclude 文件已存在，应追加 Quipu 块而不是覆盖。"""
        engine, repo_path = engine_setup
~~~~~
~~~~~python
    def test_sync_appends_to_existing_file(self, engine_instance: Engine):
        """测试：如果 exclude 文件已存在，应追加 Quipu 块而不是覆盖。"""
        engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
    def test_sync_updates_existing_block(self, engine_setup):
        """测试：如果 Quipu 块已存在，应更新其内容。"""
        engine, repo_path = engine_setup
~~~~~
~~~~~python
    def test_sync_updates_existing_block(self, engine_instance: Engine):
        """测试：如果 Quipu 块已存在，应更新其内容。"""
        engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

~~~~~act
patch_file
tests/engine/test_engine.py
~~~~~
~~~~~python
    def test_sync_uses_user_config(self, engine_setup):
        """测试：应优先使用 .quipu/config.yml 中的用户配置。"""
        import yaml

        engine, repo_path = engine_setup
~~~~~
~~~~~python
    def test_sync_uses_user_config(self, engine_instance: Engine):
        """测试：应优先使用 .quipu/config.yml 中的用户配置。"""
        import yaml

        engine, repo_path = engine_instance, engine_instance.root_dir
~~~~~

#### Acts 4: 重构 `tests/cli/test_navigation_commands.py`

最后，我们重构此文件中的 `nav_workspace` fixture，让它也依赖 `engine_instance`。同时移除本地的 `runner` fixture，因为它现在由根 `conftest.py` 提供。

~~~~~act
patch_file
tests/cli/test_navigation_commands.py
~~~~~
~~~~~python
@pytest.fixture
def nav_workspace(tmp_path):
    """
    创建一个包含 Git 仓库和 Engine 实例的测试环境。
    """
    repo_path = tmp_path / "nav_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)

    git_db = GitDB(repo_path)
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)
    engine = Engine(repo_path, db=git_db, reader=reader, writer=writer)

    # Helper to create distinct states
    def create_state(content: str) -> str:
        (repo_path / "file.txt").write_text(content)
        return engine.git_db.get_tree_hash()

    return engine, create_state


@pytest.fixture
def runner():
    return CliRunner()
~~~~~
~~~~~python
@pytest.fixture
def nav_workspace(engine_instance: Engine):
    """
    创建一个包含 Git 仓库和 Engine 实例的测试环境。
    """
    engine = engine_instance
    repo_path = engine.root_dir

    # Helper to create distinct states
    def create_state(content: str) -> str:
        (repo_path / "file.txt").write_text(content)
        return engine.git_db.get_tree_hash()

    return engine, create_state
~~~~~

### 下一步建议
在执行此计划后，**必须**运行完整的测试套件 (`pytest tests/`)，以确保所有重构都已正确完成，并且没有引入任何回归错误。所有原来通过的测试都应该继续通过。
