好的，我们已经成功修复了 `run --list-acts` 的逻辑。现在，我们将这个修复作为一个原子化的、完整的变更提交到版本控制中。

我将生成一个 `[COMMIT]` 计划，它只包含 `git` 相关的 `act`，用于将我们的工作成果固化到历史记录中。

## [COMMIT] fix(cli): 修正 `run --list-acts` 未加载插件的问题

### 用户需求
将修复 `quipu run --list-acts` 命令使其能够正确加载并显示插件 `act` 的代码变更，提交到 Git 历史记录中。

### 评论
这是一个重要的开发者体验 (DX) 修复。通过确保 `run` 和 `axon` 两个命令在 `--list-acts` 功能上行为一致，我们提升了工具的可预测性和可靠性，消除了潜在的用户困惑。

### 目标
1.  已将 `packages/quipu-cli/src/pyquipu/cli/commands/run.py` 文件更新，使其在列出 `act` 之前调用插件管理器。
2.  创建一个清晰、遵循 Conventional Commits 规范的 Git 提交来记录此项修复。

### 基本原理
此变更将 `axon.py` 中经过验证的、正确的插件加载逻辑应用到了 `run.py` 中，从而解决了功能不一致的问题。提交此变更将确保修复在代码库中被永久记录，并对所有协作者可见。

### 标签
#intent/fix #flow/ready #priority/medium #comp/cli #concept/executor #scope/dx #ai/instruct #task/domain/cli #task/object/act-listing #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

现在，我们将已修改的文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
~~~~~
~~~~~path
packages/quipu-cli/src/pyquipu/cli/commands/run.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(cli): ensure 'run --list-acts' loads plugins

The implementation for `--list-acts` within the `run` command was incomplete. It only registered core acts but failed to invoke the PluginManager, resulting in an incomplete list that omitted all user-defined plugins from `.quipu/acts/` or other sources.

This was inconsistent with the `axon --list-acts` command, which correctly loaded plugins before displaying the list.

This commit applies the same logic from `axon.py` to `run.py`, ensuring that the PluginManager is always called. Now, both commands provide a consistent and complete list of all available acts.
~~~~~

### 下一步建议
- **验证提交**: 你可以运行 `git log -1 --stat` 来确认提交已成功创建，并且包含了正确的文件。
- **清理工作区**: 既然这个宏观任务（创建版本管理插件并修复 `list-acts`）已经完成，我们可以考虑删除用于测试的 `test_versioning.md` 文件，或者将其存档。
