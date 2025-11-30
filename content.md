分析正确。测试失败是因为 `ctx.fail` 抛出的 `ExecutionError` 被外层的 `try...except Exception` 块意外捕获，导致错误被重新包装成了 `acts.shell.error.exception`。

这是一个经典的异常处理范围过大问题。`ctx.fail` 是用于流程控制的机制，不应被视为系统异常。

我们将缩小 `try...except` 块的范围，仅包裹实际的 `subprocess.run` 调用。

## [WIP] fix: 修复 shell act 异常捕获范围过大导致的测试失败

### 错误分析
在 `_run_command` 中，`ctx.fail` 被放置在了一个捕获所有 `Exception` 的 `try` 块中。
当命令返回非零退出码时，代码调用 `ctx.fail`，抛出 `ExecutionError`。
这个 `ExecutionError` 随后被 `except Exception as e` 捕获，并被错误地再次包装为 `acts.shell.error.exception`，导致测试断言的 `msg_id` 不匹配。

### 目标
修改 `packages/quipu-runtime/src/pyquipu/acts/shell.py`，将结果检查和 `ctx.fail` 调用移出 `try...except` 块。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #task/domain/testing #task/object/acts #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正 shell.py 的异常处理逻辑

~~~~~act
patch_file
packages/quipu-runtime/src/pyquipu/acts/shell.py
~~~~~
~~~~~python
    bus.info("acts.shell.info.executing", command=command)

    try:
        result = subprocess.run(command, cwd=ctx.root_dir, shell=True, capture_output=True, text=True)

        if result.stdout:
            bus.data(result.stdout.strip())
        if result.stderr:
            bus.warning("acts.shell.warning.stderrOutput", output=result.stderr.strip())

        if result.returncode != 0:
            ctx.fail(bus.get("acts.shell.error.failed", code=result.returncode))

    except Exception as e:
        ctx.fail(bus.get("acts.shell.error.exception", error=e))
~~~~~
~~~~~python
    bus.info("acts.shell.info.executing", command=command)

    try:
        result = subprocess.run(command, cwd=ctx.root_dir, shell=True, capture_output=True, text=True)
    except Exception as e:
        ctx.fail(bus.get("acts.shell.error.exception", error=e))
        return

    if result.stdout:
        bus.data(result.stdout.strip())
    if result.stderr:
        bus.warning("acts.shell.warning.stderrOutput", output=result.stderr.strip())

    if result.returncode != 0:
        ctx.fail(bus.get("acts.shell.error.failed", code=result.returncode))
~~~~~

### 下一步建议
运行测试 `pytest tests/runtime/acts/test_shell.py` 确认修复。
