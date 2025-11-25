# 计划：修复 Git 对象存储的分支处理与历史迁移逻辑

## 用户需求
用户在使用 `qd save` 和 `qd history migrate` 时发现，非主干（非最新写入）的历史节点会被丢弃，导致分支（Branching）结构无法被正确记录和显示。具体表现为：
1.  **Writer 逻辑错误**：新节点总是以“最新写入的节点”为父节点，而不是以“Input Tree 对应的节点”为父节点，导致物理上的 Git Commit Graph 总是线性的，无法反映实际的分支拓扑。
2.  **Ref 覆盖问题**：`refs/quipu/history` 总是指向最新节点，导致旧的分支 Tip 变为悬空对象（Dangling Commits），从而被 Reader 忽略。

## 目标
1.  **正确的拓扑链接**：`Writer` 应根据 `input_tree` 查找对应的父 Commit，确保 Git Commit Graph 正确反映逻辑上的父子关系。
2.  **多头（Multi-Head）引用管理**：引入 `refs/quipu/heads/` 命名空间，自动维护所有分支的 Tip，确保没有任何有效的历史节点因为指针移动而丢失。
3.  **迁移修复**：`Migration` 脚本应同样应用上述逻辑，确保旧数据迁移后能保留完整的分支结构。

## 标签
#comp/engine #concept/history #scope/core #fix-branching

---

## Script

### Acts 1: GitDB - 增强查询与引用管理能力

我们需要在底层增加两个能力：
1.  根据 `X-Quipu-Output-Tree` 查找对应的 Commit Hash（用于找到正确的父节点）。
2.  删除引用（用于在节点延伸时清理旧的 Head 引用）。

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_db.py
~~~~~

~~~~~python
    def update_ref(self, ref_name: str, commit_hash: str):
        """
        更新引用 (如 refs/quipu/history)。
        防止 Commit 被 GC 回收。
        """
        self._run(["update-ref", ref_name, commit_hash])

    def get_head_commit(self) -> Optional[str]:
~~~~~

~~~~~python
    def update_ref(self, ref_name: str, commit_hash: str):
        """
        更新引用 (如 refs/quipu/history)。
        防止 Commit 被 GC 回收。
        """
        self._run(["update-ref", ref_name, commit_hash])

    def delete_ref(self, ref_name: str):
        """删除指定的引用"""
        self._run(["update-ref", "-d", ref_name], check=False)

    def get_commit_by_output_tree(self, tree_hash: str) -> Optional[str]:
        """
        根据 Trailer 中的 X-Quipu-Output-Tree 查找对应的 Commit Hash。
        用于在创建新节点时定位语义上的父节点。
        """
        # 使用 grep 搜索所有 refs/quipu/ 下的记录
        # 注意：这假设 Output Tree 是唯一的，这在大概率上是成立的，
        # 且即使有重复（如 merge），找到任意一个作为父节点通常也是可接受的起点。
        cmd = [
            "log",
            "--all",
            f"--grep=X-Quipu-Output-Tree: {tree_hash}",
            "--format=%H",
            "-n", "1"
        ]
        res = self._run(cmd, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return None

    def get_head_commit(self) -> Optional[str]:
~~~~~

### Acts 2: Writer - 修正父节点定位与分支引用维护

修改 `GitObjectHistoryWriter`：
1.  不再盲目使用 `refs/quipu/history` 作为父节点。
2.  使用 `input_tree` 反查父 Commit。
3.  实施 **Head 维护策略**：
    *   为新节点创建 `refs/quipu/heads/<hash>`。
    *   删除父节点的 `refs/quipu/heads/<parent_hash>`（因为它不再是 Tip）。
    *   始终更新 `refs/quipu/history` 指向最新写入，作为一种类似 HEAD 的游标。

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~

~~~~~python
        # 使用 100444 权限 (只读文件)
        tree_descriptor = (
            f"100444 blob {meta_blob_hash}\tmetadata.json\n"
            f"100444 blob {content_blob_hash}\tcontent.md"
        )
        tree_hash = self.git_db.mktree(tree_descriptor)

        last_commit_hash: Optional[str] = None
        res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False, log_error=False)
        if res.returncode == 0:
            last_commit_hash = res.stdout.strip()

        parents = [last_commit_hash] if last_commit_hash else None
        commit_message = f"{summary}\n\nX-Quipu-Output-Tree: {output_tree}"
        new_commit_hash = self.git_db.commit_tree(
            tree_hash=tree_hash, parent_hashes=parents, message=commit_message
        )

        self.git_db.update_ref("refs/quipu/history", new_commit_hash)
        logger.info(f"✅ History node created as commit {new_commit_hash[:7]}")

        # 返回一个 QuipuNode 实例以兼容现有接口
~~~~~

