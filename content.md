# fix-test: 更新 checkout 命令的成功消息断言

## 用户需求
在之前的 `feat` 提交中，`checkout` 命令的成功提示语被修改，导致 `test_cli_checkout_success` 测试用例失败。需要更新此测试用例以匹配新的提示语。

## 评论
这是一个简单的测试用例维护任务，确保测试代码与功能代码保持同步。

## 目标
修正 `tests/test_integration_v2.py` 中失败的断言，使测试套件能够全部通过。

## 基本原理
将 `assert "✅ 已成功将工作区恢复到节点" in result.stderr` 修改为 `assert "✅ 已成功切换到状态" in result.stderr`，以匹配 `_execute_visit` 辅助函数输出的新消息。

## 标签
#fix #test

---

## Script

### Acts 1: 修正测试用例

更新 `tests/test_integration_v2.py` 中 `TestCheckoutCLI.test_cli_checkout_success` 方法内的断言字符串。

~~~~~act
replace
~~~~~

~~~~~path
tests/test_integration_v2.py
~~~~~

~~~~~python
        result = runner.invoke(app, ["checkout", hash_a[:8], "--work-dir", str(workspace), "--force"])
        
        assert result.exit_code == 0
        assert "✅ 已成功将工作区恢复到节点" in result.stderr
        
        # Post-flight check: we are now in state A
~~~~~

~~~~~python
        result = runner.invoke(app, ["checkout", hash_a[:8], "--work-dir", str(workspace), "--force"])
        
        assert result.exit_code == 0
        assert "✅ 已成功切换到状态" in result.stderr
        
        # Post-flight check: we are now in state A
~~~~~