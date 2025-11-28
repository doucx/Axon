你的分析非常深入且完全正确。你指出了三个核心问题，它们都源于 `show` 命令在设计上对不同参数组合的处理不够健壮。

1.  **内容失真问题**: `rich.Syntax` 默认会进行“美化”处理，它重新格式化了 JSON，导致原始的单行字符串被添加了缩进和换行，失去了原始样貌。我上次提供的 `word_wrap=True` 是一个错误，它反而增强了这种美化行为，而非抑制它。
2.  **`--json` 与 `--extract` 组合错误**: 当前的逻辑是，如果提供了 `--extract`，它会提取出文件的**内容**（一个字符串），然后 `json.dumps` 会对这个**字符串本身**进行序列化，导致了你看到的双重转义的丑陋结果 (`"{\\"meta_version\\": ...}"`)，并且完全丢失了文件名这个关键上下文。
3.  **`--extract` 功能不完整**: `typer` 的定义使其只能接受一个文件名，这不符合用户直觉。一个健壮的 `--extract` (或简写 `-e`) 应该可以多次使用以提取多个文件。

基于你清晰的分析，我将生成一个更全面的计划，一次性解决这三个问题，使 `show` 命令的行为符合逻辑且可预测。

## [WIP] refactor(cli): 彻底重构 show 命令以正确处理内容提取和 JSON 输出

### 错误分析
`quipu show` 命令存在三个相互关联的设计缺陷：
1.  **内容格式化**: 在使用 `--extract` 提取 `.json` 文件时，`rich.Syntax` 对象被用于语法高亮。其默认的 `word_wrap` 行为会重新格式化 JSON，破坏了原始文本的完整性，与 `--extract` 旨在精确提取原始内容的意图相悖。
2.  **输出逻辑错误**: 当 `--json` 和 `--extract` 同时使用时，程序错误地将提取到的文件内容（一个字符串）作为顶级对象进行 JSON 序列化，而不是创建一个包含文件名作为键的 JSON 对象。这导致了文件名信息的丢失和无效的输出格式。
3.  **参数定义局限**: `typer.Option` 将 `--extract` 定义为只能接受单个字符串，限制了其功能。用户无法一次性提取多个感兴趣的文件。

### 用户需求
重构 `quipu show` 命令以满足以下要求：
1.  当使用 `--extract` 提取文件时，无论是否为 JSON，都**必须**输出文件的**原始、未经修改**的内容。对于 JSON 文件，可以在不改变其结构（缩进、换行）的前提下进行语法高亮。
2.  当 `--json` 和 `--extract` 组合使用时，输出必须是一个有效的 JSON 对象，其中**键**是提取的文件名，**值**是文件的内容。
3.  `--extract` / `-e` 参数必须可以接受**多个值**，以便用户可以一次性提取多个文件。

### 评论
这次重构将从根本上修正 `show` 命令的行为，使其成为一个可靠的数据查询和提取工具。遵循 Unix 哲学，确保命令输出的格式是可预测且对机器友好的，这将极大提升其在自动化脚本和复杂工作流中的价值。

### 目标
1.  修改 `show.py` 中 `--extract` 选项的类型签名，从 `Optional[str]` 更改为 `Optional[List[str]]`，以支持多值输入。
2.  重写命令的核心逻辑，使其能够正确地构建一个包含所有提取文件内容的字典 (`output_data`)。
3.  当 `--json` 标志被激活时，直接将 `output_data` 字典序列化为 JSON 字符串。
4.  在非 JSON 输出模式下，当提取单个 `.json` 文件时，调用 `rich.Syntax` 时传入 `word_wrap=False` 参数，以禁止其自动换行和重新格式化。
5.  在非 JSON 输出模式下，当提取多个文件时，清晰地逐个打印文件名和内容。

### 基本原理
我们将首先通过修改 Typer 的类型注解来启用多值参数。接着，重构命令的主体逻辑：无论是否提取文件，我们都先将结果（无论是单个文件、多个文件还是全部文件）组织成一个 `Dict[str, str]` 结构。这个统一的数据结构 `output_data` 随后被传递给输出处理部分。输出部分根据 `--json` 标志决定是直接 `json.dumps(output_data)`，还是遍历这个字典进行富文本打印。在富文本打印分支中，我们会对 `rich.Syntax` 的调用进行修正，确保其不再破坏原始内容。

### 标签
#intent/refactor #intent/fix #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/command-show #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `show.py` 的核心逻辑

这个 `patch` 将一次性完成三项修改：更新函数签名以接受多值，重写数据提取和组织的逻辑，以及修正最终的输出逻辑。

