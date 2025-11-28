好的，完全同意。我们分步进行，先修复核心的 Git 同步逻辑，同时保持架构的灵活性，以便未来引入 SQLite 优化和其他同步策略。

### 修复方案：`sync` 的安全实现

我们将按照“拉取 -> 调和 -> 推送” (Fetch -> Reconcile -> Push) 的无损模型来重构 `sync` 流程。

**核心改动点**：
1.  **修改 `push_quipu_refs`**: 从 `git push` 命令中移除危险的 `--prune` 选项。
2.  **新增 `reconcile_local_with_remote`**: 在 `GitDB` 中实现一个新的方法，用于将远程拉取下来的历史安全地合并到本地。
3.  **调整 `sync` 命令**: 在 `quipu-cli` 的 `remote.py` 中，调整 `sync` 命令的执行顺序，插入新的调和步骤。

我们将首先在 `quipu-engine` 中完成底层能力的修改。

---

### 计划

## [WIP] refactor: 重构 sync 机制以支持无损多设备同步

### 用户需求
当前的 `quipu sync` 命令在多设备场景下存在数据丢失的风险。这是因为 `push --prune` 会用当前设备不完整的本地历史覆盖远程的完整历史。需要将 `sync` 流程重构为一个安全的、非破坏性的双向同步模型。

### 评论
这是一个关键的架构修复，解决了之前设计中的严重缺陷。新的“拉取-调和-推送”模型将确保用户可以在多个设备之间安全、无缝地工作，而不会丢失任何历史记录。

### 目标
1.  在 `GitDB` 中移除 `push` 操作的 `--prune` 选项，使其变为非破坏性操作。
2.  在 `GitDB` 中增加一个新的 `reconcile` 方法，用于将远程获取的 refs 安全地合并到本地工作区。
3.  调整 `quipu-cli` 中的 `sync` 命令，使其遵循 `Fetch -> Reconcile -> Push` 的正确顺序。

### 基本原理
通过将 `sync` 从一个单向的“镜像推送”操作，转变为一个真正的双向同步操作，来保证数据的完整性。首先拉取远程的全量数据到本地的一个隔离命名空间，然后通过一个新的“调和”步骤将这些新数据安全地合并到本地工作区，最后再将这个合并后的、最完整的本地状态推送回远程。这个过程确保了任何时候都不会有数据被意外删除。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #comp/cli #concept/sync #scope/core #ai/brainstorm #task/domain/sync #task/object/multi-device #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: [Engine] 移除 `push` 的破坏性 `--prune` 选项

首先，我们修改 `quipu-engine` 包中的 `git_db.py`，让 `push` 操作变得安全。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
    def push_quipu_refs(self, remote: str, user_id: str):
        """
        将本地 Quipu heads 推送到远程用户专属的命名空间。
        遵循 QDPS v1.1 规范。
        """
        refspec = f"refs/quipu/local/heads/*:refs/quipu/users/{user_id}/heads/*"
        logger.info(f"🚀 Pushing Quipu history to {remote} for user {user_id}...")
        self._run(["push", remote, "--prune", refspec])
~~~~~
~~~~~python
    def push_quipu_refs(self, remote: str, user_id: str):
        """
        将本地 Quipu heads 推送到远程用户专属的命名空间。
        遵循 QDPS v1.1 规范。
        """
        refspec = f"refs/quipu/local/heads/*:refs/quipu/users/{user_id}/heads/*"
        logger.info(f"🚀 Pushing Quipu history to {remote} for user {user_id}...")
        # 移除了 --prune 选项，使推送操作变为非破坏性。
        self._run(["push", remote, refspec])
~~~~~

#### Acts 2: [Engine] 实现本地与远程的调和逻辑

接下来，在 `GitDB` 类中添加 `reconcile_local_with_remote` 方法。这个方法是新模型的**核心**。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
        logger.info(f"🔍 Fetching Quipu history from {remote} for user {user_id}...")
        self._run(["fetch", remote, "--prune", refspec])
