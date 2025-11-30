分析正确。测试失败是因为我生成的 `patch_file` 指令存在两个严重问题：

1.  **参数缺失**：在修改 `cli.json` 时，我只提供了一个 JSON 块，导致 `patch_file` 缺少 `new_string` 参数（或 `old_string`，视解析器而定）。
2.  **上下文认知错误**：在修改 `git_object_storage.py` 时，我错误地认为文件中尚未包含“引用修剪”的逻辑。实际上，**文件中已经包含了修剪逻辑的代码**，但由于上层 `Engine` 未传递正确的 `parent_commit_hash`，导致该逻辑未能生效。因此，Act 2 的目标应该是修改父节点的获取逻辑，而不是重新添加修剪代码。

### 解决方案
1.  **修正 JSON Patch**：为 `cli.json` 提供明确的 `old_string`（锚点）和 `new_string`（锚点+新内容）。
2.  **修正 Storage Patch**：基于文件的**真实内容**，仅修改 `create_node` 方法开头获取 `parent_commit` 的部分，使其优先使用 `kwargs`。
3.  **保留其他 Acts**：`state_machine.py` 的修改（传递参数）和 `cache.py` 的新增命令（清理工具）是正确的。

## [WIP] fix: 修复节点引用管理并添加清理工具

### 错误分析
1.  `cli.json` 的 `patch_file` 操作失败，因为只提供了一个参数块，不符合 `[path, old, new]` 的签名。
2.  `git_object_storage.py` 中虽然已存在引用修剪代码，但由于 `Engine` 未传递 `parent_commit_hash`，且基于 `output_tree` 的反查在幂等操作中不可靠，导致修剪逻辑失效。

### 用户需求
1.  修复 `patch_file` 语法错误。
2.  修复引用修剪逻辑，通过显式传递 `parent_commit_hash` 解决引用膨胀问题。
3.  提供 `quipu cache prune-refs` 工具清理现有冗余。

### 评论
这是一个纠正性的修复。关键在于正确地 Patch 现有代码，并补全缺失的参数。

### 目标
1.  修正 `cli.json` 的 Patch 操作。
2.  修改 `GitObjectHistoryWriter` 以优先从 `kwargs` 获取父节点。
3.  修改 `Engine` 以传递父节点 Commit Hash。
4.  实现 `prune-refs` 命令。

### 基本原理
-   **JSON Patch**: 使用现有的键值对作为锚点进行追加。
-   **Logic Fix**: 只有当 `Engine` 明确告知谁是父节点时，Writer 才能放心地删除父节点的引用。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/cli #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/ref-management #task/action/prune #task/state/continue

---

### Script

#### Acts 1: 更新本地化文件 (修正版)

使用 `cache.rebuild.error.deleteFailed` 作为锚点，在其后追加新键值对。

~~~~~act
patch_file
packages/quipu-common/src/pyquipu/common/locales/zh/cli.json
~~~~~
~~~~~json
  "cache.rebuild.error.deleteFailed": "❌ 删除旧数据库失败: {error}",
~~~~~
~~~~~json
  "cache.rebuild.error.deleteFailed": "❌ 删除旧数据库失败: {error}",
  "cache.prune.info.scanning": "🔍 正在扫描冗余引用...",
  "cache.prune.info.found": "🗑️  发现 {count} 个冗余引用 (总计 {total} 个 heads)。",
  "cache.prune.success": "✅ 清理完成，已删除 {count} 个引用。",
  "cache.prune.info.noRedundant": "✅ 未发现冗余引用。",
~~~~~

#### Acts 2: 修改 `GitObjectHistoryWriter` 以支持显式父节点 (修正版)

修改 `create_node` 方法的开头，使其优先检查 `kwargs` 中的 `parent_commit_hash`。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/git_object_storage.py
~~~~~
~~~~~python
        # 1. 确定父节点 (Topological Parent)
        parent_commit = self.git_db.get_commit_by_output_tree(input_tree)
        parents = [parent_commit] if parent_commit else None

        if not parent_commit and input_tree != "4b825dc642cb6eb9a060e54bf8d69288fbee4904":
