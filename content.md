# perf/git-batch Git 批处理读取优化

## 用户需求
`GitObjectHistoryReader.load_all_nodes` 方法存在 N+1 查询问题，在加载大量历史节点时性能严重下降，导致“补水”流程不可用。

## 评论
这是 Quipu 迈向生产级应用的关键一步。通过将 O(N) 的进程启动开销降低为 O(1)，我们为未来支持数千甚至数万个历史节点奠定了基础。

## 目标
利用 `git cat-file --batch` 将历史加载过程中的 Git 调用次数从 `2N` 降低到 `2` 次。

## 基本原理
1.  **Git Plumbing**: 使用 `git cat-file --batch` 接口，它允许通过标准输入批量请求对象，并通过标准输出流式返回结果。
2.  **批处理管线**:
    *   Phase 1: 批量获取所有 Commit 指向的 Tree 对象。
    *   Phase 2: 在内存中解析 Tree，提取 `metadata.json` 的 Blob Hash。
    *   Phase 3: 批量获取所有 Metadata Blob。
    *   Phase 4: 组装节点。
3.  **懒加载保持**: `content.md` 依然保持懒加载（不在 `load_all_nodes` 中读取），因此本次优化仅针对元数据加载。

## 标签
#comp/engine #concept/perf #scope/core

---

## Script

### Acts 1: 实现 GitDB 批处理底层能力

在 `GitDB` 中增加 `batch_cat_file` 方法，封装对 `git cat-file --batch` 的流式操作。

~~~~~act
write_file packages/quipu-engine/src/quipu/core/git_db.py
~~~~~

~~~~~python
import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union
from contextlib import contextmanager
from quipu.core.exceptions import ExecutionError

logger = logging.getLogger(__name__)

