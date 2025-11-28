好的，你的想法非常有远见。将 `show` 命令设计得不依赖于硬编码的文件结构 (`metadata.json`, `content.md`)，而是动态地展示节点 Git Tree 中的所有内容，这极大地增强了它的健壮性和面向未来的扩展性。同时，提供 `--json` 和 `--extract` 选项将使其成为一个强大的脚本和调试工具。

我将生成一个计划来实现这个更优雅、更强大的 `quipu show` 命令。

## [WIP] refactor(cli): 增强 `show` 命令以支持 JSON 输出和动态文件提取

### 用户需求
需要对新创建的 `quipu show` 命令进行重构，以满足以下高级需求：
1.  **JSON 输出**: 提供一个 `--json` 标志，将节点内的所有文件（`metadata.json`, `content.md`, `intent.md` 等）及其内容作为一个 JSON 对象输出到 `stdout`，以方便脚本调用。
2.  **动态文件发现**: 命令不应硬编码查找 `metadata.json` 和 `content.md`。它应该能够动态地发现并展示节点对应 Git Tree 中的所有文件。
3.  **单文件提取**: 提供一个 `--extract <filename>` 标志，用于仅提取并打印指定文件的原始内容。此功能应能与 `--json` 标志组合使用（将文件内容作为 JSON 字符串输出）。

### 评论
这是一个卓越的架构改进。它将 `quipu show` 从一个简单的“信息查看器”提升为一个灵活的“数据提取工具”。动态发现文件的能力确保了当 Quipu 的数据持久化协议（QDPS）未来演进（例如正式加入 `intent.md`）时，此命令无需任何修改即可兼容，这是一种非常优雅的解耦。为脚本提供结构化的 JSON 输出是提升开发者体验（DX）的关键一步。

### 目标
1.  在 `HistoryReader` 接口中添加一个 `get_node_blobs(commit_hash: str) -> Dict[str, bytes]` 方法，用于获取节点内所有文件的原始字节内容。
2.  在 `GitDB` 中添加一个底层辅助方法 `get_blobs_from_tree`。
3.  在 `GitObjectHistoryReader` 中实现新接口，直接调用 `GitDB`。
4.  在 `SQLiteHistoryReader` 中实现新接口，通过委托给其内部的 `_git_reader` 来提供此功能，以此作为一种兼容策略，避免立即进行复杂的数据库迁移。
5.  彻底重构 `quipu-cli` 中的 `show.py`，实现对 `--json` 和 `--extract` 参数的处理逻辑。

### 基本原理
我们将数据访问的粒度从“获取特定文件”泛化为“获取节点内的所有文件”。新的 `get_node_blobs` 方法将成为 `show` 命令唯一的数据源。该方法返回一个字典，键是文件名，值是文件内容的字节流。

在 CLI 层，`show` 命令的逻辑将变为：
1.  调用 `engine.reader.get_node_blobs()` 获取数据字典。
2.  检查 `--extract` 标志。如果存在，则从字典中提取特定文件。
3.  检查 `--json` 标志。如果存在，则将目标数据（整个字典或提取的单个文件内容）序列化为 JSON 并打印。
4.  如果两个标志都不存在，则进入“人类可读”模式，遍历字典，根据文件名（`.json`, `.md` 等）智能地选择不同的格式化方式进行打印。

`SQLiteHistoryReader` 无法直接从数据库满足此请求，因为它只缓存了部分数据。因此，它将把这个特定的请求“穿透”到底层的 `GitObjectHistoryReader`，这是一种务实且高效的实现策略。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/engine #comp/interfaces #concept/history #scope/api #scope/dx #ai/instruct #task/domain/cli #task/object/show-command #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 升级 `HistoryReader` 接口

我们将用一个更通用的方法 `get_node_blobs` 替换 `get_node_metadata_raw`。

~~~~~act
patch_file
packages/quipu-interfaces/src/quipu/core/storage.py
~~~~~
~~~~~python
    @abstractmethod
    def get_node_metadata_raw(self, commit_hash: str) -> Optional[str]:
        """获取指定节点未经解析的原始 metadata JSON 字符串。"""
        pass
~~~~~
~~~~~python
    @abstractmethod
    def get_node_blobs(self, commit_hash: str) -> Dict[str, bytes]:
        """获取一个节点内所有文件的原始二进制内容，以字典形式返回 {filename: content_bytes}。"""
        pass
~~~~~

#### Acts 2: 在 `GitDB` 中添加底层 Tree 解析能力

为了实现 `get_node_blobs`，我们需要一个 `GitDB` 的辅助函数来解析 tree 并批量获取 blobs。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
        result = self._run(cmd)
        return result.stdout.encode("utf-8")

    def batch_cat_file(self, object_hashes: List[str]) -> Dict[str, bytes]:
        """
        批量读取 Git 对象。
~~~~~
~~~~~python
        result = self._run(cmd)
        return result.stdout.encode("utf-8")

    def get_blobs_from_tree(self, tree_hash: str) -> Dict[str, bytes]:
        """解析一个 Tree 对象，并返回其包含的所有 blob 文件的 {filename: content_bytes} 字典。"""
        # 1. 获取 Tree 的内容
        tree_content_bytes = self.cat_file(tree_hash, "tree")
        tree_content = tree_content_bytes.decode("utf-8", "ignore")

        # 2. 解析 Tree 内容以获取 blob 哈希
        # 格式: <mode> <type> <hash>\t<filename>
        blob_info = {}
        for line in tree_content.strip().splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[1] == "blob":
                blob_hash, filename = parts[2], parts[3]
                blob_info[filename] = blob_hash

        if not blob_info:
            return {}

        # 3. 批量获取所有 blob 的内容
        return self.batch_cat_file(list(blob_info.values()))

    def batch_cat_file(self, object_hashes: List[str]) -> Dict[str, bytes]:
        """
        批量读取 Git 对象。