~~~~~
~~~~~python
        # 1. 确定父节点 (Topological Parent)
        # 优先使用 Engine 提供的确切父节点，仅在未提供时回退到 Tree 反查
        parent_commit = kwargs.get("parent_commit_hash")
        if not parent_commit:
            parent_commit = self.git_db.get_commit_by_output_tree(input_tree)
            
        parents = [parent_commit] if parent_commit else None

        if not parent_commit and input_tree != "4b825dc642cb6eb9a060e54bf8d69288fbee4904":
~~~~~

#### Acts 3: 修改 `Engine` 以传递 `parent_commit_hash`

更新 `Engine.capture_drift`。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~python
        user_id = self._get_current_user_id()

        new_node = self.writer.create_node(
            node_type="capture",
            input_tree=input_hash,
            output_tree=current_hash,
            content=body,
            message=message,
            owner_id=user_id,
        )

        self.history_graph[new_node.commit_hash] = new_node
~~~~~
~~~~~python
        user_id = self._get_current_user_id()
        parent_hash = self.current_node.commit_hash if self.current_node else None

        new_node = self.writer.create_node(
            node_type="capture",
            input_tree=input_hash,
            output_tree=current_hash,
            content=body,
            message=message,
            owner_id=user_id,
            parent_commit_hash=parent_hash,
        )

        self.history_graph[new_node.commit_hash] = new_node
~~~~~

更新 `Engine.create_plan_node`。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/state_machine.py
~~~~~
~~~~~python
        user_id = self._get_current_user_id()

        new_node = self.writer.create_node(
            node_type="plan",
            input_tree=input_tree,
            output_tree=output_tree,
            content=plan_content,
            summary_override=summary_override,
            owner_id=user_id,
        )

        self.history_graph[new_node.commit_hash] = new_node
~~~~~
~~~~~python
        user_id = self._get_current_user_id()
        parent_hash = self.current_node.commit_hash if self.current_node else None

        new_node = self.writer.create_node(
            node_type="plan",
            input_tree=input_tree,
            output_tree=output_tree,
            content=plan_content,
            summary_override=summary_override,
            owner_id=user_id,
            parent_commit_hash=parent_hash,
        )

        self.history_graph[new_node.commit_hash] = new_node
~~~~~

#### Acts 4: 实现 `quipu cache prune-refs` 命令

添加一个新的子命令到 `cache` 组。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/cache.py
~~~~~
~~~~~python
    cache_sync(ctx, work_dir)
~~~~~
~~~~~python
    cache_sync(ctx, work_dir)


@cache_app.command("prune-refs")
def cache_prune_refs(
    ctx: typer.Context,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
):
    """
    清理 refs/quipu/local/heads/ 下的冗余引用。
    只保留分支末端 (Leaves)，删除中间节点的引用。
    """
    setup_logging()
    
    with engine_context(work_dir) as engine:
        bus.info("cache.prune.info.scanning")
        
        # 1. 获取所有本地 heads
        local_heads = engine.git_db.get_all_ref_heads("refs/quipu/local/heads/")
        if not local_heads:
            bus.success("cache.prune.info.noRedundant")
            return

        head_commits = {h[0] for h in local_heads}
        
        # 2. 批量获取这些 commit 的内容以解析 parent
        commits_content = engine.git_db.batch_cat_file(list(head_commits))
        
        parents_of_heads = set()
        for c_hash, content in commits_content.items():
            text = content.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if line.startswith("parent "):
                    p_hash = line.split()[1]
                    parents_of_heads.add(p_hash)
                elif line == "":
                    break 
        
        # 3. 计算交集：既是 Head 又是某个 Head 的 Parent -> 冗余
        redundant_commits = head_commits.intersection(parents_of_heads)
        
        if not redundant_commits:
            bus.success("cache.prune.info.noRedundant")
            return

        # 4. 找出对应的 ref names 并删除
        refs_to_delete = []
        for c_hash, ref_name in local_heads:
            if c_hash in redundant_commits:
                refs_to_delete.append(ref_name)
        
        bus.info("cache.prune.info.found", count=len(refs_to_delete), total=len(local_heads))
        
        deleted_count = 0
        for ref in refs_to_delete:
            engine.git_db.delete_ref(ref)
            deleted_count += 1
            
        bus.success("cache.prune.success", count=deleted_count)
~~~~~

### 下一步建议
1.  执行 `quipu cache prune-refs` 清理旧数据。
2.  再次执行 `qd run a`，验证新的引用机制是否生效（引用总数不应增加，或者如果是分支末端，则总数不变）。
