好的，我们已经完成了所有必要的代码修改和测试断言的重构。现在本地与 CI 环境已经完全对齐，测试套件也已回归全绿状态。

我将生成一个 `[COMMIT]` 计划，将这些旨在提升测试鲁棒性和 CI 兼容性的变更正式提交到仓库。

## [COMMIT] fix(tests): 统一 CI 与本地测试环境，全面转向 Key 标识符断言

### 用户需求
创建一个 Git 提交，包含所有关于 I18N `raw` 模式的引入以及集成测试断言重构的更改。

### 评论
通过引入 `raw` 语言模式并在测试中强制激活，我们彻底解决了“测试验证翻译文本”这一反模式问题。现在测试验证的是系统发出的原始信号，这使得项目在进行多语言扩展时，测试套件依然保持绝对稳定。

### 目标
1.  将 `bus.py` 和根 `conftest.py` 的环境配置变更加入暂存区。
2.  将 `pyquipu-cli` 及其集成测试目录下的所有断言重构变更加入暂存区。
3.  执行提交。

### 基本原理
这次提交将基础设施的改进（`raw` 模式）与受其影响的测试用例修复合并为一个原子操作，确保仓库历史的每一个节点都是可测试且一致的。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/common #concept/config #scope/dx #ai/instruct #task/domain/testing #task/object/ci-consistency #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及到的文件添加到暂存区，并创建一个描述详尽的提交记录。

~~~~~act
git_add
packages/pyquipu-common/src/quipu/common/bus.py
conftest.py
packages/pyquipu-cli/tests/integration/test_cli_interaction.py
tests/integration/test_cli_workflow.py
tests/integration/test_sync_workflow.py
tests/integration/test_storage_selection.py
tests/integration/test_sync_modes.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(tests): unify CI and local environments using raw I18N mode

Unified the behavior of the feedback bus across local development and CI
environments to prevent test failures caused by localized string mismatches.

Core Changes:
- Modified 'quipu-common' bus to support 'raw' and 'keys' language modes,
  which bypass translation loading and output original message keys.
- Forced 'QUIPU_LANG=raw' in the root 'conftest.py' for all test suites.
- Refactored all integration tests to assert against message keys (e.g.,
  'workspace.save.success') instead of hardcoded Chinese text.
- Standardized the use of '-y' (YOLO) flag in integration tests to avoid
  TTY dependencies in non-interactive CI runners.

This ensures tests are robust against translation changes and environment
path differences.
~~~~~

### 下一步建议
- **CI 验证**：推送代码后，观察 GitHub Actions 的运行情况。由于断言已与 Key 绑定且绕过了交互，CI 应当会稳定通过。
- **文档更新**：可以在开发者文档中记录“测试断言规范”，要求后续所有新测试均使用 `L.xxx.xxx` 路径对应的 Key 进行匹配。
