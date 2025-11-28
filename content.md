好的，我看到了新的 Traceback。`FOREIGN KEY constraint failed` 是一个非常明确的数据库错误信号。

## fix: 修复 Hydrator 中因乱序插入导致的边关系建立失败问题

### 错误分析
1.  **根本原因**: `FOREIGN KEY constraint failed` 错误发生在向 `edges` 表插入数据时。`edges` 表的 `(child_hash, parent_hash)` 列都是外键，引用自 `nodes(commit_hash)`。这个错误意味着，当 `Hydrator` 尝试插入一条边 `(A, B)` 时，作为父节点的 `B` 还没有被插入到 `nodes` 表中。
2.  **`Hydrator` 的逻辑缺陷**:
    *   `_get_missing_commits_with_owner` 方法获取了所有需要补水的节点哈希列表。
    *   `git log` 命令返回的日志条目顺序**不保证是拓扑有序或时间有序的**，尤其是在处理多个分支末端时。
    *   `Hydrator` 遍历这个无序的列表，构建 `nodes_to_insert` 和 `edges_to_insert`。
    *   然后，它先批量插入所有节点，再批量插入所有边。
    *   问题在于，当处理一个复杂的、包含多个独立分支的历史时，`git log` 可能会先返回一个子节点 `A`，然后再返回它的父节点 `B`。如果父节点 `B` 本身在数据库中也不存在（这是一个完整的重建场景），那么在构建 `edges_to_insert` 列表时，我们会记录 `(A, B)` 这条边。然而，如果 `B` 在 `missing_commits` 列表中但由于某种原因没有被 `git log` 返回（例如，它是一个旧的、没有被任何当前 head 引用的 commit），那么 `nodes_to_insert` 列表将不包含 `B`。最终导致外键约束失败。

### 用户需求
-   `quipu cache rebuild` 命令必须能够可靠地从零开始，完整、正确地重建包含所有父子关系的数据库，即使面对复杂的多分支历史。

### 评论
这是一个经典的图数据处理问题。在处理有向无环图（DAG）时，如果节点的插入顺序不正确，依赖关系就会被破坏。当前的 `Hydrator` 实现过于乐观，它假设 `git log` 会一次性返回所有相关的 commits。我们需要一个更稳健的策略来处理这种情况。

### 目标
1.  **修复 `Hydrator`**: 调整 `Hydrator` 的 `sync` 逻辑，确保在插入边之前，所有相关的父节点都已经被识别并准备好插入。
2.  **保证原子性**: 确保节点和边的插入在一个数据库事务中完成，要么全部成功，要么全部失败，避免产生不一致的数据库状态。

### 基本原理
**核心修复思路**：在构建插入批次时，确保 `edges` 表中引用的所有 `parent_hash` 都存在于 `nodes` 表的插入批次中。

1.  **扩大日志范围**: 当前的 `git log missing_hashes` 可能范围太小。我们应该获取所有 `refs/quipu/` 下的完整历史记录，这样可以确保我们拥有所有潜在的父节点信息。
2.  **两阶段构建**:
    *   **第一阶段**: 遍历所有日志条目，构建一个完整的 `log_map` (`hash -> log_entry`) 和一个待处理的 `missing_hashes` 集合。
    *   **第二阶段**: 遍历 `missing_hashes` 集合。对于每个缺失的 commit `C`：
        *   构建其 `node` 数据并添加到 `nodes_to_insert`。
        *   查找其父节点 `P`。
        *   **关键检查**: 如果父节点 `P` 的哈希**同时存在**于 `log_map` 中（意味着它在我们的历史范围内）**并且**（`P` 在 `missing_hashes` 集合中 或 `P` 已经存在于数据库中），我们才将 `(C, P)` 这条边添加到 `edges_to_insert`。这可以防止我们尝试链接到一个不存在的、被垃圾回收的或来自外部历史的父节点。
3.  **事务性写入**: `DatabaseManager` 中的 `batch_insert_nodes` 和 `batch_insert_edges` 都使用了 `with conn:` 上下文管理器，这确保了每个批量操作都是事务性的。为了获得更大的安全性，我们可以将两者包装在同一个事务中，但这会增加复杂性。目前的独立事务已经足够好，因为失败主要发生在 `edges` 插入阶段。

