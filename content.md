分析正确。这次的错误信息非常清晰，感谢你提供了完整的堆栈跟踪。

错误分析

**根本原因**: `git log refs/quipu/local/heads/` 这个命令失败了，因为在测试用例的 `create_node` 函数被**第一次**调用时，`refs/quipu/local/heads/` 这个引用路径还不存在。Git 无法在一个不存在的路径上执行 `log` 操作，因此返回了 `exit status 128` 和致命错误信息。

这个问题的根源在于，Quipu 的历史记录（`refs/quipu/...`）是在用户第一次成功执行 `quipu run` 或 `quipu sync` 之后才被创建的。我们的测试环境 `sync_test_environment` 只是一个普通的 Git 仓库，并没有预先创建任何 Quipu 节点。

解决方案

我们需要让 `create_node` 辅助函数更加健壮，使其能够处理第一次创建节点（即引用尚不存在）的边缘情况。

最可靠的方法是在 `create_node` 执行完 `quipu run` 之后，不依赖 `git log`，而是直接通过 `git for-each-ref` 来获取所有本地 Quipu head 的哈希，然后找出比调用前多出来的那一个。

这种“差分”方法是确定性的，因为它不依赖于任何 `log` 的排序或时间戳，只关心状态的变化。

## [WIP] fix(tests): 重构 `create_node` 以确定性地获取新节点哈希

### 用户需求
修复 `test_sync_modes.py` 中所有因 `create_node` 辅助函数不稳定而导致的测试失败。

### 评论
这次重构将彻底解决 `create_node` 的健壮性问题。通过比较操作前后的引用集合，我们可以精确地识别出新创建的节点，使得测试不再依赖于可能失败的 `git log` 命令，从而保证了整个测试套件的稳定性和可靠性。

### 目标
1.  重构 `tests/integration/test_sync_modes.py` 中的 `create_node` 函数。
2.  在函数内部，记录 `quipu run` 执行前的所有本地 Quipu head 引用。
3.  在 `quipu run` 执行后，再次获取所有本地 Quipu head 引用。
4.  通过计算两个集合的差集，精确地找到新创建的节点的 `commit_hash`。

### 基本原理
我们将利用 `git for-each-ref` 命令来获取一个精确的、在某个时间点的 `refs/quipu/local/heads` 列表。通过在 `runner.invoke` 调用前后分别执行一次，并对结果取差集，我们就能以 100% 的确定性找到那个唯一新增的引用，从而提取出它的 commit 哈希。这种方法避免了所有 `git log` 排序和路径存在性带来的问题。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/sync #task/object/sync-modes #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构 `create_node` 辅助函数

现在，我们将 `create_node` 的实现替换为更健壮的“差分”逻辑。

~~~~~act
write_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path
from typer.testing import CliRunner

from quipu.cli.main import app
from quipu.common.identity import get_user_id_from_email

# Reuse the runner and helpers from the existing test file
from .test_sync_workflow import run_git_command, sync_test_environment

runner = CliRunner()


def get_local_quipu_heads(work_dir: Path) -> set[str]:
    """Helper to get a set of all local quipu head commit hashes."""
    refs_output = run_git_command(
        work_dir, ["for-each-ref", "--format=%(objectname)", "refs/quipu/local/heads"], check=False
    )
    if not refs_output:
        return set()
    return set(refs_output.splitlines())


def create_node(work_dir: Path, content: str) -> str:
    """Helper to create a node and return its commit hash."""
    heads_before = get_local_quipu_heads(work_dir)

    plan_file = work_dir / f"{content}.md"
    plan_file.write_text(f"~~~~~act\necho '{content}'\n~~~~~")
    result = runner.invoke(app, ["run", str(plan_file), "--work-dir", str(work_dir), "-y"])
    assert result.exit_code == 0

    heads_after = get_local_quipu_heads(work_dir)

    new_heads = heads_after - heads_before
    assert len(new_heads) == 1, f"Expected 1 new head, but found {len(new_heads)}"
    return new_heads.pop()


