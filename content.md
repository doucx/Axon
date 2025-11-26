# fix: 修正测试用例中 Engine 的直接实例化

## 用户需求
在修复了测试 fixtures 后，`TestPersistentIgnores` 类中的测试用例仍然因为 `TypeError: Engine.__init__() missing 1 required positional argument: 'db'` 而失败。

## 评论
这是上一次重构的后续修复。`TestPersistentIgnores` 中的测试用例为了验证 `Engine` 初始化时的 `_sync_persistent_ignores` 行为，会显式地重新创建一个 `Engine` 实例。我需要更新这些实例化调用，以符合新的构造函数签名。

## 目标
1.  修改 `tests/test_engine.py` 文件中 `TestPersistentIgnores` 类下的所有 `Engine(...)` 调用，为其添加 `db` 参数。
2.  确保所有测试都能通过。

## 基本原理
在 `engine_setup` fixture 返回的 `engine` 实例中，`engine.git_db` 属性已经包含了正确的 `GitDB` 实例。因此，在重新实例化 `Engine` 时，我们只需将这个已有的 `db` 实例传递进去即可。

## 标签
#intent/fix #flow/ready #priority/critical 
#comp/engine #comp/tests 
#scope/dx 
#ai/instruct 

---

## Script

### Acts 1: 更新 `TestPersistentIgnores` 中的 Engine 调用

由于所有四个测试用例中的错误代码行完全相同，我可以使用一个 `replace` 指令一次性修复它们。

````act
replace tests/test_engine.py
````
````python
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, reader=engine.reader, writer=engine.writer)
````
````python
        # 重新初始化 Engine 以触发同步逻辑
        engine = Engine(repo_path, db=engine.git_db, reader=engine.reader, writer=engine.writer)
````
