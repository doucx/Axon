好的，分析完成。

你发现的这些 `echo` 和 `secho` 调用是 `MessageBus` 重构项目中需要清理的最后一批硬编码 UI 字符串。它们主要集中在处理复杂交互（如 `prompt_for_confirmation`）和特殊格式化输出（如 `show` 命令的标题头）的地方。

我们将执行一个计划，将这些剩余的调用全部迁移到 `MessageBus` 规范下，从而完成整个 CLI 输出层的统一。这个过程将涉及：
1.  为这些特殊的 UI 元素在 `locales/zh/cli.json` 中创建新的、语义化的消息 ID。
2.  重构 `ui_utils.py`，使其成为消息的“消费者”而不是“定义者”。
3.  简化 `navigation.py` 和 `workspace.py` 中的逻辑，将 diff 显示的职责完全委托给 `prompt_for_confirmation`。
4.  统一 `show.py` 的输出方式。

## [WIP] refactor: Finalize MessageBus migration and remove remaining secho calls

### 用户需求
根据 `rg echo` 的输出结果，定位并重构 `quipu-cli` 中所有剩余的硬编码 `typer.echo` 和 `typer.secho` 调用。目标是将所有面向用户的文本移入 `locales/zh/cli.json`，并通过 `MessageBus` 进行输出，以完成整个 CLI 输出层的统一化和重构。

### 评论
这是 `MessageBus` 重构计划的收尾工作。通过清理这些散落在交互工具和特定命令中的硬编码字符串，我们能确保整个 CLI 的输出逻辑 100% 可测试、可维护且已为国际化做好准备。这是一个提升代码质量和开发者体验的关键步骤。

### 目标
1.  在 `locales/zh/cli.json` 中为确认提示、差异预览和节点展示的 UI 元素添加新的消息模板。
2.  修改 `quipu/cli/ui_utils.py`，使其从 `MessageBus` 获取消息模板，而不是硬编码它们。
3.  修改 `quipu/cli/commands/navigation.py` 和 `workspace.py`，移除手动的 diff 打印逻辑。
4.  修改 `quipu/cli/commands/show.py`，使其标题输出也通过 `MessageBus`。

### 基本原理
我们将遵循“关注点分离”原则。`ui_utils.py` 作为 UI 工具，其职责是“如何显示”，而不应关心“显示什么内容”。因此，我们将内容（文本模板）提取到 `cli.json` 中，`ui_utils.py` 通过 `bus.get()` 获取这些模板，然后使用 `typer` 的底层功能进行渲染（例如，逐行着色）。对于 `navigation` 和 `workspace` 命令，我们将简化其代码，因为它们不再需要直接处理 diff 的显示逻辑，只需将 diff 数据传递给 `prompt_for_confirmation` 即可。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/message-bus #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 扩充 `cli.json` 消息模板

首先，我们在 `locales/zh/cli.json` 中添加所有新识别出的 UI 文本。

```````act
patch_file
locales/zh/cli.json
```````
```````json
  "export.success.zip": "\n✅ 导出成功，已保存为压缩包: {path}",
  "export.success.dir": "\n✅ 导出成功完成。"
}
```````
```````json
  "export.success.zip": "\n✅ 导出成功，已保存为压缩包: {path}",
  "export.success.dir": "\n✅ 导出成功完成。",

  "prompt.ui.diffHeader": "\n🔍 变更预览:",
  "prompt.suffix.yesDefault": " [Y/n]: ",
  "prompt.suffix.noDefault": " [y/N]: ",
  "prompt.info.nonInteractive": " (non-interactive)",

  "show.ui.header": "{ts} {tag} {short_hash} - {summary}\n",
  "navigation.checkout.prompt.confirm": "🚨 即将重置工作区到状态 {short_hash} ({timestamp})。\n此操作会覆盖未提交的更改。是否继续？",
  "workspace.discard.prompt.confirm": "🚨 即将丢弃上述所有变更，并恢复到状态 {short_hash}。\n此操作不可逆。是否继续？"
}
```````

#### Acts 2: 重构 `ui_utils.py`

现在我们修改 `prompt_for_confirmation`，让它从 `MessageBus` 获取文本，同时保留其对 diff 内容进行逐行着色的渲染能力。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/ui_utils.py
```````
```````python
import click
import typer
from typing import List, Optional
```````
```````python
import click
import typer
from typing import List, Optional

from quipu.common.messaging import bus
```````

```````act
patch_file
packages/quipu-cli/src/quipu/cli/ui_utils.py
```````
```````python
    Returns:
        如果用户确认则返回 True，否则返回 False。
    """
    if diff_lines:
        typer.echo("\n🔍 变更预览:", err=True)
        for line in diff_lines:
            if line.startswith("+"):
                typer.secho(line.strip("\n"), fg=typer.colors.GREEN, err=True)
            elif line.startswith("-"):
                typer.secho(line.strip("\n"), fg=typer.colors.RED, err=True)
            elif line.startswith("^"):
                typer.secho(line.strip("\n"), fg=typer.colors.BLUE, err=True)
            else:
                typer.echo(line.strip("\n"), err=True)
        typer.echo("", err=True)

    prompt_suffix = " [Y/n]: " if default else " [y/N]: "
    typer.secho(prompt + prompt_suffix, nl=False, err=True)

    try:
        # click.getchar() 会智能地尝试从 /dev/tty 读取
        char = click.getchar(echo=False)
        click.echo(char, err=True)  # 手动回显到 stderr
    except (OSError, EOFError):
        # 在完全没有 tty 的环境中 (例如 CI runner)，会抛出异常
        click.echo(" (non-interactive)", err=True)
        return False  # 非交互式环境应安全失败
```````
```````python
    Returns:
        如果用户确认则返回 True，否则返回 False。
    """
    if diff_lines:
        bus.info("prompt.ui.diffHeader")
        for line in diff_lines:
            if line.startswith("+"):
                typer.secho(line.strip("\n"), fg=typer.colors.GREEN, err=True)
            elif line.startswith("-"):
                typer.secho(line.strip("\n"), fg=typer.colors.RED, err=True)
            elif line.startswith("^"):
                typer.secho(line.strip("\n"), fg=typer.colors.BLUE, err=True)
            else:
                typer.echo(line.strip("\n"), err=True)
        typer.echo("", err=True)

    prompt_suffix = bus.get("prompt.suffix.yesDefault") if default else bus.get("prompt.suffix.noDefault")
    typer.secho(prompt + prompt_suffix, nl=False, err=True)

    try:
        # click.getchar() 会智能地尝试从 /dev/tty 读取
        char = click.getchar(echo=False)
        click.echo(char, err=True)  # 手动回显到 stderr
    except (OSError, EOFError):
        # 在完全没有 tty 的环境中 (例如 CI runner)，会抛出异常
        bus.info("prompt.info.nonInteractive")
        return False  # 非交互式环境应安全失败
