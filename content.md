### Acts 1: 提交补水机制

~~~~~act
git_add .
~~~~~
~~~~~act
git_commit
~~~~~
~~~~~text
chore: 实现 SQLite 数据补水机制

- 在 quipu-engine 中添加了 `Hydrator` 类，负责从 Git 历史记录向 SQLite 数据库同步节点和边数据。
- 采用 `git cat-file --batch` 实现高性能批量读取，遵循冷数据 (`plan_md_cache` = NULL) 策略。
- 在 `DatabaseManager` 中添加了批量插入和哈希查询的方法。
- 在 `Engine` 初始化时，若配置为 sqlite 后端，则自动触发增量补水。
- 在 quipu-cli 中添加了 `quipu cache sync` 和 `quipu cache rebuild` 命令，用于手动管理缓存。
- 添加了相应的单元测试 (`test_hydration.py`)。
~~~~~
