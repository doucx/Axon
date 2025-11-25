# fix-test: Correctly identify commit hash in workflow test

## 用户需求
`test_full_workflow_with_git_object_storage` 测试用例在 `checkout` 环节的准备步骤中失败。失败的原因是测试代码试图通过 `git log --grep="File A content"` 来查找与状态 A 对应的 Git Commit，但这个字符串存在于文件内容中，而不是 Git Commit 的摘要信息里，导致无法找到对应的 Commit。我需要修复这个测试，使其能够正确地定位到目标 Commit。

## 评论
这次的测试失败暴露了测试用例与系统实际行为之间的不匹配。系统的 `plan` 节点摘要是从 `act` 指令中提取的（例如 `write_file a.txt`），而不是从文件内容中提取。测试代码错误地假设了摘要的来源。

修复方案很简单：我们将修改测试用例，使其使用正确的、基于 `act` 指令的摘要字符串 (`write_file a.txt`) 来搜索 Git 日志。这使得测试用例的行为与系统的实际摘要生成逻辑保持一致，从而能够准确地找到目标 Commit 以进行后续的 `checkout` 验证。

## 目标
1.  修改 `tests/test_storage_integration.py` 中 `test_full_workflow_with_git_object_storage` 函数。
2.  将其中的 `git log --grep` 命令的搜索条件从 `"File A content"` 更改为 `"write_file a.txt"`。
3.  确保修复后所有测试都能通过，完成存储层重构的验证。

## 基本原理
在 `GitObject` 存储后端中，`plan` 节点的摘要（summary）被用作 Git Commit Message 的第一行。对于 `PLAN_A` 这个测试计划，其摘要是 `write_file a.txt`。因此，为了在 Git 历史中唯一地标识出创建状态 A 的那个节点，我们应该使用 `git log --grep="write_file a.txt"` 来进行搜索。当前测试代码错误地使用了文件内容的一部分作为搜索条件，导致搜索失败，后续的 `checkout` 无法执行。通过校准搜索条件，我们可以修复这个测试流程。

## 标签
#comp/tests #concept/history #scope/dx

---

## Script

### Acts 1: 修正集成测试中用于定位 Commit 的搜索字符串

我们将更新 `test_storage_integration.py`，使用正确的摘要信息来查找 Git Commit。

~~~~~act
replace
~~~~~
~~~~~path
tests/test_storage_integration.py
~~~~~
~~~~~python
        # that the reader uses. Let's find the commit for state A.
        commit_log_a = subprocess.run(
            ["git", "log", "--grep=File A content", "--format=%H", "refs/quipu/history"],
            cwd=git_workspace, capture_output=True, text=True
        ).stdout.strip()
~~~~~
~~~~~python
        # that the reader uses. Let's find the commit for state A by its summary.
        commit_log_a = subprocess.run(
            ["git", "log", "--grep=write_file a.txt", "--format=%H", "refs/quipu/history"],
            cwd=git_workspace, capture_output=True, text=True
        ).stdout.strip()
~~~~~