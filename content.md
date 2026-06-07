好的，我们已经完成了代码修改。现在我们将这部分变更作为一个完整的逻辑单元提交到 Git 仓库中。

## [COMMIT] feat(cli): 添加 --version 选项以显示套件版本

### 用户需求
完成对 `quipu --version` 功能的开发并提交代码。

### 评论
这个功能虽然简单，但对于维护 Monorepo 结构的工具来说至关重要，它能帮助用户在遇到问题时提供准确的环境上下文。

### 目标
1. 将修改后的 `main.py` 文件添加到 Git 暂存区。
2. 创建一个符合 Conventional Commits 规范的提交。

### 基本原理
遵循“开发与提交分离”的原则，在确认代码逻辑正确后执行 Commit 操作，确保 Git 历史的整洁和可追溯性。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/version-command #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交代码变更

我们将修改后的 `main.py` 文件添加到暂存区，并创建一个描述清晰的提交记录。

~~~~~act
git_add
packages/pyquipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): add --version command to display package versions

Introduced a global --version (-V) option that displays the version numbers of all Quipu sub-packages (engine, runtime, spec, etc.) using importlib.metadata.

This is particularly useful for debugging in a monorepo environment where individual components might have different versions. The implementation uses an eager callback in Typer to ensure immediate execution and exit.
~~~~~

### 下一步建议
- **生产环境对齐**: 如果你正在使用 `bootstrap.py` 管理环境，建议运行 `python3 bootstrap.py promote` 将当前的开发代码同步到 `stable` 环境，这样你就可以直接使用 `qs --version` 来验证了。
- **文档更新**: 考虑在全局 README 中增加对该命令的简要说明。
