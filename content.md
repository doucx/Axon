好的，测试已经通过，现在我们将把这个健壮的自动化集成测试固化到版本历史中。

## commit(test(integration)): 为 sync 工作流添加自动化测试

### 用户需求
在 `sync` 功能的核心逻辑（包括 `Hydrator` 修复）通过手动脚本验证后，需要将该验证流程转化为一个自动化的 `pytest` 集成测试，并将其提交到版本库。

### 评论
这是确保 `sync` 功能长期稳定性的关键一步。通过将复杂的手动验证流程自动化，我们建立了一道强大的安全屏障，可以有效防止未来对相关代码的修改引入回归性错误。这个测试尤其重要，因为它覆盖了从用户引导到多用户数据正确同步的全过程。

### 目标
创建一个 Git 提交，将新添加的、已通过验证的 `tests/integration/test_sync_workflow.py` 文件及其所有修复正式纳入项目。

### 基本原理
该测试使用 `pytest` 框架和 `typer.testing.CliRunner` 来实现。它通过 `pytest` 的 `fixture` 在临时目录中动态创建了一个完整的协作环境，包括一个裸 Git 仓库（作为远程服务器）和两个独立的用户工作区。测试流程编排了用户 A 创建历史、用户 B 订阅并拉取历史的完整交互，并最终通过直接查询 SQLite 数据库来断言数据补水的正确性，特别是验证了所有权 (`owner_id`) 的无误传播。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/testing #task/object/sync-workflow #task/action/build #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交测试

现在，我们将把这个最终的、健壮的集成测试提交到版本库。

~~~~~act
git_add tests/integration/test_sync_workflow.py
~~~~~
~~~~~act
git_commit
~~~~~
~~~~~text
test(integration): add automated test for sync workflow

This commit introduces a comprehensive, automated integration test for the Quipu Sync feature, replacing the previous manual test script.

The test suite, located in `tests/integration/test_sync_workflow.py`, validates the entire end-to-end user workflow using a pytest fixture that sets up a realistic multi-user environment with a bare remote repository.

Key Scenarios Covered:
- **User Onboarding**: Verifies that the first `quipu sync` run correctly generates and saves a user_id.
- **Collaboration**: Simulates User B subscribing to User A and successfully fetching their history.
- **Ownership Integrity**: Critically, it asserts that the Hydrator correctly propagates `owner_id` to ALL historical nodes (including non-head ancestors), preventing data pollution. This directly tests the fix for the previously identified Hydrator bug.
- **Idempotency**: Ensures that running `sync` multiple times produces no side effects.
- **Remote Pruning**: Confirms that deleting a local Quipu head and syncing correctly prunes the corresponding ref on the remote.
~~~~~