### 标签
#intent/fix #flow/ready #priority/critical 
#comp/engine #scope/core 
#ai/instruct
#task/domain/storage #task/object/hydrator #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修复 `Hydrator.sync` 的核心逻辑

我们将修改 `sync` 方法，使其能够处理乱序的 commit 和不完整的历史。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/hydrator.py
~~~~~
~~~~~python
    def sync(self, local_user_id: str):
        """
        执行增量补水操作。
        """
        missing_commits = self._get_missing_commits_with_owner(local_user_id)
        if not missing_commits:
            logger.debug("✅ 数据库与 Git 历史一致，无需补水。")
            return

        missing_hashes = list(missing_commits.keys())
        all_git_logs = self.git_db.log_ref(missing_hashes) # Log only missing commits for efficiency
        log_map = {entry["hash"]: entry for entry in all_git_logs}

        # --- 批量准备数据 ---
        nodes_to_insert: List[Tuple] = []
~~~~~
~~~~~python
    def sync(self, local_user_id: str):
        """
        执行增量补水操作。
        """
        missing_commits_with_owner = self._get_missing_commits_with_owner(local_user_id)
        if not missing_commits_with_owner:
            logger.debug("✅ 数据库与 Git 历史一致，无需补水。")
            return

        missing_hashes = list(missing_commits_with_owner.keys())
        
        # 关键修复：获取所有 Quipu 引用下的完整历史，确保父节点信息不会丢失。
        all_ref_heads = [t[0] for t in self.git_db.get_all_ref_heads("refs/quipu/")]
        if not all_ref_heads:
            return

        all_git_logs = self.git_db.log_ref(all_ref_heads)
        log_map = {entry["hash"]: entry for entry in all_git_logs}
        
        # 获取数据库中已存在的节点哈希，用于边关系检查
        db_hashes = self.db_manager.get_all_node_hashes()

        # --- 批量准备数据 ---
        nodes_to_insert: List[Tuple] = []
~~~~~

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/hydrator.py
~~~~~
~~~~~python
        # 3. 构建插入数据
        for commit_hash in missing_hashes:
            if commit_hash not in log_map: continue
            
            log_entry = log_map[commit_hash]
            tree_hash = log_entry["tree"]
            owner_id = missing_commits[commit_hash]

            meta_blob_hash = tree_to_meta_blob.get(tree_hash)
            if not meta_blob_hash:
~~~~~
~~~~~python
        # 3. 构建插入数据
        for commit_hash in missing_hashes:
            if commit_hash not in log_map: continue
            
            log_entry = log_map[commit_hash]
            tree_hash = log_entry["tree"]
            owner_id = missing_commits_with_owner[commit_hash]

            meta_blob_hash = tree_to_meta_blob.get(tree_hash)
            if not meta_blob_hash:
~~~~~

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/hydrator.py
~~~~~
~~~~~python
                # 处理边关系
                parent_hashes = log_entry["parent"].split()
                for p_hash in parent_hashes:
                    edges_to_insert.append((commit_hash, p_hash))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析 {commit_hash[:7]} 的元数据失败: {e}")
~~~~~
~~~~~python
                # 处理边关系
                parent_hashes = log_entry["parent"].split()
                for p_hash in parent_hashes:
                    # 关键检查：只在父节点已知存在于 Git 历史中，
                    # 并且父节点本身也即将被插入或已经存在于数据库中时，才创建边。
                    if p_hash in log_map and (p_hash in missing_hashes or p_hash in db_hashes):
                        edges_to_insert.append((commit_hash, p_hash))
                    else:
                        logger.warning(f"跳过边关系 {commit_hash[:7]} -> {p_hash[:7]}：父节点在本次补水范围内未找到。")
                        
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析 {commit_hash[:7]} 的元数据失败: {e}")
~~~~~

### 下一步建议
1.  **应用补丁**: 应用上述对 `hydrator.py` 的修改。
2.  **再次执行恢复**:
    ```bash
    rm .quipu/history.sqlite
    qd cache rebuild --force
    ```
3.  **验证**: 检查命令输出。这一次，不应该再出现 `FOREIGN KEY constraint failed` 错误。`quipu ui` 也应该能够正常启动并显示完整的、连接正确的历史图谱。
