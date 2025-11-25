# feat: 增强 GitDB 以支持底层对象操作

## 用户需求
根据 `Quipu 存储层改造实施计划 (TODO).md` 的规划，我们需要执行阶段二的第一步 (2.1) ，即增强 `GitDB` 模块，使其具备直接操作 Git 底层对象的能力。这是后续实现 `GitObjectHistoryWriter` 的前置条件，也是整个存储层升级的核心基础。

## 评论
这是一个关键的重构步骤。通过将 Git 的底层命令 (`hash-object`, `mktree`, `commit-tree`) 封装到 `GitDB` 中，我们为上层模块提供了一个清晰、稳定的接口，使其能够以编程方式构建完整的 Git 历史链，而无需关心 `subprocess` 的实现细节。

## 目标
1.  在 `quipu.core.git_db.GitDB` 中实现 `hash_object`, `mktree` 方法。
2.  将现有的 `create_anchor_commit` 方法重构为功能更强大、接口更清晰的 `commit_tree` 方法。
3.  更新 `state_machine.py` 中对该方法的调用。
4.  为所有新添加和修改的方法编写对应的单元测试，确保其功能正确无误。

## 基本原理
本次修改遵循“职责分离”原则，将所有与 Git 底层对象交互的逻辑收敛到 `GitDB` 模块中。
*   `hash_object` 方法将用于创建 Git Blobs (文件内容)。
*   `mktree` 方法将用于创建 Git Trees (目录结构)。
*   `commit_tree` 方法将用于将一个 Tree 链接到历史链中，形成一个 Commit。

这些方法共同构成了创建符合 `QDPS v1.0` 规范的历史节点的原子操作。通过重构 `_run` 辅助函数以接受标准输入，我们可以更优雅地向 Git 传递复杂数据 (如多行 commit message 或 tree descriptor) 。

## 标签
#comp/engine #concept/state #scope/api #refactor

---

## Script

### Acts 1: 增强 GitDB 模块并重构 commit 方法

首先，我们将修改 `git_db.py` 文件，添加所需的新方法，并对现有方法进行重构，使其更符合底层命令的语义。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict
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

    def _run(self, args: list[str], env: Optional[Dict] = None, check: bool = True, log_error: bool = True) -> subprocess.CompletedProcess:
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
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            if log_error:
                logger.error(f"Git plumbing error: {e.stderr}")
            raise RuntimeError(f"Git command failed: {' '.join(args)}\n{e.stderr}") from e

    @contextmanager
    def shadow_index(self):
~~~~~
~~~~~python
import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, List
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
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
            # 2. 将索引写入对象库，返回 Tree Hash
            result = self._run(["write-tree"], env=env)
            return result.stdout.strip()

    def create_anchor_commit(self, tree_hash: str, message: str, parent_commits: list[str] = None) -> str:
        """
        创建一个 Commit Object 指向特定的 Tree Hash。
        这是 Axon 历史链的物理载体。
        """
        cmd = ["commit-tree", tree_hash, "-m", message]
        
        if parent_commits:
            for p in parent_commits:
                cmd.extend(["-p", p])
                
        result = self._run(cmd)
        return result.stdout.strip()

    def update_ref(self, ref_name: str, commit_hash: str):
        """
        更新引用 (如 refs/quipu/history)。
~~~~~
~~~~~python
            # 2. 将索引写入对象库，返回 Tree Hash
            result = self._run(["write-tree"], env=env)
            return result.stdout.strip()

    def hash_object(self, content_bytes: bytes, object_type: str = "blob") -> str:
        """
        将内容写入 Git 对象数据库并返回对象哈希。
        """
        try:
            result = subprocess.run(
                ["git", "hash-object", "-w", f"-t={object_type}", "--stdin"],
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
~~~~~

### Acts 2: 更新 StateMachine 对 commit 方法的调用

现在，我们需要更新 `state_machine.py`，将其中对 `create_anchor_commit` 的调用替换为新的 `commit_tree` 方法。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~
~~~~~python
        res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
        if res.returncode == 0:
            last_commit_hash = res.stdout.strip()
        commit_msg = f"Axon Save: {message}" if message else f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else []
        new_commit_hash = self.git_db.create_anchor_commit(current_hash, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)

        self.history_graph[current_hash] = new_node
        self.current_node = new_node
~~~~~
~~~~~python
        res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
        if res.returncode == 0:
            last_commit_hash = res.stdout.strip()
        commit_msg = f"Axon Save: {message}" if message else f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else None
        new_commit_hash = self.git_db.commit_tree(current_hash, parent_hashes=parents, message=commit_msg)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)

        self.history_graph[current_hash] = new_node
        self.current_node = new_node
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~
~~~~~python
        try:
            res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
            if res.returncode == 0:
                parent_commit = res.stdout.strip()
        except Exception: pass
        commit_msg = f"Axon Plan: {output_tree[:7]}"
        parents = [parent_commit] if parent_commit else []
        new_commit_hash = self.git_db.create_anchor_commit(output_tree, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)

        self.history_graph[output_tree] = new_node
        self.current_node = new_node
~~~~~
~~~~~python
        try:
            res = self.git_db._run(["rev-parse", "refs/quipu/history"], check=False)
            if res.returncode == 0:
                parent_commit = res.stdout.strip()
        except Exception: pass
        commit_msg = f"Axon Plan: {output_tree[:7]}"
        parents = [parent_commit] if parent_commit else None
        new_commit_hash = self.git_db.commit_tree(output_tree, parent_hashes=parents, message=commit_msg)
        self.git_db.update_ref("refs/quipu/history", new_commit_hash)

        self.history_graph[output_tree] = new_node
        self.current_node = new_node
~~~~~

### Acts 3: 扩充单元测试

最后，为了验证新方法的正确性，我们在 `test_git_db.py` 中添加新的测试用例。

~~~~~act
replace
~~~~~
~~~~~path
tests/test_git_db.py
~~~~~
~~~~~python
        assert commit_tree == tree_hash

    def test_is_ancestor(self, git_repo, db, caplog):
        """测试血统检测，并验证无错误日志"""
        import logging
~~~~~
~~~~~python
        assert commit_tree == tree_hash

    def test_hash_object(self, db):
        """测试 hash_object 能否正确创建 blob 并返回 hash。"""
        content = b"hello quipu blob"
        expected_hash = "25932e65e33320875635397eac352a926a798889"
        
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
~~~~~