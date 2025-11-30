好的，我将处理 `packages/quipu-engine/` 目录下的这两个 `E501` (行太长) 错误。

## [WIP] style: 修正超长代码行以符合 ruff 规范

### 错误分析
`ruff` 检测到两个超过 120 字符限制的行：
1.  在 `sqlite_storage.py` 中，一个 SQL `INSERT` 语句的列名列表过长。
2.  在 `state_machine.py` 中，一个 `logger.warning` 调用中的 f-string 过长。

### 用户需求
修改这两行代码，使其长度符合项目代码风格要求，以通过 lint 检查。

### 评论
这是常规的代码风格调整，通过换行来提高代码的可读性，并确保代码库的一致性。

### 目标
1.  将 `sqlite_storage.py` 中的 SQL 查询语句格式化为多行。
2.  将 `state_machine.py` 中的长 f-string 拆分为多行。

### 基本原理
-   对于 SQL 字符串，在列列表的中间位置进行换行。
-   对于 f-string，利用 Python 字符串字面量会自动拼接的特性，将其拆分为两个相邻的 f-string。

### 标签
#intent/tune #flow/ready #priority/low #comp/engine #scope/dx #ai/instruct #task/domain/testing #task/object/linter #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 格式化 `sqlite_storage.py` 中的 SQL 查询

我们将把 `INSERT` 语句中的列名列表拆分为两行。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/sqlite_storage.py
~~~~~
~~~~~python
            self.db_manager.execute_write(
                """
                INSERT OR REPLACE INTO nodes 
                (commit_hash, owner_id, output_tree, node_type, timestamp, summary, generator_id, meta_json, plan_md_cache)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_hash,
~~~~~
~~~~~python
            self.db_manager.execute_write(
                """
                INSERT OR REPLACE INTO nodes
                (commit_hash, owner_id, output_tree, node_type, timestamp, summary,
                 generator_id, meta_json, plan_md_cache)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_hash,
~~~~~

#### Acts 2: 拆分 `state_machine.py` 中的长 f-string

我们将把过长的 f-string 日志消息拆分为两行。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~python
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            logger.warning(
                f"⚠️  HEAD 指针 '{head_tree_hash[:7] if head_tree_hash else 'N/A'}' 无效或丢失，自动回退到最新历史节点: {input_hash[:7]}"
            )

        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
~~~~~
~~~~~python
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            logger.warning(
                f"⚠️  HEAD 指针 '{head_tree_hash[:7] if head_tree_hash else 'N/A'}' 无效或丢失，"
                f"自动回退到最新历史节点: {input_hash[:7]}"
            )

        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
~~~~~

### 下一步建议
- 请执行此计划。
- 执行后，再次运行 `ruff check .` 以确认所有问题均已解决。