~~~~~

#### Acts 3: 在后端实现新接口

首先是 `GitObjectHistoryReader` 的原生实现。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~
~~~~~python
    def get_node_metadata_raw(self, commit_hash: str) -> Optional[str]:
        """从 Git 对象中按需读取并返回 metadata.json 的内容。"""
        try:
            # 1. Get Tree Hash from Commit
            commit_bytes = self.git_db.cat_file(commit_hash, "commit")
            tree_line = commit_bytes.split(b"\n", 1)[0].decode("utf-8")
            if not tree_line.startswith("tree "):
                raise ValueError("Invalid commit object format")
            tree_hash = tree_line.split()[1]

            # 2. Get metadata.json Blob Hash from Tree
            tree_content_map = self.git_db.batch_cat_file([tree_hash])
            if tree_hash not in tree_content_map:
                return None
            tree_content = tree_content_map[tree_hash]
            entries = self._parse_tree_binary(tree_content)
            blob_hash = entries.get("metadata.json")

            if not blob_hash:
                return None  # No metadata found

            # 3. Read Blob content
            content_bytes = self.git_db.cat_file(blob_hash)
            return content_bytes.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Failed to lazy load raw metadata for commit {commit_hash[:7]}: {e}")
            return None
~~~~~
~~~~~python
    def get_node_blobs(self, commit_hash: str) -> Dict[str, bytes]:
        """从 Git 对象中读取节点的所有文件内容。"""
        try:
            # 1. Get Tree Hash from Commit
            commit_content = self.git_db.cat_file(commit_hash, "commit").decode("utf-8", "ignore")
            tree_line = commit_content.split("\n", 1)[0]
            if not tree_line.startswith("tree "):
                raise ValueError("Invalid commit object format")
            tree_hash = tree_line.split()[1]

            # 2. 解析 Tree 并批量获取所有 blobs
            # We need to map blob hashes back to filenames.
            tree_content_bytes = self.git_db.cat_file(tree_hash, "tree")
            entries = self._parse_tree_binary(tree_content_bytes)

            blob_hashes = list(entries.values())
            blob_contents = self.git_db.batch_cat_file(blob_hashes)

            # Reconstruct the {filename: content} map
            result = {}
            for filename, blob_hash in entries.items():
                if blob_hash in blob_contents:
                    result[filename] = blob_contents[blob_hash]
            return result

        except Exception as e:
            logger.error(f"Failed to load blobs for commit {commit_hash[:7]}: {e}")
            return {}
~~~~~

然后是 `SQLiteHistoryReader` 的委托实现。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/sqlite_storage.py
~~~~~
~~~~~python
    def get_node_metadata_raw(self, commit_hash: str) -> Optional[str]:
        """从 SQLite 高效获取原始 meta_json 字符串。"""
        conn = self.db_manager._get_conn()
        try:
            cursor = conn.execute("SELECT meta_json FROM nodes WHERE commit_hash = ?", (commit_hash,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get raw metadata for {commit_hash[:7]}: {e}")
            return None
~~~~~
~~~~~python
    def get_node_blobs(self, commit_hash: str) -> Dict[str, bytes]:
        """
        从 Git 回源获取节点的所有文件内容。
        SQLite 缓存不存储所有 blob，因此此操作总是委托给底层的 git_reader。
        """
        return self._git_reader.get_node_blobs(commit_hash)
~~~~~

#### Acts 4: 重构 `show` CLI 命令

现在我们用新的数据获取方式和参数处理逻辑重写 `show.py`。

~~~~~act
write_file
packages/quipu-cli/src/quipu/cli/commands/show.py
~~~~~
~~~~~python
import json
import logging
from pathlib import Path
from typing import Annotated, Optional, Dict

import typer
from rich.console import Console
from rich.syntax import Syntax

from .helpers import engine_context
from ..config import DEFAULT_WORK_DIR

logger = logging.getLogger(__name__)


def _find_target_node(graph: Dict, hash_prefix: str):
    """辅助函数，用于在图中查找唯一的节点。"""
    matches = [
        node
        for node in graph.values()
        if node.commit_hash.startswith(hash_prefix) or node.output_tree.startswith(hash_prefix)
    ]
    if not matches:
        typer.secho(f"❌ 错误: 未找到哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if len(matches) > 1:
        typer.secho(
            f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    return matches[0]


def register(app: typer.Typer):
    @app.command()
    def show(
        ctx: typer.Context,
        hash_prefix: Annotated[str, typer.Argument(help="目标状态节点的 commit_hash 或 output_tree 的哈希前缀。")],
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
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
                        syntax = Syntax(output_data, "json", theme="default", line_numbers=True)
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

### 下一步建议
- **编写全面的测试**：为 `quipu show` 命令编写新的测试用例，覆盖 `--json`、`--extract` 以及两者组合的场景，并验证当请求不存在的文件时是否能正确报错。
- **更新文档**：这是一个重要的用户功能，需要在用户手册中详细记录 `quipu show` 的用法，特别是新增的 `--json` 和 `--extract` 选项。
- **二进制文件处理**：当前实现对二进制文件仅显示大小。可以考虑在 `--json` 模式下提供 `base64` 编码的选项，以支持更复杂的脚本处理需求。
