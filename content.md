# fix: resolve project root in create_engine to fix subdirectory execution

## 用户需求
提交修复的代码，该修复解决了在 Git 仓库的子目录中运行 Quipu 命令时因无法找到 `.git` 目录而导致的崩溃问题。

## 目标
将修改后的 `factory.py` 和更新后的测试文件提交到版本控制系统。

## 基本原理
`create_engine` 现在会向上查找 Git 根目录来初始化 `Engine`（因为 Engine 依赖 GitDB），而 `Executor` 继续在用户指定的 `work_dir`（子目录）中运行。这不仅修复了崩溃，还保持了文件操作符合用户直觉（即在当前目录创建文件）。同时更新了测试以反映这种正确的隔离行为。

## 标签
#comp/cli #comp/tests #scope/core #fix

---

## Script

### Acts 1: Commit Changes

提交代码修复和测试更新。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~

~~~~~message
fix(cli): resolve project root in create_engine to fix subdirectory execution

This change ensures that the Engine is always initialized at the true Git root
(found via find_project_root), preventing crashes when 'work_dir' is a subdirectory.
The Executor remains bound to 'work_dir', preserving the expected behavior of
relative file operations.

Updates:
- packages/quipu-cli/src/quipu/cli/factory.py: Use find_project_root in create_engine.
- tests/test_isolation.py: Initialize git in nested work_dir to satisfy GitDB requirements.
- tests/test_root_invariance.py: Update assertions to expect file creation in subdir.
~~~~~
