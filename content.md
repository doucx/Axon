# fix-test: Correct summary display in `log` command

## 用户需求
`test_full_workflow_with_git_object_storage` 测试用例失败。失败的原因是 `quipu log` 命令未能正确显示 `quipu save "..."` 命令提供的用户自定义消息，而是显示了一个通用的 "Workspace changes captured" 摘要。我需要修复这个问题。

## 评论
问题根源在于 `log` 命令试图通过重新解析节点内容来“猜测”摘要，而不是使用由存储后端生成的、权威的摘要信息。这违反了单一事实来源原则，导致了显示不一致。

正确的解决方案是进行一次小型的架构重构：
1.  将 `summary` 字段正式添加到核心数据模型 `QuipuNode` 中。
2.  确保两种存储读取器 (`GitObjectHistoryReader` 和 `FileSystemHistoryReader`) 在加载节点时都负责填充这个 `summary` 字段。
3.  最后，简化 `log` 命令，使其不再进行任何解析，而是直接显示 `node.summary` 字段的内容。

这个修复不仅能解决当前的测试失败，还能使 `log` 命令的实现更简洁、更健壮，并确保了摘要信息在整个系统中的一致性。

## 目标
1.  在 `quipu-interfaces` 中，为 `QuipuNode` 数据类添加 `summary: str` 字段。
2.  在 `quipu-engine` 中，更新 `GitObjectHistoryReader` 以从 `metadata.json` 中读取 `summary` 并填充到 `QuipuNode` 实例中。
3.  同样在 `quipu-engine` 中，更新 `history.py`（服务于 `FileSystemHistoryReader`），为其增加一个回退逻辑，用于从旧格式 `.md` 文件的内容中解析出摘要，并填充到 `QuipuNode` 实例中。
4.  在 `quipu-cli` 中，重构 `log` 命令，移除所有本地的摘要生成逻辑，改为直接使用 `node.summary`。
5.  确保所有测试（包括之前失败的测试）都能通过。

## 标签
#comp/cli #comp/engine #comp/interfaces #concept/history #scope/core

---

## Script

### Acts 1: 升级核心数据模型

我们在 `QuipuNode` 中添加 `summary` 字段，使其成为节点的核心属性之一。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-interfaces/src/quipu/core/models.py
~~~~~
~~~~~python
    # 文件主体内容
    content: str = ""
    
    # --- 图遍历字段 (由加载器填充) ---
~~~~~
~~~~~python
    # 文件主体内容
    content: str = ""

    # 从元数据或内容生成的单行摘要
    summary: str = ""
    
    # --- 图遍历字段 (由加载器填充) ---
~~~~~

### Acts 2: 更新数据读取器以填充摘要

我们确保两个 `Reader` 实现都能正确填充新的 `summary` 字段。

首先，更新 `GitObjectHistoryReader` 以从 `metadata.json` 读取权威摘要。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
                node = QuipuNode(
                    # Placeholder, will be filled in the linking phase
                    input_tree="", 
                    output_tree=output_tree,
                    timestamp=datetime.fromtimestamp(float(meta_data.get("exec", {}).get("start") or entry["timestamp"])),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=meta_data.get("type", "unknown"),
                    content=content,
                )
~~~~~
~~~~~python
                node = QuipuNode(
                    # Placeholder, will be filled in the linking phase
                    input_tree="", 
                    output_tree=output_tree,
                    timestamp=datetime.fromtimestamp(float(meta_data.get("exec", {}).get("start") or entry["timestamp"])),
                    filename=Path(f".quipu/git_objects/{commit_hash}"),
                    node_type=meta_data.get("type", "unknown"),
                    content=content,
                    summary=meta_data.get("summary", "No summary available"),
                )
~~~~~

其次，更新 `history.py` (供 `FileSystemHistoryReader` 使用) 以便为旧节点生成摘要。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/history.py
~~~~~
~~~~~python
            node = QuipuNode(
                input_tree=input_hash, output_tree=output_hash,
                timestamp=datetime.strptime(ts_str, "%Y%m%d%H%M%S"),
                filename=file_path, node_type=meta.get("type", "unknown"),
                content=body_content
            )
            all_nodes.append(node)
~~~~~
~~~~~python
            node_type = meta.get("type", "unknown")
            # For legacy nodes, we generate a summary on the fly.
            summary = "No description"
            if node_type == 'plan':
                # Simple heuristic: find the first non-empty line after `~~~act`
                in_act_block = False
                for line in body_content.strip().split('\n'):
                    if line.strip().startswith(('~~~act', '```act')): in_act_block = True; continue
                    if in_act_block and line.strip(): summary = line.strip(); break
                if not summary or summary in ('~~~', '```'): summary = "Plan executed"
            elif node_type == 'capture':
                # Prioritize user message from the body
                match = re.search(r"### 💬 备注:\n(.*?)\n\n", body_content, re.DOTALL)
                if match:
                    summary = match.group(1).strip()
                else:
                    summary = "Workspace changes captured"

            node = QuipuNode(
                input_tree=input_hash, output_tree=output_hash,
                timestamp=datetime.strptime(ts_str, "%Y%m%d%H%M%S"),
                filename=file_path, node_type=node_type,
                content=body_content,
                summary=(summary[:75] + '...') if len(summary) > 75 else summary
            )
            all_nodes.append(node)
~~~~~

### Acts 3: 简化 `log` 命令以使用权威摘要

最后，我们移除 `log` 命令中所有脆弱的摘要解析逻辑，使其直接使用 `node.summary`。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
        color = typer.colors.CYAN if node.node_type == "plan" else typer.colors.MAGENTA
        tag = f"[{node.node_type.upper()}]"
        summary = ""
        content_lines = node.content.strip().split('\n')
        if node.node_type == 'plan':
            in_act_block = False
            for line in content_lines:
                if line.strip().startswith(('~~~act', '```act')): in_act_block = True; continue
                if in_act_block and line.strip(): summary = line.strip(); break
            if not summary: summary = "Plan executed"
        elif node.node_type == 'capture':
            in_diff_block = False; diff_summary_lines = []
            for line in content_lines:
                if "变更文件摘要" in line: in_diff_block = True; continue
                if in_diff_block and line.strip().startswith('```'): break
                if in_diff_block and line.strip(): diff_summary_lines.append(line.strip())
            if diff_summary_lines:
                files_changed = [l.split('|')[0].strip() for l in diff_summary_lines]
                summary = f"Changes captured in: {', '.join(files_changed)}"
            else: summary = "Workspace changes captured"
        summary = (summary[:75] + '...') if len(summary) > 75 else summary
        typer.secho(f"{ts} {tag:<9} {node.short_hash}", fg=color, nl=False, err=True)
        typer.echo(f" - {summary}", err=True)
~~~~~
~~~~~python
        color = typer.colors.CYAN if node.node_type == "plan" else typer.colors.MAGENTA
        tag = f"[{node.node_type.upper()}]"
        summary = node.summary # Use the authoritative summary from the node object
        typer.secho(f"{ts} {tag:<9} {node.short_hash}", fg=color, nl=False, err=True)
        typer.echo(f" - {summary}", err=True)
~~~~~