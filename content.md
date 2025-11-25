# chore: Create commit for test fixes

## 用户需求
测试已全部通过，需要将当前的修复工作提交到版本控制中。

## 评论
提交是保存工作进度的原子操作。一个清晰的提交信息有助于未来的代码审查和问题追溯。

## 目标
创建一个 Git 提交，记录 `test_engine.py` 中关于查询 API 测试的修复。

## 基本原理
使用 `git_commit` act 指令，并遵循标准的提交信息格式，清晰地描述本次修复的内容和原因。

## 标签
#comp/tests #scope/dx

---

## Script

### Acts 1: 提交代码

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~

~~~~~text
fix(test): Fix ambiguous regex in engine find_nodes test

The test `test_find_combined_filters` was failing because the regex "feat" used for querying plan nodes was too broad. It unintentionally matched the summary of a capture node ("Snapshot after feature A").

This commit corrects the test by using a more specific regex `^feat:` which anchors the search to the beginning of the summary string. This ensures the test accurately validates the filtering logic and is not susceptible to coincidental substring matches in test data.
~~~~~
