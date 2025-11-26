# chore: 创建提交

## 用户需求
测试已通过，需要将所有暂存的变更创建一个 Git 提交。

## 评论
这是一个重要的重构提交，它通过依赖注入解耦了 `Engine` 和存储层，并引入了内存测试后端，为项目的健康发展奠定了坚实基础。我将撰写一条清晰的提交信息来记录这次变更。

## 目标
1.  将所有变更添加到 Git 暂存区。
2.  创建一个符合 Conventional Commits 规范的提交。

## 基本原理
使用 `git_add` 和 `git_commit` 指令来完成版本控制操作。提交信息将清晰地说明本次重构的目的、方法和带来的好处。

## 标签
#intent/tooling #flow/ready #priority/high 
#comp/build 
#ai/instruct 

---

## Script

### Acts 1: 提交变更

````act
git_add .
````
````act
git_commit
````
````
refactor(engine): Introduce DB dependency injection for testability

This commit refactors the Engine and related components to support dependency injection for the database backend. This change is crucial for improving the testability of the system.

Key changes include:
- The `Engine` constructor now accepts a `db` object (e.g., `GitDB` or a mock) instead of creating a `GitDB` instance internally.
- An `InMemoryDB` and `InMemoryHistoryManager` have been created in `tests/helpers.py` to provide a fast, isolated, in-memory storage backend for testing.
- All relevant test fixtures and direct instantiations of the `Engine` across the test suite have been updated to pass the required `db` argument.
- A new test file, `test_engine_memory.py`, has been added to validate the in-memory backend.

This architectural improvement enables true unit testing of the Engine's core logic, significantly speeding up the test suite and improving test isolation by removing dependencies on the filesystem and Git subprocesses.
````