~~~~~
~~~~~python
        logger.info(f"🔍 Fetching Quipu history from {remote} for user {user_id}...")
        self._run(["fetch", remote, "--prune", refspec])

    def reconcile_local_with_remote(self, remote: str, user_id: str):
        """
        将远程拉取下来的历史 (remotes) 与本地历史 (local) 进行调和。
        这是一个安全的操作，只会添加本地不存在的远程引用。
        """
        remote_heads_prefix = f"refs/quipu/remotes/{remote}/{user_id}/heads/"
        remote_heads = self.get_all_ref_heads(remote_heads_prefix)
        if not remote_heads:
            logger.debug("No remote refs found to reconcile.")
            return

        reconciled_count = 0
        for commit_hash, remote_ref in remote_heads:
            # e.g., remote_ref = refs/quipu/remotes/origin/user/heads/abc...
            #       local_ref should be refs/quipu/local/heads/abc...
            local_ref_suffix = remote_ref.replace(remote_heads_prefix, "")
            local_ref = f"refs/quipu/local/heads/{local_ref_suffix}"

            # 使用 rev-parse 检查本地 ref 是否已存在
            # 如果本地已经存在，我们假设它是最新的或用户有意为之，不做任何操作
            check_res = self._run(["rev-parse", "--verify", local_ref], check=False, log_error=False)
            if check_res.returncode != 0:
                # 本地不存在此 ref，从远程镜像创建它
                self.update_ref(local_ref, commit_hash)
                reconciled_count += 1
                logger.info(f"🤝 Reconciled: Added new history branch -> {commit_hash[:7]}")

        if reconciled_count > 0:
            logger.info(f"✅ Reconciliation complete. Added {reconciled_count} new history branches from remote.")
        else:
            logger.debug("✅ Local history is already up-to-date with remote.")
~~~~~

#### Acts 3: [CLI] 调整 `sync` 命令的执行顺序

最后，我们修改 `quipu-cli` 包中的 `remote.py`，应用新的同步流程。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/remote.py
~~~~~
~~~~~python
        try:
            git_db = GitDB(sync_dir)

            typer.secho(f"⬆️  正在向 '{remote}' 推送你的本地历史...", fg=typer.colors.BLUE, err=True)
            git_db.push_quipu_refs(remote, final_user_id)

            subscriptions = config.get("sync.subscriptions", [])
            target_ids_to_fetch = set(subscriptions)
            target_ids_to_fetch.add(final_user_id)

            if target_ids_to_fetch:
                typer.secho(
                    f"⬇️  正在从 '{remote}' 拉取 {len(target_ids_to_fetch)} 个用户的历史...", fg=typer.colors.BLUE, err=True
                )
                for target_id in sorted(list(target_ids_to_fetch)):
                    git_db.fetch_quipu_refs(remote, target_id)

            typer.secho("\n✅ Quipu 引用同步完成。", fg=typer.colors.GREEN, err=True)
            typer.secho("\n💡 提示: 运行 `quipu cache sync` 来更新本地数据库和 UI 视图。", fg=typer.colors.YELLOW, err=True)

        except RuntimeError as e:
~~~~~
~~~~~python
        try:
            git_db = GitDB(sync_dir)

            # --- Stage 1: Fetch ---
            subscriptions = config.get("sync.subscriptions", [])
            target_ids_to_fetch = set(subscriptions)
            target_ids_to_fetch.add(final_user_id)

            if target_ids_to_fetch:
                typer.secho(
                    f"⬇️  正在从 '{remote}' 拉取 {len(target_ids_to_fetch)} 个用户的历史...", fg=typer.colors.BLUE, err=True
                )
                for target_id in sorted(list(target_ids_to_fetch)):
                    git_db.fetch_quipu_refs(remote, target_id)

            # --- Stage 2: Reconcile ---
            typer.secho(f"🤝 正在将远程历史与本地进行调和...", fg=typer.colors.BLUE, err=True)
            git_db.reconcile_local_with_remote(remote, final_user_id)

            # --- Stage 3: Push ---
            typer.secho(f"⬆️  正在向 '{remote}' 推送合并后的本地历史...", fg=typer.colors.BLUE, err=True)
            git_db.push_quipu_refs(remote, final_user_id)


            typer.secho("\n✅ Quipu 双向同步完成。", fg=typer.colors.GREEN, err=True)
            typer.secho("\n💡 提示: 运行 `quipu cache sync` 来更新本地数据库和 UI 视图。", fg=typer.colors.YELLOW, err=True)

        except RuntimeError as e:
~~~~~

### 下一步建议
在执行此计划后，我们需要：
1.  手动运行 `quipu sync` 并观察日志输出，确保 `Fetch -> Reconcile -> Push` 的顺序正确执行。
2.  （可选）编写一个集成测试，模拟多设备同步场景，验证数据不会丢失。
3.  讨论为 `sync` 命令添加不同策略（如 `--force-push`，`--fetch-only`）的接口设计。
