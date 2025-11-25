# 任务：实现 `axon save` 微提交功能

## 第一步：修改核心引擎 `capture_drift`

我们为 `capture_drift` 函数增加一个可选的 `message` 参数，并用它来丰富生成的快照内容和 Git 锚点信息。

~~~act
replace
~~~
~~~path
core/engine.py
~~~
~~~python
    def capture_drift(self, current_hash: str) -> AxonNode:
        """
        捕获当前工作区的漂移，生成一个新的 CaptureNode。
        """
        logger.info(f"📸 正在捕获工作区漂移，新状态 Hash: {current_hash[:7]}")
        
        # 1. 确定父节点
        # 使用 Git 官方的 Empty Tree Hash 作为创世基准
        # 这允许 diff-tree 正确计算从"无"到"有"的变更
        input_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        last_commit_hash = None
        
        if self.history_graph:
            # 按时间戳找到最近的节点作为父节点
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            # 获取上一个锚点 commit 用于链接历史
            parent_ref_commit_result = self.git_db._run(["rev-parse", "refs/axon/history"], check=False)
            if parent_ref_commit_result.returncode == 0:
                last_commit_hash = parent_ref_commit_result.stdout.strip()

        # 2. 生成差异摘要
        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
        
        # 3. 构建节点内容和元数据
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_hash}_{current_hash}_{ts_str}.md"
        
        meta = {
            "type": "capture",
            "input_tree": input_hash,
            "output_tree": current_hash
        }
        body = (
            f"# 📸 Snapshot Capture\n\n"
            f"检测到工作区发生变更。\n\n"
            f"### 📝 变更文件摘要:\n```\n{diff_summary}\n```"
        )
        
        # 4. 写入文件
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        filename.write_text(frontmatter + body, "utf-8")
        
        # 5. 创建锚点 Commit 并更新引用
        commit_msg = f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else []
        new_commit_hash = self.git_db.create_anchor_commit(current_hash, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/axon/history", new_commit_hash)

        # 6. 在内存中创建并返回新节点
        new_node = AxonNode(
            input_tree=input_hash,
            output_tree=current_hash,
            timestamp=timestamp,
            filename=filename,
            node_type="capture",
            content=body
        )
        
        # 7. 更新引擎内部状态
        self.history_graph[current_hash] = new_node
        self.current_node = new_node
        
        logger.info(f"✅ 捕获完成，新节点已创建: {filename.name}")
        return new_node
~~~
~~~python
    def capture_drift(self, current_hash: str, message: Optional[str] = None) -> AxonNode:
        """
        捕获当前工作区的漂移，生成一个新的 CaptureNode。
        可以附带一条可选的消息。
        """
        log_message = f"📸 正在捕获工作区漂移 (Message: {message})" if message else f"📸 正在捕获工作区漂移"
        logger.info(f"{log_message}，新状态 Hash: {current_hash[:7]}")

        # 1. 确定父节点
        input_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904" # Git Empty Tree Hash
        last_commit_hash = None
        
        if self.history_graph:
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            parent_ref_commit_result = self.git_db._run(["rev-parse", "refs/axon/history"], check=False)
            if parent_ref_commit_result.returncode == 0:
                last_commit_hash = parent_ref_commit_result.stdout.strip()

        # 2. 生成差异摘要
        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
        
        # 3. 构建节点内容和元数据
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_hash}_{current_hash}_{ts_str}.md"
        
        meta = {"type": "capture", "input_tree": input_hash, "output_tree": current_hash}
        
        # 动态构建 Markdown Body
        user_message_section = f"### 💬 备注:\n{message}\n\n" if message else ""
        body = (
            f"# 📸 Snapshot Capture\n\n"
            f"{user_message_section}"
            f"检测到工作区发生变更。\n\n"
            f"### 📝 变更文件摘要:\n```\n{diff_summary}\n```"
        )
        
        # 4. 写入文件
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        filename.write_text(frontmatter + body, "utf-8")
        
        # 5. 创建锚点 Commit 并更新引用
        commit_msg = f"Axon Save: {message}" if message else f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else []
        new_commit_hash = self.git_db.create_anchor_commit(current_hash, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/axon/history", new_commit_hash)

        # 6. 在内存中创建并返回新节点
        new_node = AxonNode(
            input_tree=input_hash,
            output_tree=current_hash,
            timestamp=timestamp,
            filename=filename,
            node_type="capture",
            content=body
        )
        
        # 7. 更新引擎内部状态
        self.history_graph[current_hash] = new_node
        self.current_node = new_node
        
        logger.info(f"✅ 捕获完成，新节点已创建: {filename.name}")
        return new_node
~~~

## 第二步：在 `main.py` 中添加 `save` 命令

我们将 `save` 命令添加到 CLI 中，使其成为用户可用的功能。我把它放在 `sync` 命令之前，保持逻辑分组。

~~~act
replace
~~~
~~~path
main.py
~~~
~~~python
@app.command()
def sync(
    ctx: typer.Context,
~~~
~~~python
@app.command()
def save(
    ctx: typer.Context,
    message: Annotated[Optional[str], typer.Argument(help="本次快照的简短描述。")] = None,
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
):
    """
    捕获当前工作区的状态，创建一个“微提交”快照。

    这是一种轻量级的版本控制，用于记录开发过程中的思考步骤，
    而无需创建正式的 Git Commit。
    """
    setup_logging()
    
    engine = Engine(work_dir)
    status = engine.align()
    
    if status == "CLEAN":
        typer.secho("✅ 工作区状态未发生变化，无需创建快照。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)
    
    current_hash = engine.git_db.get_tree_hash()
    try:
        node = engine.capture_drift(current_hash, message=message)
        msg_suffix = f' ({message})' if message else ''
        typer.secho(f"📸 快照已保存: {node.short_hash}{msg_suffix}", fg=typer.colors.GREEN, err=True)
    except Exception as e:
        typer.secho(f"❌ 创建快照失败: {e}", fg=typer.colors.RED, err=True)
        ctx.exit(1)


@app.command()
def sync(
    ctx: typer.Context,
~~~

## 第三步：更新 CLI 文档

最后，我们将新命令的用法添加到用户文档中，以便其他人也能发现并使用这个强大的功能。

~~~act
append_file
~~~
~~~path
docs/03_user_guide/02_cli_reference.md
~~~
~~~markdown

## `save` - 保存快照 (微提交)

创建一个当前工作区状态的轻量级快照。

```bash
axon save "[MESSAGE]" [OPTIONS]
```

*   `[MESSAGE]`: (可选) 为这个快照添加一句描述，例如 "尝试修复 bug" 或 "重构前的状态"。
*   `--work-dir, -w`: 指定工作区。

**核心用途**:
`save` 命令填补了“编辑器撤销”和“Git 提交”之间的巨大空白。它允许你以极低的成本、极高的频率保存你的工作进度，而不会污染 Git 的主提交历史。你可以把它看作是一个拥有无限历史记录的“存盘点”。
~~~

## 完成

所有修改已定义完毕。执行此脚本后，`axon save` 功能即可使用。