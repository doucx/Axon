在 `checkout` 命令中，变量 `target_tree_hash` 被错误地使用，而实际定义的变量名是 `target_output_tree_hash`。这导致了 `NameError` 并使得相关测试失败。

## fix: 修复 checkout 命令中的变量名错误

### 错误分析
测试失败显示 `checkout` 命令抛出了 `NameError: name 'target_tree_hash' is not defined`。这是因为在之前的重构中，变量被重命名为 `target_output_tree_hash` 以提高清晰度，但函数内部的引用未完全更新。

### 用户需求
修复 `checkout` 命令，确保其能正常工作并通过所有测试。

### 评论
这是一个关键的修复，用于保证导航功能的核心逻辑正确。

### 目标
修正 `packages/quipu-cli/src/quipu/cli/main.py` 中的 `checkout` 函数。

### 基本原理
将所有对 `target_tree_hash` 的引用替换为 `target_output_tree_hash`。

### 标签
#intent/fix #flow/ready #priority/high
#comp/cli #concept/navigation #scope/core
#ai/instruct
#task/domain/storage #task/object/api-contract #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修复 checkout 变量引用

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~old_string
    target_node = matches[0]
    target_output_tree_hash = target_node.output_tree

    current_hash = engine.git_db.get_tree_hash()
    if current_hash == target_tree_hash:
        typer.secho(f"✅ 工作区已处于目标状态 ({target_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)

    is_dirty = engine.current_node is None or engine.current_node.output_tree != current_hash
    if is_dirty:
        typer.secho("⚠️  检测到当前工作区存在未记录的变更，将自动创建捕获节点...", fg=typer.colors.YELLOW, err=True)
        engine.capture_drift(current_hash)
        typer.secho("✅ 变更已捕获。", fg=typer.colors.GREEN, err=True)
        current_hash = engine.git_db.get_tree_hash()

    diff_stat = engine.git_db.get_diff_stat(current_hash, target_tree_hash)
    if diff_stat:
        typer.secho("\n以下是将要发生的变更:", fg=typer.colors.YELLOW, err=True)
        typer.secho("-" * 20, err=True)
        typer.echo(diff_stat, err=True)
        typer.secho("-" * 20, err=True)

    if not force:
        prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    _execute_visit(ctx, engine, target_tree_hash, f"正在导航到节点: {target_node.short_hash}")
~~~~~
~~~~~new_string
    target_node = matches[0]
    target_output_tree_hash = target_node.output_tree

    current_hash = engine.git_db.get_tree_hash()
    if current_hash == target_output_tree_hash:
        typer.secho(f"✅ 工作区已处于目标状态 ({target_node.short_hash})，无需操作。", fg=typer.colors.GREEN, err=True)
        ctx.exit(0)

    is_dirty = engine.current_node is None or engine.current_node.output_tree != current_hash
    if is_dirty:
        typer.secho("⚠️  检测到当前工作区存在未记录的变更，将自动创建捕获节点...", fg=typer.colors.YELLOW, err=True)
        engine.capture_drift(current_hash)
        typer.secho("✅ 变更已捕获。", fg=typer.colors.GREEN, err=True)
        current_hash = engine.git_db.get_tree_hash()

    diff_stat = engine.git_db.get_diff_stat(current_hash, target_output_tree_hash)
    if diff_stat:
        typer.secho("\n以下是将要发生的变更:", fg=typer.colors.YELLOW, err=True)
        typer.secho("-" * 20, err=True)
        typer.echo(diff_stat, err=True)
        typer.secho("-" * 20, err=True)

    if not force:
        prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
        if not _prompt_for_confirmation(prompt, default=False):
            typer.secho("\n🚫 操作已取消。", fg=typer.colors.YELLOW, err=True)
            raise typer.Abort()

    _execute_visit(ctx, engine, target_output_tree_hash, f"正在导航到节点: {target_node.short_hash}")
~~~~~

### 下一步建议
运行测试验证修复结果。