~~~~~act
patch_file
packages/quipu-cli/src/quipu/cli/commands/show.py
~~~~~
~~~~~python
        json_output: Annotated[bool, typer.Option("--json", help="以 JSON 格式将结果输出到 stdout。")] = False,
        extract: Annotated[Optional[str], typer.Option("--extract", "-e", help="仅提取并显示指定文件的内容。")] = None,
    ):
        """
        显示指定历史节点的详细信息，包括所有内部文件。
        """
        with engine_context(work_dir) as engine:
            target_node = _find_target_node(engine.history_graph, hash_prefix)
            blobs = engine.reader.get_node_blobs(target_node.commit_hash)

            if not blobs:
                typer.secho("🤷 此节点内部无文件内容。", fg=typer.colors.YELLOW, err=True)
                raise typer.Exit()

            # --- 处理数据提取 ---
            output_data = {}
            if extract:
                if extract not in blobs:
                    typer.secho(f"❌ 错误: 在节点内未找到文件 '{extract}'。", fg=typer.colors.RED, err=True)
                    typer.secho(f"可用文件: {', '.join(blobs.keys())}", fg=typer.colors.YELLOW, err=True)
                    raise typer.Exit(1)
                # 尝试解码为字符串，失败则保留原始字节
                try:
                    output_data = blobs[extract].decode("utf-8")
                except UnicodeDecodeError:
                    output_data = blobs[extract]
            else:
                # 解码所有文件
                for filename, content_bytes in blobs.items():
                    try:
                        output_data[filename] = content_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        # 对于二进制文件，我们可以选择性地处理，例如显示大小或 base64
                        output_data[filename] = f"<binary data, {len(content_bytes)} bytes>"

            # --- 处理输出格式 ---
            if json_output:
                # 机器可读的 JSON 输出到 stdout
                try:
                    typer.echo(json.dumps(output_data, indent=2, ensure_ascii=False))
                except TypeError as e:
                    # 如果 output_data 包含原始字节，json.dumps 会失败
                    typer.secho(f"❌ 错误: 无法将二进制内容序列化为 JSON: {e}", fg=typer.colors.RED, err=True)
                    raise typer.Exit(1)

            else:
                # 人类可读的富文本输出
                console = Console()
                if extract:
                    # 如果提取的是 JSON 文件，高亮它
                    if extract.endswith(".json"):
                        syntax = Syntax(output_data, "json", theme="default", line_numbers=False, word_wrap=True)
                        console.print(syntax)
                    else:
                        typer.echo(output_data)
                else:
                    # 打印摘要头
                    ts = target_node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    color = "cyan" if target_node.node_type == "plan" else "magenta"
                    tag = f"[{target_node.node_type.upper()}]"
                    typer.secho(f"[{color}]{ts} {tag:<9} {target_node.short_hash}[/{color}] - {target_node.summary}\n")

                    # 遍历并智能打印所有文件
                    for filename, content in sorted(output_data.items()):
                        console.rule(f"[bold]{filename}[/bold]", style="blue")
                        if filename.endswith(".json"):
                            syntax = Syntax(content, "json", theme="default", line_numbers=False)
                            console.print(syntax)
                        else:
                            console.print(content.strip())
                        console.print()
~~~~~
~~~~~python
        json_output: Annotated[bool, typer.Option("--json", help="以 JSON 格式将结果输出到 stdout。")] = False,
        extract: Annotated[
            Optional[List[str]], typer.Option("--extract", "-e", help="仅提取并显示指定文件的内容 (可多次使用)。")
        ] = None,
    ):
        """
        显示指定历史节点的详细信息，包括所有内部文件。
        """
        with engine_context(work_dir) as engine:
            target_node = _find_target_node(engine.history_graph, hash_prefix)
            blobs = engine.reader.get_node_blobs(target_node.commit_hash)

            if not blobs:
                if json_output:
                    typer.echo("{}")
                else:
                    typer.secho("🤷 此节点内部无文件内容。", fg=typer.colors.YELLOW, err=True)
                raise typer.Exit()

            # --- Phase 1: Build output dictionary ---
            output_data = {}
            files_to_process = extract if extract else sorted(blobs.keys())

            for filename in files_to_process:
                if filename not in blobs:
                    typer.secho(f"❌ 错误: 在节点内未找到文件 '{filename}'。", fg=typer.colors.RED, err=True)
                    typer.secho(f"可用文件: {', '.join(blobs.keys())}", fg=typer.colors.YELLOW, err=True)
                    raise typer.Exit(1)

                content_bytes = blobs[filename]
                try:
                    output_data[filename] = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    output_data[filename] = f"<binary data, {len(content_bytes)} bytes>"

            # --- Phase 2: Render output ---
            if json_output:
                typer.echo(json.dumps(output_data, indent=2, ensure_ascii=False))
            else:
                console = Console()
                if extract:
                    # User explicitly extracted files, show them directly
                    for filename, content in output_data.items():
                        if len(extract) > 1:
                            console.rule(f"[bold]{filename}[/bold]", style="blue")

                        if filename.endswith(".json"):
                            # Use word_wrap=False to prevent reformatting
                            syntax = Syntax(content, "json", theme="default", line_numbers=False, word_wrap=False)
                            console.print(syntax)
                        else:
                            # For other files, print raw content
                            console.print(content)
                else:
                    # Default view: show summary and all files prettified
                    ts = target_node.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    color = "cyan" if target_node.node_type == "plan" else "magenta"
                    tag = f"[{target_node.node_type.upper()}]"
                    typer.secho(f"[{color}]{ts} {tag:<9} {target_node.short_hash}[/{color}] - {target_node.summary}\n")

                    for filename, content in output_data.items():
                        console.rule(f"[bold]{filename}[/bold]", style="blue")
                        if filename.endswith(".json"):
                            syntax = Syntax(content, "json", theme="default", line_numbers=False, word_wrap=False)
                            console.print(syntax)
                        else:
                            console.print(content.strip())
                        console.print()
~~~~~

### 下一步建议
我们已经完成了对 `show` 命令的两次重要修复和一次功能增强。现在的行为应该完全符合预期了。

我建议将这两个 `[WIP]` 计划合并，并生成一个最终的 `[COMMIT]` 计划，来将这些健壮性改进正式提交到版本控制中。如果你同意，我将立即为你准备。