class GitDB:
    """
    Axon 的 Git 底层接口 (Plumbing Interface)。
    负责与 Git 对象数据库交互，维护 Shadow Index 和 Refs。
    """
    def __init__(self, root_dir: Path):
        if not shutil.which("git"):
            raise ExecutionError("未找到 'git' 命令。请安装 Git 并确保它在系统的 PATH 中。")

        self.root = root_dir.resolve()
        self.quipu_dir = self.root / ".quipu"
        self._ensure_git_repo()

    def _ensure_git_repo(self):
        """确保目标是一个 Git 仓库"""
        if not (self.root / ".git").is_dir():
            # 这是一个关键的前置条件检查
            raise ExecutionError(f"工作目录 '{self.root}' 不是一个有效的 Git 仓库。请先运行 'git init'。")

    def _run(
        self,
        args: list[str],
        env: Optional[Dict] = None,
        check: bool = True,
        log_error: bool = True,
        input_data: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        """执行 git 命令的底层封装，返回完整的 CompletedProcess 对象"""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
            
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.root,
                env=full_env,
                capture_output=True,
                text=True,
                check=check,
                input=input_data
            )
            return result
        except subprocess.CalledProcessError as e:
            if log_error:
                logger.error(f"Git plumbing error: {e.stderr}")
            raise RuntimeError(f"Git command failed: {' '.join(args)}\n{e.stderr}") from e

    @contextmanager
    def shadow_index(self):
        """
        上下文管理器：创建一个隔离的 Shadow Index。
        在此上下文内的操作不会污染用户的 .git/index。
        """
        index_path = self.quipu_dir / "tmp_index"
        self.quipu_dir.mkdir(exist_ok=True)
        
        # 定义隔离的环境变量
        env = {"GIT_INDEX_FILE": str(index_path)}
        
        try:
            yield env
        finally:
            # 无论成功失败，必须清理临时索引文件
            if index_path.exists():
                try:
                    index_path.unlink()
                except OSError:
                    logger.warning(f"Failed to cleanup shadow index: {index_path}")

    def get_tree_hash(self) -> str:
        """
        计算当前工作区的 Tree Hash (Snapshot)。
        实现 'State is Truth' 的核心。
        """
        with self.shadow_index() as env:
            # 1. 将当前工作区全量加载到影子索引
            # 使用 ':(exclude).quipu' 确保 Axon 自身数据不影响状态计算
            # -A: 自动处理添加、修改、删除
            # --ignore-errors: 即使某些文件无法读取也继续（尽力而为）
            self._run(
                ["add", "-A", "--ignore-errors", ".", ":(exclude).quipu"],
                env=env
            )
            
            # 2. 将索引写入对象库，返回 Tree Hash
            result = self._run(["write-tree"], env=env)
            return result.stdout.strip()

    def hash_object(self, content_bytes: bytes, object_type: str = "blob") -> str:
        """
        将内容写入 Git 对象数据库并返回对象哈希。
        """
        try:
            result = subprocess.run(
                ["git", "hash-object", "-w", "-t", object_type, "--stdin"],
                cwd=self.root,
                input=content_bytes,
                capture_output=True,
                check=True
            )
            return result.stdout.decode('utf-8').strip()
        except subprocess.CalledProcessError as e:
            stderr_str = e.stderr.decode('utf-8') if e.stderr else "No stderr"
            logger.error(f"Git hash-object failed: {stderr_str}")
            raise RuntimeError(f"Git command failed: hash-object\n{stderr_str}") from e

    def mktree(self, tree_descriptor: str) -> str:
        """
        从描述符创建 tree 对象并返回其哈希。
        """
        result = self._run(["mktree"], input_data=tree_descriptor)
        return result.stdout.strip()

    def commit_tree(self, tree_hash: str, parent_hashes: Optional[List[str]], message: str) -> str:
        """
        创建一个 commit 对象并返回其哈希。
        """
        cmd = ["commit-tree", tree_hash]
        if parent_hashes:
            for p in parent_hashes:
                cmd.extend(["-p", p])
        
        result = self._run(cmd, input_data=message)
        return result.stdout.strip()

    def update_ref(self, ref_name: str, commit_hash: str):
        """
        更新引用 (如 refs/quipu/history)。
        防止 Commit 被 GC 回收。
        """
        self._run(["update-ref", ref_name, commit_hash])

    def delete_ref(self, ref_name: str):
        """删除指定的引用"""
        self._run(["update-ref", "-d", ref_name], check=False)

    def get_commit_by_output_tree(self, tree_hash: str) -> Optional[str]:
        """
        根据 Trailer 中的 X-Quipu-Output-Tree 查找对应的 Commit Hash。
        用于在创建新节点时定位语义上的父节点。
        """
        # 使用 grep 搜索所有 refs/quipu/ 下的记录
        # 注意：这假设 Output Tree 是唯一的，这在大概率上是成立的，
        # 且即使有重复（如 merge），找到任意一个作为父节点通常也是可接受的起点。
        cmd = [
            "log",
            "--all",
            f"--grep=X-Quipu-Output-Tree: {tree_hash}",
            "--format=%H",
            "-n", "1"
        ]
        res = self._run(cmd, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return None

    def get_head_commit(self) -> Optional[str]:
        """获取当前工作区 HEAD 的 Commit Hash"""
        try:
            result = self._run(["rev-parse", "HEAD"])
            return result.stdout.strip()
        except RuntimeError:
            return None # 可能是空仓库

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """
        判断两个 Commit 是否具有血统关系。
        用于解决 'Lost Time' 问题。
        """
        # merge-base --is-ancestor A B 返回 0 表示真，1 表示假
        # 我们在这里直接调用 subprocess，因为我们关心返回码而不是输出
        result = self._run(
            ["merge-base", "--is-ancestor", ancestor, descendant],
            check=False, # 必须禁用 check，否则非 0 退出码会抛异常
            log_error=False # 我们不认为这是一个错误
        )
        return result.returncode == 0

    def get_diff_stat(self, old_tree: str, new_tree: str) -> str:
        """
        获取两个 Tree 之间的差异统计 (Human Readable)。
        """
        result = self._run(["diff-tree", "--stat", old_tree, new_tree])
        return result.stdout.strip()

    def get_diff_name_status(self, old_tree: str, new_tree: str) -> List[Tuple[str, str]]:
        """
        获取两个 Tree 之间的文件变更状态列表 (M, A, D, etc.)。
        """
        result = self._run(["diff-tree", "--name-status", "--no-commit-id", "-r", old_tree, new_tree])
        changes = []
        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status, path = parts
                changes.append((status, path))
        return changes

    def checkout_tree(self, tree_hash: str):
        """
        将工作区强制重置为目标 Tree 的状态。
        这是一个底层方法，上层应确保工作区的未提交更改已被处理。
        """
        logger.info(f"Executing hard checkout to tree: {tree_hash[:7]}")
        
        # 1. 使用 read-tree 更新索引，这是一个安全的操作
        self._run(["read-tree", tree_hash])
        
        # 2. 从更新后的索引检出文件，-a (all) -f (force)
        self._run(["checkout-index", "-a", "-f"])
        
        # 3. 清理工作区中多余的文件和目录
        # -d: 目录, -f: 强制
        # 移除了 -x 参数，以尊重 .gitignore 规则
        # -e .quipu: 排除 .quipu 目录，防止自毁
        self._run(["clean", "-df", "-e", ".quipu"])
        
        logger.info("✅ Workspace reset to target state.")

    def cat_file(self, object_hash: str, object_type: str = "blob") -> bytes:
        """读取 Git 对象的内容，返回字节流。"""
        # 使用 -p (pretty print) for commits/trees, and no flag for blobs
        cmd = ["cat-file"]
        if object_type in ["commit", "tree"]:
            cmd.append("-p")
        else:
            cmd.append(object_type)
        cmd.append(object_hash)

        result = self._run(cmd)
        return result.stdout.encode('utf-8')

    def batch_cat_file(self, object_hashes: List[str]) -> Dict[str, bytes]:
        """
        批量读取 Git 对象。
        解决 N+1 查询性能问题。
        
        Args:
            object_hashes: 需要读取的对象哈希列表 (可以重复，内部会自动去重)
            
        Returns:
            Dict[hash, content_bytes]: 哈希到内容的映射。
            如果对象不存在，则不会出现在返回字典中。
        """
        if not object_hashes:
            return {}
            
        # Deduplicate
        unique_hashes = list(set(object_hashes))
        
        # Prepare input: <hash>\n
        input_str = "\n".join(unique_hashes) + "\n"
        
        results = {}
        
        try:
            # git cat-file --batch format:
            # <hash> <type> <size>\n
            # <content>\n
            with subprocess.Popen(
                ["git", "cat-file", "--batch"],
                cwd=self.root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # bufsize=0 is often recommended for binary streams but careful buffering is usually fine
            ) as proc:
                
                # Write requests and close stdin to signal EOF
                if proc.stdin:
                    proc.stdin.write(input_str.encode('utf-8'))
                    proc.stdin.close()
                
                if not proc.stdout:
                    return {}

                while True:
                    # Read header line
                    header_line = proc.stdout.readline()
                    if not header_line:
                        break
                    
                    header_parts = header_line.strip().split()
                    if not header_parts:
                        continue
                        
                    obj_hash_bytes = header_parts[0]
                    obj_hash = obj_hash_bytes.decode('utf-8')
                    
                    # Check for missing object: "<hash> missing"
                    if len(header_parts) == 2 and header_parts[1] == b"missing":
                        continue
                    
                    if len(header_parts) < 3:
                        logger.warning(f"Unexpected git cat-file header: {header_line}")
                        continue
                        
                    # size is at index 2
                    try:
                        size = int(header_parts[2])
                    except ValueError:
                        logger.warning(f"Invalid size in header: {header_line}")
                        continue
                    
                    # Read content bytes + trailing newline
                    content = proc.stdout.read(size)
                    proc.stdout.read(1) # Consume the trailing LF
                    
                    results[obj_hash] = content
                    
        except Exception as e:
            logger.error(f"Batch cat-file failed: {e}")
            raise RuntimeError(f"Git batch operation failed: {e}") from e

        return results

    def get_all_ref_heads(self, prefix: str) -> List[str]:
        """查找指定前缀下的所有 ref heads 并返回其 commit 哈希。"""
        res = self._run(["for-each-ref", f"--format=%(objectname)", prefix], check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return []
        return res.stdout.strip().splitlines()

    def has_quipu_ref(self) -> bool:
        """检查是否存在任何 'refs/quipu/' 引用，用于判断存储格式。"""
        # We use show-ref and check the exit code. Exit 0 if refs exist, 1 otherwise.
        res = self._run(["show-ref", "--verify", "--quiet", "refs/quipu/"], check=False, log_error=False)
        return res.returncode == 0

    def log_ref(self, ref_names: Union[str, List[str]]) -> List[Dict[str, str]]:
        """获取指定引用的日志，并解析为结构化数据列表。"""
        # A unique delimiter that's unlikely to appear in commit messages
        DELIMITER = "---QUIPU-LOG-ENTRY---"
        # Format: H=hash, P=parent, T=tree, ct=commit_timestamp, B=body
        log_format = f"%H%n%P%n%T%n%ct%n%B{DELIMITER}"
        
        if isinstance(ref_names, str):
            refs_to_log = [ref_names]
        else:
            refs_to_log = ref_names

        if not refs_to_log:
            return []
        
        # Git log on multiple refs will automatically show the union of their histories without duplicates.
        cmd = ["log", f"--format={log_format}"] + refs_to_log
        res = self._run(cmd, check=False, log_error=False)

        if res.returncode != 0:
            return []

        entries = res.stdout.strip().split(DELIMITER)
        parsed_logs = []
        for entry in entries:
            if not entry.strip():
                continue
            
            parts = entry.strip().split('\n', 4)
            if len(parts) >= 4:
                parsed_logs.append({
                    "hash": parts[0],
                    "parent": parts[1],
                    "tree": parts[2],
                    "timestamp": parts[3],
                    "body": parts[4] if len(parts) > 4 else ""
                })
        return parsed_logs
~~~~~

### Acts 2: 重构 Reader 以使用批处理

修改 `GitObjectHistoryReader.load_all_nodes`，移除循环中的 `cat_file` 调用，改为三阶段批处理加载。

~~~~~act
write_file packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~

~~~~~python
import json
import logging
import os
import platform
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib.metadata

from quipu.core.git_db import GitDB
from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader, HistoryWriter

logger = logging.getLogger(__name__)


class GitObjectHistoryReader(HistoryReader):
    """
    一个从 Git 底层对象读取历史的实现。
    使用批处理优化加载性能。
    """
    def __init__(self, git_db: GitDB):
        self.git_db = git_db

    def _parse_output_tree_from_body(self, body: str) -> Optional[str]:
        match = re.search(r"X-Quipu-Output-Tree:\s*([0-9a-f]{40})", body)
        return match.group(1) if match else None

    def load_all_nodes(self) -> List[QuipuNode]:
        """
        加载所有节点。
        优化策略: Batch cat-file
        1. 获取所有 commits
        2. 批量读取所有 Trees
        3. 解析 Trees 找到 metadata.json Blob Hashes
        4. 批量读取所有 Metadata Blobs
        5. 组装 Nodes
        """
        # Step 1: Get Commits
        all_heads = self.git_db.get_all_ref_heads("refs/quipu/")
        if not all_heads:
            return []

        log_entries = self.git_db.log_ref(all_heads)
        if not log_entries:
            return []

        # Step 2: Batch fetch Trees
        tree_hashes = [entry["tree"] for entry in log_entries]
        trees_content = self.git_db.batch_cat_file(tree_hashes)

        # Step 3: Parse Trees to find Metadata Blob Hashes
        # Map tree_hash -> metadata_blob_hash
        tree_to_meta_blob = {}
        meta_blob_hashes = []

        for tree_hash, content_bytes in trees_content.items():
            try:
                content_str = content_bytes.decode('utf-8')
                for line in content_str.splitlines():
                    # format: <mode> <type> <hash>\t<filename>
                    parts = line.split()
                    if len(parts) == 4 and parts[3] == "metadata.json":
                        blob_hash = parts[2]
                        tree_to_meta_blob[tree_hash] = blob_hash
                        meta_blob_hashes.append(blob_hash)
                        break
            except Exception:
                pass # Skip corrupted trees

        # Step 4: Batch fetch Metadata Blobs
        metas_content = self.git_db.batch_cat_file(meta_blob_hashes)

        # Step 5: Assemble Nodes
        temp_nodes: Dict[str, QuipuNode] = {}
        parent_map: Dict[str, str] = {}

        for entry in log_entries:
            commit_hash = entry["hash"]
            tree_hash = entry["tree"]
            
            # Skip if already processed (though log entries shouldn't duplicate commits usually)
            if commit_hash in temp_nodes:
                continue

            try:
                # Retrieve metadata content
                if tree_hash not in tree_to_meta_blob:
                    logger.warning(f"Skipping commit {commit_hash[:7]}: metadata.json not found in tree.")
                    continue
                
                meta_blob_hash = tree_to_meta_blob[tree_hash]
                
                if meta_blob_hash not in metas_content:
                    logger.warning(f"Skipping commit {commit_hash[:7]}: metadata blob missing.")
                    continue

                meta_bytes = metas_content[meta_blob_hash]
                meta_data = json.loads(meta_bytes)

                output_tree = self._parse_output_tree_from_body(entry["body"])
                if not output_tree:
                    logger.warning(f"Skipping commit {commit_hash[:7]}: X-Quipu-Output-Tree trailer not found.")
                    continue

                # Content is lazy loaded
                content = "" 

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
                
                temp_nodes[commit_hash] = node
                parent_hash = entry["parent"].split(" ")[0] if entry["parent"] else None
                if parent_hash:
                    parent_map[commit_hash] = parent_hash

            except Exception as e:
                logger.error(f"Failed to load history node from commit {commit_hash[:7]}: {e}")

        # Phase 2: Link nodes (Same as before)
        for commit_hash, node in temp_nodes.items():
            parent_commit_hash = parent_map.get(commit_hash)
            if parent_commit_hash and parent_commit_hash in temp_nodes:
                parent_node = temp_nodes[parent_commit_hash]
                node.parent = parent_node
                parent_node.children.append(node)
                node.input_tree = parent_node.output_tree
            else:
                node.input_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

        # Sort children by timestamp
        for node in temp_nodes.values():
            node.children.sort(key=lambda n: n.timestamp)
            
        return list(temp_nodes.values())

    def get_node_content(self, node: QuipuNode) -> str:
        """
        从 Git Commit 中按需读取 content.md。
        node.filename 被 hack 为 ".quipu/git_objects/{commit_hash}"
        """
        if node.content:
            return node.content

        try:
            # Extract commit hash from the virtual filename
            commit_hash = node.filename.name
            
            # 1. Get Tree Hash from Commit
            commit_bytes = self.git_db.cat_file(commit_hash, "commit")
            # Parse "tree {hash}" from the first line
            tree_line = commit_bytes.split(b"\n", 1)[0].decode("utf-8")
            if not tree_line.startswith("tree "):
                raise ValueError("Invalid commit object format")
            tree_hash = tree_line.split()[1]

            # 2. Get content.md Blob Hash from Tree
            tree_content = self.git_db.cat_file(tree_hash, "tree").decode('utf-8')
            blob_hash = None
            for line in tree_content.splitlines():
                # format: <mode> <type> <hash>\t<filename>
                parts = line.split()
                if len(parts) == 4 and parts[3] == "content.md":
                    blob_hash = parts[2]
                    break
            
            if not blob_hash:
                return "" # No content found
            
            # 3. Read Blob
            content_bytes = self.git_db.cat_file(blob_hash)
            content = content_bytes.decode('utf-8', errors='ignore')
            
            # Cache it
            node.content = content
            return content

        except Exception as e:
            logger.error(f"Failed to lazy load content for node {node.short_hash}: {e}")
            return ""


class GitObjectHistoryWriter(HistoryWriter):
    """
    一个将历史节点作为 Git 底层对象写入存储的实现。
    遵循 Quipu 数据持久化协议规范 (QDPS) v1.0。
    """

    def __init__(self, git_db: GitDB):
        self.git_db = git_db

    def _get_generator_info(self) -> Dict[str, str]:
        """根据 QDPS v1.0 规范，通过环境变量获取生成源信息。"""
        return {
            "id": os.getenv("QUIPU_GENERATOR_ID", "manual"),
            "tool": os.getenv("QUIPU_TOOL", "quipu-cli"),
        }

    def _get_env_info(self) -> Dict[str, str]:
        """获取运行时环境指纹。"""
        try:
            quipu_version = importlib.metadata.version("quipu-engine")
        except importlib.metadata.PackageNotFoundError:
            quipu_version = "unknown"

        return {
            "quipu": quipu_version,
            "python": platform.python_version(),
            "os": platform.system().lower(),
        }

    def _generate_summary(
        self,
        node_type: str,
        content: str,
        input_tree: str,
        output_tree: str,
        **kwargs: Any,
    ) -> str:
        """根据节点类型生成单行摘要。"""
        if node_type == "plan":
            # 优先从 act 块中提取摘要
            summary = ""
            in_act_block = False
            for line in content.strip().splitlines():
                clean_line = line.strip()
                if clean_line.startswith(('~~~act', '```act')):
                    in_act_block = True
                    continue
                
                if in_act_block:
                    if clean_line.startswith(('~~~', '```')):
                        break  # 块结束
                    if clean_line:
                        summary = clean_line
                        break  # 找到摘要
            
            if summary:
                return (summary[:75] + '...') if len(summary) > 75 else summary

            # 回退：尝试从 Markdown 的第一个标题中提取
            match = re.search(r"^\s*#{1,6}\s+(.*)", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            
            # Fallback to the first non-empty line
            first_line = next((line.strip() for line in content.strip().splitlines() if line.strip()), "Plan executed")
            return (first_line[:75] + '...') if len(first_line) > 75 else first_line

        elif node_type == "capture":
            user_message = (kwargs.get("message") or "").strip()
            
            changes = self.git_db.get_diff_name_status(input_tree, output_tree)
            if not changes:
                auto_summary = "Capture: No changes detected"
            else:
                formatted_changes = [f"{status} {Path(path).name}" for status, path in changes[:3]]
                summary_part = ", ".join(formatted_changes)
                if len(changes) > 3:
                    summary_part += f" ... and {len(changes) - 3} more files"
                auto_summary = f"Capture: {summary_part}"

            return f"{user_message} {auto_summary}".strip() if user_message else auto_summary
        
        return "Unknown node type"

    def create_node(
        self,
        node_type: str,
        input_tree: str,
        output_tree: str,
        content: str,
        **kwargs: Any,
    ) -> QuipuNode:
        """
        在 Git 对象数据库中创建并持久化一个新的历史节点。
        """
        start_time = kwargs.get("start_time", time.time())
        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        summary = self._generate_summary(
            node_type, content, input_tree, output_tree, **kwargs
        )

        metadata = {
            "meta_version": "1.0",
            "summary": summary,
            "type": node_type,
            "generator": self._get_generator_info(),
            "env": self._get_env_info(),
            "exec": {"start": start_time, "duration_ms": duration_ms},
        }

        meta_json_bytes = json.dumps(
            metadata, sort_keys=False, ensure_ascii=False
        ).encode("utf-8")
        content_md_bytes = content.encode("utf-8")

        meta_blob_hash = self.git_db.hash_object(meta_json_bytes)
        content_blob_hash = self.git_db.hash_object(content_md_bytes)

        # 使用 100444 权限 (只读文件)
        tree_descriptor = (
            f"100444 blob {meta_blob_hash}\tmetadata.json\n"
            f"100444 blob {content_blob_hash}\tcontent.md"
        )
        tree_hash = self.git_db.mktree(tree_descriptor)

        # 1. 确定父节点 (Topological Parent)
        parent_commit = self.git_db.get_commit_by_output_tree(input_tree)
        parents = [parent_commit] if parent_commit else None
        
        if not parent_commit and input_tree != "4b825dc642cb6eb9a060e54bf8d69288fbee4904":
             logger.warning(f"⚠️  Could not find parent commit for input state {input_tree[:7]}. This node may be detached.")

        # 2. 创建 Commit
        commit_message = f"{summary}\n\nX-Quipu-Output-Tree: {output_tree}"
        new_commit_hash = self.git_db.commit_tree(
            tree_hash=tree_hash, parent_hashes=parents, message=commit_message
        )

        # 3. 引用管理 (Multi-Head Strategy)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)
        self.git_db.update_ref(f"refs/quipu/heads/{new_commit_hash}", new_commit_hash)
        
        if parent_commit:
            self.git_db.delete_ref(f"refs/quipu/heads/{parent_commit}")

        logger.info(f"✅ History node created as commit {new_commit_hash[:7]}")

        # 返回一个 QuipuNode 实例，content 此时已在内存中，无需 Lazy Load
        return QuipuNode(
            input_tree=input_tree,
            output_tree=output_tree,
            timestamp=datetime.fromtimestamp(start_time),
            filename=Path(f".quipu/git_objects/{new_commit_hash}"),
            node_type=node_type,
            content=content,
        )
~~~~~

### Acts 3: 增加单元测试

在 `tests/test_git_db.py` 中增加对 `batch_cat_file` 的测试。

~~~~~act
write_file tests/test_git_db.py
~~~~~

~~~~~python
import pytest
import subprocess
from pathlib import Path
from quipu.core.git_db import GitDB

@pytest.fixture
def git_repo(tmp_path):
    """创建一个初始化的 Git 仓库"""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True)
    
    # 配置 User，防止 Commit 报错
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Axon Test"], cwd=root, check=True)
    
    return root

@pytest.fixture
def db(git_repo):
    """返回绑定到该仓库的 GitDB 实例"""
    return GitDB(git_repo)

class TestGitDBPlumbing:
    
    def test_get_tree_hash_stability(self, git_repo, db):
        """测试：内容不变，Hash 不变 (State Truth)"""
        f = git_repo / "test.txt"
        f.write_text("hello", encoding="utf-8")
        
        hash1 = db.get_tree_hash()
        hash2 = db.get_tree_hash()
        
        assert len(hash1) == 40
        assert hash1 == hash2

    def test_get_tree_hash_sensitivity(self, git_repo, db):
        """测试：内容变化，Hash 必变"""
        f = git_repo / "test.txt"
        f.write_text("v1", encoding="utf-8")
        hash1 = db.get_tree_hash()
        
        f.write_text("v2", encoding="utf-8")
        hash2 = db.get_tree_hash()
        
        assert hash1 != hash2

    def test_shadow_index_isolation(self, git_repo, db):
        """
        测试关键特性：零污染 (Zero Pollution)
        Axon 计算 Hash 的过程绝对不能把文件加入到用户的暂存区。
        """
        f = git_repo / "wip.txt"
        f.write_text("working in progress", encoding="utf-8")
        
        # 1. 确保用户暂存区是空的
        status_before = subprocess.check_output(["git", "status", "--porcelain"], cwd=git_repo).decode()
        assert "??" in status_before  # Untracked
        assert "A" not in status_before # Not staged
        
        # 2. Axon 执行计算
        _ = db.get_tree_hash()
        
        # 3. 验证用户暂存区依然是空的
        status_after = subprocess.check_output(["git", "status", "--porcelain"], cwd=git_repo).decode()
        assert status_after == status_before
        
        # 验证 Shadow Index 文件已被清理
        assert not (git_repo / ".quipu" / "tmp_index").exists()

    def test_exclude_quipu_dir(self, git_repo, db):
        """测试：.quipu 目录内的变化不应改变 Tree Hash"""
        (git_repo / "main.py").touch()
        hash_base = db.get_tree_hash()
        
        # 在 .quipu 目录下乱写东西
        quipu_dir = git_repo / ".quipu"
        quipu_dir.mkdir(exist_ok=True)
        (quipu_dir / "history.md").write_text("some history", encoding="utf-8")
        
        hash_new = db.get_tree_hash()
        
        assert hash_base == hash_new

    def test_anchor_commit_persistence(self, git_repo, db):
        """测试：创建影子锚点"""
        (git_repo / "f.txt").write_text("content")
        tree_hash = db.get_tree_hash()
        
        # 创建锚点
        commit_hash = db.commit_tree(tree_hash, parent_hashes=None, message="Axon Shadow Commit")
        
        # 更新引用
        ref_name = "refs/quipu/history"
        db.update_ref(ref_name, commit_hash)
        
        # 验证 Git 能够读取该引用
        read_back = subprocess.check_output(
            ["git", "rev-parse", ref_name], cwd=git_repo
        ).decode().strip()
        
        assert read_back == commit_hash
        
        # 验证该 Commit 确实指向正确的 Tree
        commit_tree = subprocess.check_output(
            ["git", "show", "--format=%T", "-s", commit_hash], cwd=git_repo
        ).decode().strip()
        
        assert commit_tree == tree_hash

    def test_hash_object(self, db):
        """测试 hash_object 能否正确创建 blob 并返回 hash。"""
        content = b"hello quipu blob"
        expected_hash = "9cb67783b5a82481c643efb6897e5412d4c221ea"
        
        blob_hash = db.hash_object(content, object_type="blob")
        assert blob_hash == expected_hash

    def test_mktree_and_commit_tree(self, db):
        """测试 mktree 和 commit_tree 的协同工作。"""
        # 1. Create a blob
        file_content = b"content of file.txt"
        blob_hash = db.hash_object(file_content)
        
        # 2. Create a tree
        tree_descriptor = f"100644 blob {blob_hash}\tfile.txt"
        tree_hash = db.mktree(tree_descriptor)
        
        # Verify tree content using git command
        ls_tree_output = subprocess.check_output(
            ["git", "ls-tree", tree_hash], cwd=db.root
        ).decode()
        assert blob_hash in ls_tree_output
        assert "file.txt" in ls_tree_output
        
        # 3. Create a commit
        commit_message = "feat: Initial commit via commit_tree\n\nThis is the body."
        commit_hash = db.commit_tree(tree_hash, parent_hashes=None, message=commit_message)
        
        # Verify commit content
        commit_content = subprocess.check_output(
            ["git", "cat-file", "-p", commit_hash], cwd=db.root
        ).decode()
        assert f"tree {tree_hash}" in commit_content
        assert "feat: Initial commit" in commit_content
        assert "This is the body" in commit_content

    def test_is_ancestor(self, git_repo, db, caplog):
        """测试血统检测，并验证无错误日志"""
        import logging
        caplog.set_level(logging.INFO)

        # Create C1
        (git_repo / "a").touch()
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "C1"], cwd=git_repo, check=True)
        c1 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=git_repo).decode().strip()
        
        # Create C2
        (git_repo / "b").touch()
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "C2"], cwd=git_repo, check=True)
        c2 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=git_repo).decode().strip()
        
        # 验证逻辑
        assert db.is_ancestor(c1, c2) is True
        assert db.is_ancestor(c2, c1) is False
        
        # 验证日志清洁度
        assert "Git plumbing error" not in caplog.text    

    def test_checkout_tree(self, git_repo: Path, db: GitDB):
            """Test the low-level hard reset functionality of checkout_tree."""
            # 1. Create State A
            (git_repo / "file1.txt").write_text("version 1", "utf-8")
            (git_repo / "common.txt").write_text("shared", "utf-8")
            hash_a = db.get_tree_hash()
            
            # Create a file inside .quipu to ensure it's not deleted
            quipu_dir = git_repo / ".quipu"
            quipu_dir.mkdir(exist_ok=True)
            (quipu_dir / "preserve.me").touch()

            # 2. Create State B
            (git_repo / "file1.txt").write_text("version 2", "utf-8")
            (git_repo / "file2.txt").write_text("new file", "utf-8")
            
            # 3. Checkout to State A
            db.checkout_tree(hash_a)
            
            # 4. Assertions
            assert (git_repo / "file1.txt").read_text("utf-8") == "version 1"
            assert (git_repo / "common.txt").exists()
            assert not (git_repo / "file2.txt").exists(), "file2.txt should have been cleaned"
            assert (quipu_dir / "preserve.me").exists(), ".quipu directory should be preserved"

    def test_get_diff_name_status(self, git_repo: Path, db: GitDB):
        """Test the file status diffing functionality."""
        # State A
        (git_repo / "modified.txt").write_text("v1", "utf-8")
        (git_repo / "deleted.txt").write_text("delete me", "utf-8")
        hash_a = db.get_tree_hash()

        # State B
        (git_repo / "modified.txt").write_text("v2", "utf-8")
        (git_repo / "deleted.txt").unlink()
        (git_repo / "added.txt").write_text("new file", "utf-8")
        hash_b = db.get_tree_hash()

        changes = db.get_diff_name_status(hash_a, hash_b)
        
        # Convert to a dictionary for easier assertion
        changes_dict = {path: status for status, path in changes}

        assert "M" == changes_dict.get("modified.txt")
        assert "A" == changes_dict.get("added.txt")
        assert "D" == changes_dict.get("deleted.txt")
        assert len(changes) == 3
    def test_log_ref_basic(self, git_repo, db):
        """测试 log_ref 能正确解析 Git 日志格式"""
        # Create 3 commits
        for i in range(3):
            (git_repo / f"f{i}").touch()
            subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
            subprocess.run(["git", "commit", "-m", f"commit {i}\n\nBody {i}"], cwd=git_repo, check=True)
        
        logs = db.log_ref("HEAD")
        assert len(logs) == 3
        assert logs[0]["body"].strip() == "commit 2\n\nBody 2"
        assert logs[2]["body"].strip() == "commit 0\n\nBody 0"
        assert "hash" in logs[0]
        assert "tree" in logs[0]
        assert "timestamp" in logs[0]

    def test_log_ref_non_existent(self, db):
        """测试读取不存在的引用返回空列表而不是报错"""
        logs = db.log_ref("refs/heads/non-existent")
        assert logs == []

    def test_cat_file_types(self, git_repo, db):
        """测试 cat_file 处理不同类型对象的能力"""
        # 1. Prepare data: create file, add, and commit
        (git_repo / "test_file").write_text("file content", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "test commit"], cwd=git_repo, check=True)
        
        # 2. Get hashes using git command for verification source
        head_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=git_repo).decode().strip()
        tree_hash = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=git_repo).decode().strip()
        # Get blob hash via ls-tree
        ls_out = subprocess.check_output(["git", "ls-tree", "HEAD", "test_file"], cwd=git_repo).decode()
        blob_hash = ls_out.split()[2]

        # 3. Verify Blob reading
        read_blob = db.cat_file(blob_hash, "blob")
        assert read_blob == b"file content"
        
        # 4. Verify Commit reading
        read_commit = db.cat_file(head_hash, "commit")
        assert b"tree " in read_commit
        assert b"test commit" in read_commit
        
        # 5. Verify Tree reading
        read_tree = db.cat_file(tree_hash, "tree")
        # cat-file -p tree_hash output format: "100644 blob <hash>\ttest_file"
        assert b"test_file" in read_tree
        assert blob_hash.encode() in read_tree

    def test_batch_cat_file(self, git_repo, db):
        """测试 batch_cat_file 的批量读取能力"""
        # 1. Prepare objects
        h1 = db.hash_object(b"obj1")
        h2 = db.hash_object(b"obj2")
        h3_missing = "a" * 40 # non-existent

        # 2. Batch fetch
        results = db.batch_cat_file([h1, h2, h3_missing, h1]) # Duplicate h1

        # 3. Verify
        assert len(results) == 2
        assert results[h1] == b"obj1"
        assert results[h2] == b"obj2"
        assert h3_missing not in results
~~~~~