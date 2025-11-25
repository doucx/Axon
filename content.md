# fix: 提交插件加载路径和测试导入的修复

## 目标
将刚刚完成的关于 `PROJECT_ROOT` 路径修正和测试用例导入错误的修复，提交到 Git 版本历史中。

## 基本原理
在完成了关键的修复并通过了测试之后，立即创建一个原子性的提交是保证代码库健康的关键步骤。这个提交将记录我们如何解决了因 Monorepo 结构重构而引入的路径问题，确保了开发环境的稳定性和测试套件的可靠性。

## 标签
修复路径问题。 #fix #git #tests

---

## Script

### Act 1: 暂存所有修复

将所有对配置文件和测试文件的修改添加到暂存区。

~~~~~act
git_add .
~~~~~

### Act 2: 创建修复提交

使用描述性的提交信息，记录本次修复的内容。

~~~~~act
git_commit
~~~~~
~~~~~message
fix: Resolve plugin loading path and test suite errors

This commit addresses critical failures discovered after the monorepo refactoring.

- Corrects the `PROJECT_ROOT` detection logic in `quipu.cli.config` to properly locate the project's top-level directory. This enables the successful loading of plugins from the `acts/` directory.
- Fixes an `ImportError` in `tests/test_integration_v2.py` by updating the import statement for the `main` module to reflect its new location within the `quipu.cli` package.

These changes restore the integrity of the test suite and ensure the CLI can correctly locate its core components.
~~~~~