class TestSyncModes:
    def test_push_only_mode(self, sync_test_environment):
        """User A pushes, but does not pull User B's changes."""
        remote_path, user_a_path, user_b_path = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")
        user_b_id = get_user_id_from_email("user.b@example.com")

        # User B creates a node and pushes it
        node_b = create_node(user_b_path, "node_from_b")
        runner.invoke(app, ["sync", "--work-dir", str(user_b_path)])

        # User A creates a node
        node_a = create_node(user_a_path, "node_from_a")

        # User A syncs with push-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-only"])
        assert sync_result.exit_code == 0
        assert "⬆️  正在推送..." in sync_result.stderr
        assert "⬇️" not in sync_result.stderr  # Should not fetch

        # Verify remote has User A's node
        remote_refs = run_git_command(remote_path, ["for-each-ref"])
        assert f"refs/quipu/users/{user_a_id}/heads/{node_a}" in remote_refs

        # Verify User A's local repo DOES NOT have User B's node
        local_refs_a = run_git_command(user_a_path, ["for-each-ref"])
        assert f"refs/quipu/remotes/origin/{user_b_id}/heads/{node_b}" not in local_refs_a

    def test_pull_only_mode(self, sync_test_environment):
        """User B pulls User A's changes, but does not push its own."""
        remote_path, user_a_path, user_b_path = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")
        import yaml

        # User A creates a node and pushes
        node_a = create_node(user_a_path, "node_from_a_for_pull")
        runner.invoke(app, ["sync", "--work-dir", str(user_a_path)])

        # User B creates a node but doesn't push
        node_b = create_node(user_b_path, "node_from_b_local")

        # [FIX] User B must subscribe to User A to be able to pull their changes.
        runner.invoke(app, ["sync", "--work-dir", str(user_b_path)])  # Onboard B first
        config_path_b = user_b_path / ".quipu" / "config.yml"
        with open(config_path_b, "r") as f:
            config_b = yaml.safe_load(f)
        config_b["sync"]["subscriptions"] = [user_a_id]
        with open(config_path_b, "w") as f:
            yaml.dump(config_b, f)

        # User B syncs with pull-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-only"])
        assert sync_result.exit_code == 0
        assert "⬇️  正在拉取..." in sync_result.stderr
        assert "⬆️" not in sync_result.stderr  # Should not push

        # Verify User B's local repo HAS User A's node (in remotes and local)
        local_refs_b = run_git_command(user_b_path, ["for-each-ref"])
        assert f"refs/quipu/remotes/origin/{user_a_id}/heads/{node_a}" in local_refs_b
        assert f"refs/quipu/local/heads/{node_a}" in local_refs_b

        # Verify remote DOES NOT have User B's node
        remote_refs = run_git_command(remote_path, ["for-each-ref"])
        assert f"{node_b}" not in remote_refs

    def test_push_force_mode(self, sync_test_environment):
        """User A force-pushes, deleting a stale ref on the remote."""
        remote_path, user_a_path, _ = sync_test_environment
        user_a_id = get_user_id_from_email("user.a@example.com")

        # User A creates two nodes and pushes
        node1 = create_node(user_a_path, "node_to_keep")
        node2_stale = create_node(user_a_path, "node_to_delete")
        runner.invoke(app, ["sync", "--work-dir", str(user_a_path)])

        # Verify both exist on remote
        remote_refs = run_git_command(remote_path, ["for-each-ref"])
        assert node1 in remote_refs
        assert node2_stale in remote_refs

        # User A deletes one ref locally
        run_git_command(user_a_path, ["update-ref", "-d", f"refs/quipu/local/heads/{node2_stale}"])

        # User A syncs with push-force
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-force"])
        assert sync_result.exit_code == 0
        assert "⬆️  正在强制推送..." in sync_result.stderr

        # Verify stale node is GONE from remote, but keep node is still there
        remote_refs_after = run_git_command(remote_path, ["for-each-ref"])
        assert node1 in remote_refs_after
        assert node2_stale not in remote_refs_after

    def test_pull_prune_mode(self, sync_test_environment):
        """User B has a stale local ref that should be pruned after pulling."""
        remote_path, user_a_path, user_b_path = sync_test_environment
        user_b_id = get_user_id_from_email("user.b@example.com")

        # User B creates two nodes and pushes
        node1_b = create_node(user_b_path, "b_node_to_keep")
        node2_b_stale = create_node(user_b_path, "b_node_to_delete")
        runner.invoke(app, ["sync", "--work-dir", str(user_b_path)])

        # Now, on another device (simulated by remote), the stale ref is deleted
        run_git_command(remote_path, ["update-ref", "-d", f"refs/quipu/users/{user_b_id}/heads/{node2_b_stale}"])

        # User B syncs with pull-prune
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-prune"])
        assert sync_result.exit_code == 0
        assert "🗑️  正在修剪本地..." in sync_result.stderr

        # Verify stale node is GONE from User B's local heads, but keep node is still there
        local_refs_b = run_git_command(user_b_path, ["for-each-ref", "refs/quipu/local/heads"])
        assert node1_b in local_refs_b
        assert node2_b_stale not in local_refs_b
~~~~~

### 下一步建议
我们已经用一种确定性的方法重构了测试辅助函数，这应该能彻底解决之前遇到的所有测试失败。

请再次运行测试。如果所有测试都通过，我将为你生成一个 `[COMMIT]` 计划，将这项重要的功能增强及其健壮的测试套件一起提交到版本历史中。