~~~~~python
        # 使用 100444 权限 (只读文件)
        tree_descriptor = (
            f"100444 blob {meta_blob_hash}\tmetadata.json\n"
            f"100444 blob {content_blob_hash}\tcontent.md"
        )
        tree_hash = self.git_db.mktree(tree_descriptor)

        # 1. 确定父节点 (Topological Parent)
        # 根据 input_tree 查找对应的 Commit，而不是盲目使用最新的 history ref
        parent_commit = self.git_db.get_commit_by_output_tree(input_tree)
        parents = [parent_commit] if parent_commit else None
        
        if not parent_commit and input_tree != "4b825dc642cb6eb9a060e54bf8d69288fbee4904":
             # 如果不是创世节点，但找不到父节点，记录警告（可能是断链或首次迁移）
             logger.warning(f"⚠️  Could not find parent commit for input state {input_tree[:7]}. This node may be detached.")

        # 2. 创建 Commit
        commit_message = f"{summary}\n\nX-Quipu-Output-Tree: {output_tree}"
        new_commit_hash = self.git_db.commit_tree(
            tree_hash=tree_hash, parent_hashes=parents, message=commit_message
        )

        # 3. 引用管理 (Multi-Head Strategy)
        # 3.1 总是更新 history 指针到最新操作 (Chronological Head)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)
        
        # 3.2 维护分支 Heads (Topological Heads)
        # 将当前新节点标记为一个 Head
        self.git_db.update_ref(f"refs/quipu/heads/{new_commit_hash}", new_commit_hash)
        
        # 如果父节点之前是 Head，现在它有了孩子，不再是 Head，删除其引用
        if parent_commit:
            self.git_db.delete_ref(f"refs/quipu/heads/{parent_commit}")

        logger.info(f"✅ History node created as commit {new_commit_hash[:7]}")

        # 返回一个 QuipuNode 实例以兼容现有接口
~~~~~

### Acts 3: Migration - 修复迁移逻辑以保留分支

迁移逻辑也需要采用相同的“Head 维护策略”，确保迁移后的结果包含所有分支的 Tip。

~~~~~act
replace packages/quipu-engine/src/quipu/core/migration.py
~~~~~

~~~~~python
            # 6. 更新映射
            tree_to_commit[node.output_tree] = commit_hash
            
            # 7. 更新 Ref (每次都更新，确保 HEAD 指向最新的)
            # 注意：对于分叉的情况，这会导致 HEAD 在不同分支间跳动，最终指向时间戳最新的那个
            # 这对于单线历史是可以的。对于复杂图谱，我们可能需要更复杂的 ref 管理
            # 但 QDPS v1.0 暂定使用单一 refs/quipu/history
            self.git_db.update_ref("refs/quipu/history", commit_hash)
            
            migrated_count += 1
            logger.debug(f"已迁移节点: {node.summary} -> {commit_hash[:7]}")

        logger.info(f"迁移完成。共迁移 {migrated_count} 个节点。")
~~~~~

~~~~~python
            # 6. 更新映射
            tree_to_commit[node.output_tree] = commit_hash
            
            # 7. 引用管理 (Multi-Head Strategy)
            # 总是更新 history 指针到最新迁移的节点
            self.git_db.update_ref("refs/quipu/history", commit_hash)
            
            # 维护分支 Heads
            self.git_db.update_ref(f"refs/quipu/heads/{commit_hash}", commit_hash)
            
            # 如果父节点存在，移除其 Head 引用（因为它已经延伸了）
            if parent_commit:
                self.git_db.delete_ref(f"refs/quipu/heads/{parent_commit}")
            
            migrated_count += 1
            logger.debug(f"已迁移节点: {node.summary} -> {commit_hash[:7]}")

        logger.info(f"迁移完成。共迁移 {migrated_count} 个节点。")
~~~~~

### Acts 4: Test - 添加分支测试用例

添加一个测试用例来验证这种“Checkout 回去再 Save”的分支场景是否能正确生成两个 Head。

~~~~~act
write_file tests/test_branching.py
~~~~~

~~~~~python
import pytest
import subprocess
from quipu.core.git_db import GitDB
from quipu.core.git_object_storage import GitObjectHistoryWriter, GitObjectHistoryReader

@pytest.fixture
def branching_env(tmp_path):
    repo_path = tmp_path / "branch_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)
    
    git_db = GitDB(repo_path)
    writer = GitObjectHistoryWriter(git_db)
    reader = GitObjectHistoryReader(git_db)
    return repo_path, git_db, writer, reader

def test_branching_creation(branching_env):
    """
    测试分支创建场景：
    1. A -> B
    2. Checkout A -> C
    结果应为:
      A -> B
       \-> C
    Reader 应能读取到所有节点。
    """
    repo, git_db, writer, reader = branching_env
    
    # 1. Base Node A
    (repo / "f.txt").write_text("v1")
    hash_a = git_db.get_tree_hash()
    writer.create_node("plan", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", hash_a, "Node A")
    
    # 2. Node B (Child of A)
    (repo / "f.txt").write_text("v2")
    hash_b = git_db.get_tree_hash()
    writer.create_node("plan", hash_a, hash_b, "Node B")
    
    # Verify linear state
    heads = git_db.get_all_ref_heads("refs/quipu/heads")
    assert len(heads) == 1 # Only B should be head
    
    # 3. Branching: Create C from A (Simulate Checkout A then Save C)
    # Physical checkout isn't strictly needed for writer test, just correct input hash
    (repo / "f.txt").write_text("v3")
    hash_c = git_db.get_tree_hash()
    
    # The writer should detect A is the parent based on input_tree=hash_a
    writer.create_node("plan", hash_a, hash_c, "Node C")
    
    # 4. Verify Branching State
    heads = git_db.get_all_ref_heads("refs/quipu/heads")
    assert len(heads) == 2 # B and C should be heads
    
    # 5. Verify Reader sees all
    nodes = reader.load_all_nodes()
    assert len(nodes) == 3
    
    node_map = {n.summary: n for n in nodes}
    node_a = node_map["Node A"]
    node_b = node_map["Node B"]
    node_c = node_map["Node C"]
    
    assert node_b.parent == node_a
    assert node_c.parent == node_a
    assert len(node_a.children) == 2
~~~~~