好的，测试已通过。这标志着我们已经为引用膨胀问题提供了一个健壮、安全的解决方案。

我将生成一个 `[COMMIT]` 计划，该计划会：
1.  **清理技术债务**：回滚之前为支持已废弃的自动修剪逻辑而在 `Engine` 中添加的 `parent_commit_hash` 传递代码，保持代码库的整洁。
2.  **提交所有相关变更**：将回滚、新命令、新测试和本地化文件作为一个原子单元提交。

## [COMMIT] fix(engine, cli): revert auto-pruning and add manual prune-refs command

### 用户需求
在自动引用修剪逻辑被证实存在缺陷并回滚后，需要将所有相关的修复（回滚）、新功能（`prune-refs` 命令）和验证（测试用例）作为一个完整的逻辑单元进行提交。

### 评论
这个提交标志着对引用管理问题的一次完整、严谨的修复。它体现了一个健康的开发周期：提出方案、测试验证、发现缺陷、安全回滚、提供更健壮的替代方案、并为新方案提供完备的测试。最终的 `prune-refs` 命令为用户提供了对仓库维护的可控性和安全性。

### 目标
1.  回滚 `state_machine.py` 中为支持已废弃功能而添加的 `parent_commit_hash` 参数传递。
2.  将 `git_object_storage.py` 的回滚、`cache.py` 中新增的 `prune-refs` 命令、相关的本地化字符串以及 `test_cache_commands.py` 中的新测试用例全部添加到 Git 暂存区。
3.  创建一个符合 Conventional Commits 规范的 Git 提交。

### 基本原理
通过将所有相关变更捆绑在一次提交中，我们确保了代码历史的清晰性和原子性。任何人查看这次提交都能完整地理解问题的发现、失败的尝试和最终的解决方案。回滚 `state_machine.py` 是为了消除不再被任何代码使用的“僵尸代码”，遵循了最小化技术债务的原则。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/engine #comp/cli #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/ref-management #task/action/prune #task/state/end #task/status/completed

---

### Script

#### Acts 1: 清理 `Engine` 中的技术债务

回滚 `state_machine.py` 中不再需要的 `parent_commit_hash` 参数。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~python
        user_id = self._get_current_user_id()
        parent_hash = self.current_node.commit_hash if self.current_node else None

        new_node = self.writer.create_node(
            node_type="capture",
            input_tree=input_hash,
            output_tree=current_hash,
            content=body,
            message=message,
            owner_id=user_id,
            parent_commit_hash=parent_hash,
        )
~~~~~
~~~~~python
        user_id = self._get_current_user_id()

        new_node = self.writer.create_node(
            node_type="capture",
            input_tree=input_hash,
            output_tree=current_hash,
            content=body,
            message=message,
            owner_id=user_id,
        )
~~~~~

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~python
        user_id = self._get_current_user_id()
        parent_hash = self.current_node.commit_hash if self.current_node else None

        new_node = self.writer.create_node(
            node_type="plan",
            input_tree=input_tree,
            output_tree=output_tree,
            content=plan_content,
            summary_override=summary_override,
            owner_id=user_id,
            parent_commit_hash=parent_hash,
        )
~~~~~
~~~~~python
        user_id = self._get_current_user_id()

        new_node = self.writer.create_node(
            node_type="plan",
            input_tree=input_tree,
            output_tree=output_tree,
            content=plan_content,
            summary_override=summary_override,
            owner_id=user_id,
        )
~~~~~

#### Acts 2: 暂存所有相关变更

~~~~~act
git_add
packages/quipu-engine/src/pyquipu/engine/state_machine.py
packages/quipu-engine/src/pyquipu/engine/git_object_storage.py
packages/quipu-cli/src/pyquipu/cli/commands/cache.py
packages/quipu-common/src/pyquipu/common/locales/zh/cli.json
tests/cli/test_cache_commands.py
~~~~~

#### Acts 3: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine, cli): revert auto-pruning and add manual prune-refs command

Reverts a flawed automatic ref-pruning implementation and introduces a robust, manual `quipu cache prune-refs` command as a replacement.

The initial automatic pruning logic in `GitObjectHistoryWriter` incorrectly deleted parent refs in branching scenarios, causing test failures and potential data integrity issues. This change completely removes that logic, restoring the safer default behavior of creating a head ref for every node.

To address the original problem of ref proliferation, this commit adds:
1.  A new `quipu cache prune-refs` command that safely identifies and removes redundant refs from linear history chains while preserving all branch heads.
2.  A comprehensive test suite for the new command, ensuring its correctness across various scenarios (redundancy, no redundancy, empty repo).
~~~~~

### 下一步建议
我们已经成功解决了引用管理的问题。现在可以继续处理待办事项列表中的其他任务，例如：`为 quipu log 这样的选项添加类似 export 的筛选逻辑`。
