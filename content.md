好的，我们已经抵达了 `sync` 功能开发的最后阶段。现在开始执行任务 6.1，为整个工作流编写端到端的集成测试。

我将创建一个新的集成测试文件，它会模拟一个真实的协作场景：一个裸仓库作为远程服务器，以及两个独立的用户工作区。我们将在这个环境中验证首次推送、跨设备同步、订阅协作以及引用清理等核心功能。

这是一个关键的步骤，它将确保我们的架构设计在实际的 Git 环境中能够正确、稳定地运行。

## test: 为 `sync` 功能编写端到端的集成测试

### 用户需求
为 `quipu sync` 的完整工作流编写一套集成测试，以验证其在真实 Git 环境下的正确性和健壮性。测试需要覆盖以下核心场景：
1.  首次使用的用户引导 (Onboarding) 和初次推送。
2.  用户订阅其他协作者并拉取其历史。
3.  `sync` 操作的幂等性。
4.  本地删除历史后，远程引用的自动清理 (`--prune`) 功能。

### 评论
这是 `sync` 功能交付前的最后一道质量保证。通过模拟真实的多用户协作环境，我们可以捕捉到仅在单元测试中难以发现的配置、环境和流程问题。这将确保我们交付的 `sync` 功能是生产可用的。

### 目标
1.  创建一个新的测试文件 `tests/integration/test_sync_workflow.py`。
2.  利用 `pytest` 的 `fixture` 功能，搭建一个包含“远程裸仓库”和两个“用户工作区”的测试环境。
3.  编写测试用例，覆盖上述所有核心场景。
4.  确保测试完成后，所有临时创建的仓库和文件都被正确清理。

### 基本原理
-   **测试环境**: 使用 `tmp_path` fixture 创建临时目录。通过 `subprocess` 调用 `git` 命令来初始化一个裸仓库 (`--bare`) 作为中央远程，并创建两个克隆作为用户工作区。
-   **命令执行**: 使用 `typer.testing.CliRunner` 来调用 `quipu` 的 CLI 命令，模拟用户的真实操作。
-   **状态验证**: 通过 `subprocess` 调用 `git ls-remote` 和 `git for-each-ref` 等底层命令来检查远程和本地仓库的引用状态。同时，通过直接读取 `.quipu/config.yml` 和查询 SQLite 数据库来验证配置和数据补水的正确性。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #comp/cli #concept/sync #scope/core #ai/instruct #task/domain/testing #task/object/sync-workflow #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 创建集成测试文件

我将创建 `tests/integration/test_sync_workflow.py` 文件，并填充完整的测试脚手架和所有核心场景的测试用例。

~~~~~act
write_file
tests/integration/test_sync_workflow.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path
from typer.testing import CliRunner
import yaml
import sqlite3

from quipu.cli.main import app
from quipu.common.identity import get_user_id_from_email

runner = CliRunner()


def run_git_command(cwd: Path, args: list[str], check: bool = True) -> str:
    """Helper to run a git command and return stdout."""
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=check)
    return result.stdout.strip()


@pytest.fixture(scope="module")
def sync_test_environment(tmp_path_factory):
    """
    Sets up a full sync test environment:
    1. A bare remote repository.
    2. Two user workspaces cloned from the remote.
    """
    base_dir = tmp_path_factory.mktemp("sync_tests")
    remote_path = base_dir / "remote.git"
    user_a_path = base_dir / "user_a"
    user_b_path = base_dir / "user_b"

    # 1. Create bare remote
    run_git_command(base_dir, ["init", "--bare", str(remote_path)])

    # 2. Clone for User A
    run_git_command(base_dir, ["clone", str(remote_path), str(user_a_path)])
    run_git_command(user_a_path, ["config", "user.name", "User A"])
    run_git_command(user_a_path, ["config", "user.email", "user.a@example.com"])

    # 3. Clone for User B
    run_git_command(base_dir, ["clone", str(remote_path), str(user_b_path)])
    run_git_command(user_b_path, ["config", "user.name", "User B"])
    run_git_command(user_b_path, ["config", "user.email", "user.b@example.com"])

    # Add a dummy file to avoid issues with initial empty commits
    (user_a_path / "README.md").write_text("Initial commit")
    run_git_command(user_a_path, ["add", "README.md"])
    run_git_command(user_a_path, ["commit", "-m", "Initial commit"])
    run_git_command(user_a_path, ["push", "origin", "master"])
    run_git_command(user_b_path, ["pull"])

    return remote_path, user_a_path, user_b_path


