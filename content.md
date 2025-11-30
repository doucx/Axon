好的，这个问题观察得很准确。这是一个典型的空间换时间或空间换简单性的设计选择所带来的后果。当前的设计为了确保绝对的数据安全（没有任何 Quipu 节点被 Git 垃圾回收）和实现的简单性，为每一个创建的节点都保留了一个 `head` 引用。

正如你发现的，这在拥有大量线性历史记录时，会产生大量冗余的引用，占用不必要的磁盘空间并可能降低 `git` 对引用的操作性能。

**解决方案**：

我们将引入一个引用修剪 (Ref Pruning) 机制。其核心逻辑是：**只有图谱中的“叶子”节点 (没有子节点的节点) 才需要被保留为 `head` 引用**。

当一个新节点被创建时，它会成为新的 `head`，而它的父节点（如果之前是 `head` 的话）就不再是 `head` 了，因此其对应的 `head` 引用可以被安全地删除。

我将生成一个计划来修改 `GitObjectHistoryWriter` 的逻辑以实现此优化。

## [WIP] perf: 为本地历史实现引用修剪以减少磁盘占用

### 用户需求
`refs/quipu/local/heads/` 目录下产生了大量的引用文件，导致了不必要的磁盘空间占用。需要优化此行为，只保留必要的引用。

### 评论
这是一个非常重要的性能和空间优化。通过实现引用修剪，我们可以将 `refs` 的数量从 O(n) (n 为节点总数) 降低到 O(k) (k 为分支数量)，在保留历史图谱完整性的前提下，极大地减少了 Git 仓库的元数据体积。

### 目标
1.  修改 `GitObjectHistoryWriter` 的 `create_node` 方法。
2.  在创建新节点的 `head` 引用后，自动删除其父节点的 `head` 引用 (如果存在)。

### 基本原理
Git 的可达性算法决定了，只要一个提交链的末端 (head) 是可达的，那么它的所有祖先提交就都是可达的。当前的实现为链上的每个提交都创建了一个 `head` 引用，这是冗余的。

新的逻辑是：当从父节点 `P` 创建子节点 `C` 时：
1.  我们为 `C` 创建一个新的 `head` 引用 `refs/quipu/local/heads/C`。
2.  `C` 的存在保证了 `P` 的可达性。
3.  因此，`P` 不再需要自己的 `head` 引用 `refs/quipu/local/heads/P`，可以将其安全删除。

这个过程将 `head` 的角色从父节点“传递”给了子节点，确保了只有分支的末端才持有引用。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #concept/state #scope/core 
#ai/instruct
#task/domain/storage
#task/object/ref-management
#task-action/optimize
#task/state/begin

---

### Script

#### Acts 1: 在 `GitObjectHistoryWriter` 中实现引用修剪

我们将修改 `create_node` 方法，在创建新 ref 后，紧接着删除父节点的 ref。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/git_object_storage.py
~~~~~
~~~~~python
        # 3. 引用管理 (QDPS v1.1 - Local Heads Namespace)
        # 在本地工作区命名空间中为新的 commit 创建一个持久化的 head 引用。
        # 这是 push 操作的唯一来源，并且支持多分支图谱，因此不再删除父节点的 head。
        self.git_db.update_ref(f"refs/quipu/local/heads/{new_commit_hash}", new_commit_hash)

        logger.info(f"✅ History node created as commit {new_commit_hash[:7]}")
~~~~~
~~~~~python
        # 3. 引用管理 (QDPS v1.1 - Local Heads Namespace with Pruning)
        # 在本地工作区命名空间中为新的 commit 创建一个持久化的 head 引用。
        self.git_db.update_ref(f"refs/quipu/local/heads/{new_commit_hash}", new_commit_hash)

        # 4. 修剪父节点的冗余 head 引用
        # 新的 head 引用保证了其父节点的可达性，因此父节点的 head 引用变得冗余，可以被安全移除。
        # 这确保了只有图谱的叶子节点才持有 head 引用，显著减少了 ref 数量。
        if parent_commit:
            parent_ref = f"refs/quipu/local/heads/{parent_commit}"
            self.git_db.delete_ref(parent_ref)
            logger.debug(f"Pruned redundant parent ref: {parent_ref}")

        logger.info(f"✅ History node created as commit {new_commit_hash[:7]}")
~~~~~

### 下一步建议
修改完成后，你可以再次运行你的工作流，然后执行 `ls .git/refs/quipu/local/heads | wc -l` 来验证引用数量是否显著减少。对于一个线性历史，它应该接近于 1。