```````

#### Acts 3: 简化 `navigation.py`

移除 `checkout` 命令中手动的 diff 打印，并将 prompt 文本替换为消息 ID 调用。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/navigation.py
```````
```````python
            current_hash = engine.git_db.get_tree_hash()

            diff_stat = engine.git_db.get_diff_stat(current_hash, target_output_tree_hash)
            if diff_stat:
                bus.info("navigation.checkout.ui.diffHeader")
                typer.secho("-" * 20, err=True)
                typer.echo(diff_stat, err=True)
                typer.secho("-" * 20, err=True)

            if not force:
                prompt = f"🚨 即将重置工作区到状态 {target_node.short_hash} ({target_node.timestamp})。\n此操作会覆盖未提交的更改。是否继续？"
                if not prompt_for_confirmation(prompt, default=False):
                    bus.warning("common.prompt.cancel")
                    raise typer.Abort()
```````
```````python
            current_hash = engine.git_db.get_tree_hash()

            diff_stat_str = engine.git_db.get_diff_stat(current_hash, target_output_tree_hash)

            if not force:
                prompt = bus.get(
                    "navigation.checkout.prompt.confirm",
                    short_hash=target_node.short_hash,
                    timestamp=target_node.timestamp,
                )
                if not prompt_for_confirmation(prompt, diff_lines=diff_stat_str.splitlines(), default=False):
                    bus.warning("common.prompt.cancel")
                    raise typer.Abort()
```````

#### Acts 4: 简化 `workspace.py`

同样，移除 `discard` 命令中的 diff 打印，并使用消息 ID 生成 prompt。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/workspace.py
```````
```````python
            current_hash = engine.git_db.get_tree_hash()
            if current_hash == target_tree_hash:
                bus.success("workspace.discard.noChanges", short_hash=latest_node.short_hash)
                ctx.exit(0)

            diff_stat = engine.git_db.get_diff_stat(target_tree_hash, current_hash)
            bus.info("workspace.discard.ui.diffHeader")
            typer.secho("-" * 20, err=True)
            typer.echo(diff_stat, err=True)
            typer.secho("-" * 20, err=True)

            if not force:
                prompt = f"🚨 即将丢弃上述所有变更，并恢复到状态 {latest_node.short_hash}。\n此操作不可逆。是否继续？"
                if not prompt_for_confirmation(prompt, default=False):
                    bus.warning("common.prompt.cancel")
                    raise typer.Abort()
```````
```````python
            current_hash = engine.git_db.get_tree_hash()
            if current_hash == target_tree_hash:
                bus.success("workspace.discard.noChanges", short_hash=latest_node.short_hash)
                ctx.exit(0)

            diff_stat_str = engine.git_db.get_diff_stat(target_tree_hash, current_hash)

            if not force:
                prompt = bus.get("workspace.discard.prompt.confirm", short_hash=latest_node.short_hash)
                if not prompt_for_confirmation(prompt, diff_lines=diff_stat_str.splitlines(), default=False):
                    bus.warning("common.prompt.cancel")
                    raise typer.Abort()
```````

#### Acts 5: 重构 `show.py`

最后，我们将 `show` 命令的标题头输出也迁移到 `MessageBus`。

```````act
patch_file
packages/quipu-cli/src/quipu/cli/commands/show.py
```````
```````python
                    # Default view: show summary and all files prettified
                    ts = target_node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    color = "cyan" if target_node.node_type == "plan" else "magenta"
                    tag = f"[{target_node.node_type.upper()}]"
                    typer.secho(f"[{color}]{ts} {tag:<9} {target_node.short_hash}[/{color}] - {target_node.summary}\n")

                    for filename, content in output_data.items():
                        console.rule(f"[bold]{filename}[/bold]", style="blue")
```````
```````python
                    # Default view: show summary and all files prettified
                    ts = target_node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    tag = f"[{target_node.node_type.upper()}]"
                    bus.data(
                        bus.get(
                            "show.ui.header",
                            ts=ts,
                            tag=f"{tag:<9}",
                            short_hash=target_node.short_hash,
                            summary=target_node.summary,
                        )
                    )

                    for filename, content in output_data.items():
                        console.rule(f"[bold]{filename}[/bold]", style="blue")
```````

### 下一步建议
我们已经成功地将所有已知的硬编码用户输出迁移到了 `MessageBus` 系统。这标志着整个重构任务的核心部分已经完成。

下一步，我将生成一个 `[COMMIT]` 计划，将所有这些清理工作作为一个完整的单元提交到版本历史中，正式宣告 `MessageBus` 重构任务的结束。