class TestSyncWorkflow:
    def test_onboarding_and_first_push(self, sync_test_environment):
        """
        Tests the onboarding flow (user_id creation) and the first push of Quipu refs.
        """
        remote_path, user_a_path, _ = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")

        # Create a Quipu node for User A
        (user_a_path / "plan.md").write_text("~~~~~act\necho 'hello'\n~~~~~")
        result = runner.invoke(app, ["run", "plan.md", "--work-dir", str(user_a_path), "-y"])
        assert result.exit_code == 0

        # Run sync for the first time
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--remote", "origin"])
        assert sync_result.exit_code == 0
        assert "首次使用 sync 功能" in sync_result.stderr
        assert f"生成并保存用户 ID: {user_a_id}" in sync_result.stderr

        # Verify config file
        config_path = user_a_path / ".quipu" / "config.yml"
        assert config_path.exists()
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        assert config["sync"]["user_id"] == user_a_id

        # Verify remote refs
        remote_refs = run_git_command(remote_path, ["for-each-ref", "--format=%(refname)"])
        assert f"refs/quipu/users/{user_a_id}/heads/" in remote_refs

    def test_collaboration_subscribe_and_fetch(self, sync_test_environment):
        """
        Tests that User B can subscribe to and fetch User A's history.
        This test depends on the state after the first push.
        """
        remote_path, user_a_path, user_b_path = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")
        user_b_id = get_user_id_from_email("user.b@example.com")

        # User B onboards first
        runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--remote", "origin"])

        # User B subscribes to User A
        config_path_b = user_b_path / ".quipu" / "config.yml"
        with open(config_path_b, "r") as f:
            config_b = yaml.safe_load(f)
        config_b["sync"]["subscriptions"] = [user_a_id]
        with open(config_path_b, "w") as f:
            yaml.dump(config_b, f)

        # User B syncs again to fetch User A's data
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--remote", "origin"])
        assert sync_result.exit_code == 0
        assert f"拉取 2 个用户的历史" in sync_result.stderr  # Self + subscription

        # Verify local mirror ref in User B's repo
        local_refs_b = run_git_command(user_b_path, ["for-each-ref", "--format=%(refname)"])
        assert f"refs/quipu/remotes/origin/{user_a_id}/heads/" in local_refs_b

        # Verify hydration
        cache_sync_result = runner.invoke(app, ["cache", "sync", "--work-dir", str(user_b_path)])
        assert cache_sync_result.exit_code == 0

        db_path_b = user_b_path / ".quipu" / "history.sqlite"
        assert db_path_b.exists()
        conn = sqlite3.connect(db_path_b)
        cursor = conn.cursor()
        cursor.execute("SELECT owner_id FROM nodes")
        owners = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert user_a_id in owners

    def test_sync_is_idempotent(self, sync_test_environment):
        """
        Tests that running sync multiple times doesn't change state or cause errors.
        """
        _, user_a_path, _ = sync_test_environment
        result1 = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--remote", "origin"])
        assert result1.exit_code == 0
        refs_after_1 = run_git_command(user_a_path, ["for-each-ref"])

        result2 = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--remote", "origin"])
        assert result2.exit_code == 0
        refs_after_2 = run_git_command(user_a_path, ["for-each-ref"])

        assert refs_after_1 == refs_after_2

    def test_pruning_on_push(self, sync_test_environment):
        """
        Tests that deleting a local head and syncing prunes the remote ref.
        """
        remote_path, user_a_path, _ = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")

        # Create two new nodes
        (user_a_path / "plan2.md").write_text("~~~~~act\necho 'plan2'\n~~~~~")
        (user_a_path / "plan3.md").write_text("~~~~~act\necho 'plan3'\n~~~~~")
        runner.invoke(app, ["run", "plan2.md", "--work-dir", str(user_a_path), "-y"])
        runner.invoke(app, ["run", "plan3.md", "--work-dir", str(user_a_path), "-y"])

        runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--remote", "origin"])
        remote_refs_before = run_git_command(remote_path, ["for-each-ref", f"refs/quipu/users/{user_a_id}"])
        num_refs_before = len(remote_refs_before.splitlines())
        assert num_refs_before >= 2

        # Find a ref to delete locally
        local_quipu_refs = run_git_command(
            user_a_path, ["for-each-ref", "--format=%(refname)", "refs/quipu/local/heads"]
        ).splitlines()
        ref_to_delete = local_quipu_refs[0]

        # Delete it locally
        run_git_command(user_a_path, ["update-ref", "-d", ref_to_delete])

        # Sync again
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--remote", "origin"])
        assert sync_result.exit_code == 0

        # Verify it's gone from remote
        remote_refs_after = run_git_command(remote_path, ["for-each-ref", f"refs/quipu/users/{user_a_id}"])
        num_refs_after = len(remote_refs_after.splitlines())

        assert num_refs_after == num_refs_before - 1
        assert ref_to_delete.split("/")[-1] not in remote_refs_after

~~~~~

### 下一步建议
测试框架已经搭建完毕。下一步，我们可以继续向 `TestSyncWorkflow` 类中添加更多的边界条件测试，例如：
-   测试在没有 `git config user.email` 时 `sync` 命令是否会优雅地失败并给出提示。
-   测试空的 `subscriptions` 列表是否能正常工作。
-   测试 `prune` 在 `fetch` 时的行为。

同时，我们应该开始着手 **任务 6.2：更新用户文档**，将 `sync` 功能的用法和协作工作流的理念清晰地传达给用户。
