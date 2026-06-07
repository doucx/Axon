我们已经成功在本地激活了 `raw` 语言模式，目前本地与远端 CI 的环境已经达成高度统一：它们都通过总线输出原始的消息 Key 标识符。

剩下的 8 个失败用例是因为测试代码仍在断言旧的中文翻译。我将把这些硬编码的文本全部替换为对应的 Key 标识符。

## [WIP] fix(tests): 完成集成测试向 Key 标识符断言的全面迁移

### 用户需求
将 `test_storage_selection.py` 和 `test_sync_modes.py` 中遗留的硬编码中文断言替换为 Key 标识符，使测试在 `raw` 语言模式下全绿。

### 评论
这次迁移彻底解决了测试套件对翻译文件的脆弱依赖。由于本地和 CI 均强制开启 `raw` 模式，我们的断言现在是绝对稳定的。

### 目标
1.  修正 `test_storage_selection.py` 中的快照保存、日志头、查找头和无结果提示断言。
2.  修正 `test_sync_modes.py` 中的推送、拉取、强制推送和修剪提示断言。

### 标签
#intent/refine #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/i18n-raw-mode #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 修正 `tests/integration/test_storage_selection.py`

我们将替换所有 UI 相关的字符串匹配。

~~~~~act
patch_file
tests/integration/test_storage_selection.py
~~~~~
~~~~~python.old
        # 2. Manually add a file and use `save` to create state B
        (git_workspace / "b.txt").write_text("manual change")
        res_save = runner.invoke(app, ["save", "add b.txt", "-w", str(git_workspace)])
        assert res_save.exit_code == 0
        assert "快照已保存" in res_save.stderr

        # 3. Use `log` to check history
        res_log = runner.invoke(app, ["log", "-w", str(git_workspace)])
        assert res_log.exit_code == 0
        assert "--- Quipu History Log ---" in res_log.stderr
        assert "add b.txt" in res_log.stdout  # Check data in stdout
        assert "Write: a.txt" in res_log.stdout  # Check data in stdout

        # 4. Use `find` and `checkout` to go back to state A
        res_find = runner.invoke(app, ["find", "--summary", "Write: a.txt", "-w", str(git_workspace)])
        assert res_find.exit_code == 0
        assert "--- 查找结果 ---" in res_find.stderr
~~~~~
~~~~~python.new
        # 2. Manually add a file and use `save` to create state B
        (git_workspace / "b.txt").write_text("manual change")
        res_save = runner.invoke(app, ["save", "add b.txt", "-w", str(git_workspace)])
        assert res_save.exit_code == 0
        assert "workspace.save.success" in res_save.stderr

        # 3. Use `log` to check history
        res_log = runner.invoke(app, ["log", "-w", str(git_workspace)])
        assert res_log.exit_code == 0
        assert "query.log.ui.header" in res_log.stderr
        assert "add b.txt" in res_log.stdout  # Check data in stdout
        assert "Write: a.txt" in res_log.stdout  # Check data in stdout

        # 4. Use `find` and `checkout` to go back to state A
        res_find = runner.invoke(app, ["find", "--summary", "Write: a.txt", "-w", str(git_workspace)])
        assert res_find.exit_code == 0
        assert "query.find.ui.header" in res_find.stderr
~~~~~

~~~~~act
patch_file
tests/integration/test_storage_selection.py
~~~~~
~~~~~python.old
    def test_find_cli_by_type(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "--type", "plan", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "--- 查找结果 ---" in result.stderr
        assert "[PLAN]" in result.stdout
        assert "[CAPTURE]" not in result.stdout
        assert "Write: a.txt" in result.stdout

    def test_find_cli_by_summary(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "-s", "snapshot", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "--- 查找结果 ---" in result.stderr
        assert "[CAPTURE]" in result.stdout
        assert "Snapshot 1" in result.stdout
        assert "[PLAN]" not in result.stdout

    def test_find_cli_no_results(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "-s", "non-existent", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "未找到符合条件" in result.stderr
~~~~~
~~~~~python.new
    def test_find_cli_by_type(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "--type", "plan", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "query.find.ui.header" in result.stderr
        assert "[PLAN]" in result.stdout
        assert "[CAPTURE]" not in result.stdout
        assert "Write: a.txt" in result.stdout

    def test_find_cli_by_summary(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "-s", "snapshot", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "query.find.ui.header" in result.stderr
        assert "[CAPTURE]" in result.stdout
        assert "Snapshot 1" in result.stdout
        assert "[PLAN]" not in result.stdout

    def test_find_cli_no_results(self, runner, populated_workspace):
        result = runner.invoke(app, ["find", "-s", "non-existent", "-w", str(populated_workspace)])
        assert result.exit_code == 0
        assert "query.info.noResults" in result.stderr
~~~~~

#### Acts 2: 修正 `tests/integration/test_sync_modes.py`

我们将同步模式下的各种进度描述词替换为 Key。

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python.old
        # User A syncs with push-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-only"])
        assert sync_result.exit_code == 0
        assert "⬆️  正在推送..." in sync_result.stderr
        assert "⬇️" not in sync_result.stderr  # Should not fetch
~~~~~
~~~~~python.new
        # User A syncs with push-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-only"])
        assert sync_result.exit_code == 0
        assert "sync.run.info.pushing" in sync_result.stderr
        assert "sync.run.info.pulling" not in sync_result.stderr  # Should not fetch
~~~~~

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python.old
        # User B syncs with pull-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-only"])
        assert sync_result.exit_code == 0
        assert "⬇️  正在拉取..." in sync_result.stderr
        assert "⬆️" not in sync_result.stderr  # Should not push
~~~~~
~~~~~python.new
        # User B syncs with pull-only
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-only"])
        assert sync_result.exit_code == 0
        assert "sync.run.info.pulling" in sync_result.stderr
        assert "sync.run.info.pushing" not in sync_result.stderr  # Should not push
~~~~~

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python.old
        # User A syncs with push-force
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-force"])
        assert sync_result.exit_code == 0
        assert "⬆️  正在强制推送..." in sync_result.stderr
~~~~~
~~~~~python.new
        # User A syncs with push-force
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_a_path), "--mode", "push-force"])
        assert sync_result.exit_code == 0
        assert "sync.run.info.pushingForce" in sync_result.stderr
~~~~~

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python.old
        # User B syncs with pull-prune
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-prune"])
        assert sync_result.exit_code == 0
        assert "🗑️  正在修剪本地..." in sync_result.stderr
~~~~~
~~~~~python.new
        # User B syncs with pull-prune
        sync_result = runner.invoke(app, ["sync", "--work-dir", str(user_b_path), "--mode", "pull-prune"])
        assert sync_result.exit_code == 0
        assert "sync.run.info.pruning" in sync_result.stderr
~~~~~

### 下一步建议
1.  **运行全量测试**：执行 `pytest`。预期结果应为 100% 通过。
2.  **验证 Git Commit**：如果测试通过，你可以使用 `git_commit` 将这些变更固化。任务已完成。
