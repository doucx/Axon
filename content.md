### `fix-cli`: 为 `discard` 命令添加变更预览

#### 目标
增强 `quipu discard` 命令的用户体验。在执行不可逆的删除操作前，明确地告知用户哪些文件的变更将会被丢弃。

#### 基本原理
1.  在 `quipu-cli` 的 `main.py` 文件中找到 `discard` 命令的实现。
2.  在请求用户确认 (`typer.confirm`) 之前，利用 `quipu-engine` 中 `GitDB` 模块已有的 `get_diff_stat` 功能。
3.  `get_diff_stat` 函数可以比较两个 Git Tree Hash 之间的差异，并生成一个类似 `git diff --stat` 的可读摘要。
4.  我们将比较“最新的历史节点 Tree Hash” (目标状态) 和“当前工作区的 Tree Hash” (待丢弃状态) 。
5.  将生成的差异摘要输出到终端，用户即可在确认前看到变更列表。

#### 标签
#fix #cli #enhancement

---

## Script

### Act 1: 在 `discard` 命令中集成差异预览功能

我将修改 `packages/quipu-cli/src/quipu/cli/main.py` 文件，在 `discard` 函数的用户确认步骤前插入获取并显示差异的逻辑。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已经是干净状态 ({latest_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)
    if not force:
        typer.confirm(f"🚨 即将丢弃工作区所有未记录的变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？", abort=True)
    try:
        engine.checkout(target_tree_hash)
~~~~~

~~~~~python
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已经是干净状态 ({latest_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)

    # 显示将要被丢弃的变更
    diff_stat = engine.git_db.get_diff_stat(target_tree_hash, current_hash)
    typer.secho("\n以下是即将被丢弃的变更:", fg=typer.colors.YELLOW, err=True)
    typer.secho("-" * 20, err=True)
    typer.echo(diff_stat, err=True)
    typer.secho("-" * 20, err=True)

    if not force:
        typer.confirm(f"🚨 即将丢弃上述所有变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？", abort=True)
    try:
        engine.checkout(target_tree_hash)
~~~~~