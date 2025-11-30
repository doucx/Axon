分析正确。

`ruff` 检查出了两个问题：
1.  **`cache.py` 中的逻辑错误**：`cache_rebuild` 命令中有一段孤立的代码块，它引用了在该代码块作用域之外才定义的变量 `force` 和 `db_path`。这段代码是从 `cache_rebuild` 函数的早期版本遗留下来的，现在已经不再被 `cache_rebuild` 的主逻辑路径覆盖，成为了死代码和语法错误。
2.  **`test_cache_commands.py` 中的未使用变量**：在 `history_with_redundant_refs` fixture 中，我们捕获了 `capture_drift` 的返回值（`QuipuNode` 实例），但后续没有使用它们。这虽然不影响功能，但属于代码整洁性问题。

### 解决方案
1.  **修复 `cache.py`**：安全地删除 `cache_rebuild` 函数中那段孤立的、无法访问的死代码。
2.  **修复 `test_cache_commands.py`**：移除对 `capture_drift` 返回值的不必要赋值。

## [WIP] fix: 修复 ruff 检查出的代码问题

### 错误分析
1.  `pyquipu/cli/commands/cache.py`：`cache_rebuild` 函数包含一段与主逻辑分离的死代码块，该代码块错误地引用了未在其作用域内定义的 `force` 和 `db_path` 变量。
2.  `tests/cli/test_cache_commands.py`：`history_with_redundant_refs` fixture 中存在对 `capture_drift` 返回值的不必要赋值，导致 `ruff` 报告 `F841 Local variable ... is assigned to but never used` 警告。

### 用户需求
修复 `ruff check .` 报告的所有错误，确保代码库的静态分析纯净。

### 评论
这些是由 `ruff` 静态分析工具发现的代码质量问题。及时修复它们有助于保持代码库的健康、可读性和可维护性。

### 目标
1.  删除 `cache.py` 中的死代码块。
2.  移除 `test_cache_commands.py` 中的未使用变量赋值。

### 基本原理
通过移除无效代码和不必要的赋值，我们直接解决了 `ruff` 报告的问题根源，使代码更简洁、更正确。

### 标签
#intent/fix #flow/ready #priority/medium #comp/cli #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 移除 `cache.py` 中的死代码

我们将删除 `cache_rebuild` 函数末尾那段孤立的 `if not force:` 代码块。

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/commands/cache.py
~~~~~
~~~~~python
    if not force:
        prompt = f"🚨 即将删除并重建数据库 {db_path}。\n此操作不可逆。是否继续？"
        if not prompt_for_confirmation(prompt, default=False):
            bus.warning("common.prompt.cancel")
            raise typer.Abort()

    try:
        db_path.unlink()
        bus.info("cache.rebuild.info.deleting")
    except (OSError, PermissionError) as e:
        logger.error(f"删除旧数据库文件 '{db_path}' 失败", exc_info=True)
        bus.error("cache.rebuild.error.deleteFailed", error=str(e))
        ctx.exit(1)

    cache_sync(ctx, work_dir)
~~~~~
~~~~~python
~~~~~

#### Acts 2: 移除测试文件中的未使用变量

我们将修改 `history_with_redundant_refs` fixture，不再接收 `capture_drift` 的返回值。

~~~~~act
patch_file
tests/cli/test_cache_commands.py
~~~~~
~~~~~python
    # root
    (ws / "file.txt").write_text("v0")
    h0 = engine.git_db.get_tree_hash()
    n_root = engine.capture_drift(h0, "root")

    # n1
    (ws / "file.txt").write_text("v1")
    h1 = engine.git_db.get_tree_hash()
    n1 = engine.capture_drift(h1, "n1")

    # n2 (branch point)
    (ws / "file.txt").write_text("v2")
~~~~~
~~~~~python
    # root
    (ws / "file.txt").write_text("v0")
    h0 = engine.git_db.get_tree_hash()
    engine.capture_drift(h0, "root")

    # n1
    (ws / "file.txt").write_text("v1")
    h1 = engine.git_db.get_tree_hash()
    engine.capture_drift(h1, "n1")

    # n2 (branch point)
    (ws / "file.txt").write_text("v2")
~~~~~

### 下一步建议
再次运行 `ruff check .` 以确认所有问题都已解决。如果检查通过，我们就可以将这些修复作为一个独立的提交进行归档。
