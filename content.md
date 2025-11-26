# fix(runtime): Resolve TypeError regression in Executor

## 用户需求
在修复了 `Executor` 的回归错误并通过所有测试后，你需要将这个修复提交到版本控制中。

## 评论
这是一个关键的修复提交。它纠正了在上一次重构中引入的严重回归错误，使整个测试套件和应用程序恢复到稳定和可用的状态。提交信息清晰地记录了问题的根本原因，有助于未来的代码审查和维护。

## 目标
使用 `git_add` 和 `git_commit` 指令，将对 `executor.py` 的修复创建一个原子性的、符合规范的 Git 提交。

## 基本原理
通过 `git_add .` 暂存所有变更（在这种情况下，主要是 `executor.py` 的修复），然后使用 `git_commit` 附带一个详细的提交信息来固化这次修复。提交信息遵循 `Conventional Commits` 规范，类型为 `fix`，作用域为 `runtime`，清晰地说明了问题的起因和解决方案。

## 标签
#intent/fix #flow/ready #priority/critical
#comp/runtime #comp/tests
#scope/core
#ai/instruct

---

## Script

### Acts 1: 提交修复

暂存所有变更并创建提交。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~
fix(runtime): Resolve TypeError regression in Executor

This commit fixes a critical regression introduced during the recent decoupling of the Executor from the Typer UI framework.

The root cause of the `TypeError: unhashable type: 'list'` was an incorrect assignment in the `execute` and `summarize_statement` methods. The entire `tokens` list was being assigned to `act_name` instead of just the first element (`tokens[0]`). This caused a fatal error when the list was used as a dictionary key to look up the registered act.

This commit corrects the assignments, restoring the intended logic and resolving the widespread test failures. It also includes a minor fix for the `get_registered_acts` method's docstring access.
~~~~~
