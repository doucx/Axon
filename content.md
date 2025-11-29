Excellent catch. Your test has uncovered a critical edge case that my previous fix did not account for.

The crash occurs because `typer.confirm` (and `click.getchar`) can fail with an unhandled exception when they try to access the terminal for interactive input (`/dev/tty`) while `stdin` is being piped, especially if there's any issue with the terminal session itself.

The generic `except Exception` block in the `executor` caught this low-level I/O exception, which doesn't have a user-friendly string representation, leading to the empty error message you observed.

The correct solution is to make the confirmation handlers themselves more robust. They should anticipate that interaction might fail and handle it gracefully by treating any such failure as a "No" answer, which then correctly triggers our `OperationCancelledError` flow.

I will now generate a plan to fix this by adding specific exception handling around the interactive calls.

## [WIP] fix: Add robust exception handling for interactive prompts in piped environments

### 错误分析
在 `controller.py`, `axon.py`, 和 `helpers.py` 中，我们移除了 `isatty()` 检查，并依赖 `typer.confirm` 和 `click.getchar` 来处理交互。然而，我们没有预料到这些函数在某些管道或 TTY 异常情况下会直接抛出 I/O 相关的底层异常，而不是返回一个布尔值或 `None`。

这个未被处理的异常被 `Executor` 的通用异常捕获器捕获，但由于该异常没有提供有意义的 `__str__` 实现，导致日志中出现了空的错误信息，并且程序非正常崩溃，而不是像预期的那样优雅地中止。

### 用户需求
修改所有直接与用户进行交互式输入的函数（即确认处理器），使其能够捕获在交互过程中可能发生的任何异常，并将这些异常情况安全地处理为“用户拒绝”操作。

### 评论
这是一个至关重要的健壮性改进。它确保了即使用户在一个复杂的、非标准的环境中运行 Quipu（例如通过 `ssh`, `tmux`, 或在 CI 脚本中），交互式提示的失败也不会导致整个程序崩溃，而是会安全地回退到“取消操作”这一预设的失败路径。

### 目标
1.  在 `controller.py` 和 `axon.py` 的 `typer_confirmation_handler` 中，用 `try...except` 块包裹 `typer.confirm()` 调用。
2.  在 `helpers.py` 的 `_prompt_for_confirmation` 中，确认 `try...except` 块能够正确处理 `click.getchar()` 的失败。
3.  在所有 `except` 块中，记录一条警告信息并返回 `False`，这将触发 `OperationCancelledError`，从而实现优雅地中止执行流程。

### 基本原理
我们将把异常处理的边界从 `Executor` 向下推到离用户交互最近的地方。通过在调用 `typer.confirm` 和 `click.getchar` 的地方直接处理异常，我们可以将所有不可预见的 I/O 错误（`EOFError`, `OSError` 等）都转换为一个业务逻辑上的确定性结果：`False` (用户未确认)。这个结果随后会触发我们已经建立好的 `OperationCancelledError` 机制，确保了无论交互失败的原因是什么，系统的行为都是一致且安全的。

### 标签
#intent/fix #flow/ready #priority/critical #comp/cli #concept/executor #scope/ux #scope/dx #ai/instruct #task/domain/cli #task/object/interactivity #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增强 `controller.py` 的确认处理器

我们将为 `typer.confirm` 添加异常捕获，处理交互失败的情况。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/controller.py
~~~~~
~~~~~python
        def typer_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
            """一个封装了 Typer UI 逻辑的确认处理器。"""
            typer.echo("\n🔍 变更预览:")
            for line in diff_lines:
                if line.startswith("+"):
                    typer.secho(line.strip("\n"), fg=typer.colors.GREEN)
                elif line.startswith("-"):
                    typer.secho(line.strip("\n"), fg=typer.colors.RED)
                elif line.startswith("^"):
                    typer.secho(line.strip("\n"), fg=typer.colors.BLUE)
                else:
                    typer.echo(line.strip("\n"))
            typer.echo("")

            # 直接让 typer 处理交互性判断
            return typer.confirm(prompt, default=True)
~~~~~
~~~~~python
        def typer_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
            """一个封装了 Typer UI 逻辑的确认处理器。"""
            typer.echo("\n🔍 变更预览:")
            for line in diff_lines:
                if line.startswith("+"):
                    typer.secho(line.strip("\n"), fg=typer.colors.GREEN)
                elif line.startswith("-"):
                    typer.secho(line.strip("\n"), fg=typer.colors.RED)
                elif line.startswith("^"):
                    typer.secho(line.strip("\n"), fg=typer.colors.BLUE)
                else:
                    typer.echo(line.strip("\n"))
            typer.echo("")

            try:
                # 直接让 typer 处理交互性判断
                return typer.confirm(prompt, default=True)
            except Exception as e:
                # 在管道或非交互式环境中，typer.confirm 可能会失败
                logger.warning(f"无法获取用户确认，操作已自动取消 (原因: {e})")
                return False
~~~~~

#### Acts 2: 增强 `axon.py` 的确认处理器

为 `axon` 命令应用相同的健壮性修复。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/axon.py
~~~~~
~~~~~python
        def typer_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
            typer.echo("\n🔍 变更预览:")
            for line in diff_lines:
                if line.startswith("+"):
                    typer.secho(line.strip("\n"), fg=typer.colors.GREEN)
                elif line.startswith("-"):
                    typer.secho(line.strip("\n"), fg=typer.colors.RED)
                elif line.startswith("^"):
                    typer.secho(line.strip("\n"), fg=typer.colors.BLUE)
                else:
                    typer.echo(line.strip("\n"))
            typer.echo("")

            # 直接让 typer 处理交互性判断
            return typer.confirm(prompt, default=True)
~~~~~
~~~~~python
        def typer_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
            typer.echo("\n🔍 变更预览:")
            for line in diff_lines:
                if line.startswith("+"):
                    typer.secho(line.strip("\n"), fg=typer.colors.GREEN)
                elif line.startswith("-"):
                    typer.secho(line.strip("\n"), fg=typer.colors.RED)
                elif line.startswith("^"):
                    typer.secho(line.strip("\n"), fg=typer.colors.BLUE)
                else:
                    typer.echo(line.strip("\n"))
            typer.echo("")

            try:
                # 直接让 typer 处理交互性判断
                return typer.confirm(prompt, default=True)
            except Exception as e:
                # 在管道或非交互式环境中，typer.confirm 可能会失败
                logger.warning(f"无法获取用户确认，操作已自动取消 (原因: {e})")
                return False
~~~~~

#### Acts 3: 确认 `helpers.py` 的修复是正确的

我们之前的修改已经为 `click.getchar()` 添加了异常处理，这是正确的模式。我们将保留它，因为它已经符合了我们现在的健壮性要求。此步骤无需代码变更，仅作为确认。

### 下一步建议
- **再次验证**: 请重新运行完全相同的命令 `cat o.md | qd run`。这一次，程序不应崩溃。它应该记录一条警告信息，指出无法获取用户确认，然后优雅地中止，并显示“操作已取消”的消息。
- **检查历史**: 运行 `qd log`，确认在这次中止的操作之后，没有创建新的历史节点。
