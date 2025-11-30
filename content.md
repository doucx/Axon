好的，我们首先修复因接口变更导致的 `InMemoryDB` 测试失败，然后创建一个专门的测试文件来验证新的 `checkout` 逻辑：既要验证它在“脏”工作区下的健壮性（不会崩溃），也要验证它在“净”工作区下的性能优化（mtime 保持不变）。

## [WIP] fix: 修复 InMemoryDB 接口并添加 checkout 行为验证测试

### 用户需求
1.  修复 `tests/helpers.py` 中的 `InMemoryDB` 类，使其 `checkout_tree` 方法的签名与 `GitDB` 保持一致，解决 `TypeError`。
2.  创建一个新的测试文件，专门验证 `git read-tree --reset -u` 策略的两个核心特性：
    *   **健壮性**: 在索引或工作区包含未提交变更（脏状态）时，能够强制重置并成功切换。
    *   **性能**: 对于未发生变更的文件，切换过程中不更新其修改时间 (mtime)，证明 I/O 被跳过。

### 目标
1.  修改 `tests/helpers.py`，更新 `InMemoryDB.checkout_tree` 的参数列表。
2.  新建 `tests/engine/test_checkout_behavior.py`，包含 `test_checkout_resets_dirty_index` 和 `test_checkout_optimization_mtime` 两个测试用例。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/storage #task/object/checkout-performance #task/action/test #task/state/begin

---

### Script

#### Acts 1: 修复 `InMemoryDB` 接口兼容性

我们将 `InMemoryDB` 的 `checkout_tree` 方法签名更新为接受 `new_tree_hash` 和 `old_tree_hash`，以匹配 `Engine` 的调用方式。

~~~~~act
patch_file
tests/helpers.py
~~~~~
~~~~~python
    def get_tree_hash(self) -> str:
        """对当前 VFS 内容进行确定性哈希。"""
        if not self.vfs.files:
            return EMPTY_TREE_HASH

        sorted_files = sorted(self.vfs.files.items())
        hasher = hashlib.sha1()
        for path, content in sorted_files:
            hasher.update(path.encode("utf-8"))
            hasher.update(content.encode("utf-8"))

        tree_hash = hasher.hexdigest()
        if tree_hash not in self.snapshots:
            self.snapshots[tree_hash] = self.vfs.copy()
        return tree_hash

    def checkout_tree(self, tree_hash: str):
        if tree_hash not in self.snapshots:
            raise FileNotFoundError(f"In-memory snapshot not found for hash: {tree_hash}")
        self.vfs = self.snapshots[tree_hash].copy()

    def get_diff_name_status(self, old_tree: str, new_tree: str) -> List[Tuple[str, str]]:
~~~~~
~~~~~python
    def get_tree_hash(self) -> str:
        """对当前 VFS 内容进行确定性哈希。"""
        if not self.vfs.files:
            return EMPTY_TREE_HASH

        sorted_files = sorted(self.vfs.files.items())
        hasher = hashlib.sha1()
        for path, content in sorted_files:
            hasher.update(path.encode("utf-8"))
            hasher.update(content.encode("utf-8"))

        tree_hash = hasher.hexdigest()
        if tree_hash not in self.snapshots:
            self.snapshots[tree_hash] = self.vfs.copy()
        return tree_hash

    def checkout_tree(self, new_tree_hash: str, old_tree_hash: Optional[str] = None):
        # InMemoryDB 总是执行“瞬间切换”，不需要模拟 diff 优化逻辑
        tree_hash = new_tree_hash
        if tree_hash not in self.snapshots:
            raise FileNotFoundError(f"In-memory snapshot not found for hash: {tree_hash}")
        self.vfs = self.snapshots[tree_hash].copy()

    def get_diff_name_status(self, old_tree: str, new_tree: str) -> List[Tuple[str, str]]:
~~~~~

#### Acts 2: 创建 checkout 行为验证测试

这个新测试文件将使用真实的 `GitDB` 环境来验证底层的 `checkout_tree` 逻辑。

~~~~~act
write_file
tests/engine/test_checkout_behavior.py
~~~~~
~~~~~python
import os
import subprocess
import time
from pathlib import Path

import pytest
from pyquipu.engine.git_db import GitDB


@pytest.fixture
def git_env(tmp_path: Path):
    """Setup a real Git environment for testing plumbing commands."""
    repo = tmp_path / "checkout_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    # Config git user
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo, check=True)
    return repo, GitDB(repo)


class TestCheckoutBehavior:
    def test_checkout_resets_dirty_index(self, git_env):
        """
        验证：当索引/工作区不干净（有未提交的 add）时，checkout_tree 能强制重置并成功。
        这是为了修复之前遇到的 'Entry not uptodate' 崩溃问题。
        """
        repo, db = git_env

        # 1. 创建状态 A
        (repo / "f.txt").write_text("v1")
        hash_a = db.get_tree_hash()
        
        # 此时需要将 A 的状态提交到 Git 对象库，否则后续 checkout 找不到 tree
        # 我们可以借用 commit_tree 来固化它，虽然这里不依赖 commit，但得有 tree 对象
        # get_tree_hash 内部其实已经 write-tree 了，所以 tree 对象存在。
        
        # 为了让 checkout 有意义，我们先手动让工作区处于状态 A
        # (其实 get_tree_hash 并没有修改工作区，所以现在工作区就是 v1)

        # 2. 创建状态 B
        (repo / "f.txt").write_text("v2")
        hash_b = db.get_tree_hash()

        # 3. 回到状态 A，准备制造麻烦
        db.checkout_tree(hash_a)
        assert (repo / "f.txt").read_text() == "v1"

        # 4. 制造脏索引：修改文件并添加到暂存区
        (repo / "f.txt").write_text("dirty_v3")
        subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)

        # 此时索引中的 f.txt 是 "dirty_v3"，与 hash_a 的 "v1" 不一致。
        # 旧的 read-tree -m 会在这里崩溃。

        # 5. 尝试强制切换到状态 B
        # 这里的 old_tree_hash 参数对于新的实现其实是可选的，但为了模拟 Engine 的调用我们传进去
        db.checkout_tree(new_tree_hash=hash_b, old_tree_hash=hash_a)

        # 6. 验证
        # 操作应该成功（不抛异常），且文件内容应为 v2
        assert (repo / "f.txt").read_text() == "v2"
        
        # 验证索引也干净了（除了可能被 checkout 更新过）
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).decode()
        # 应该是干净的，或者有 untracked 文件（如果有的话），但这里 f.txt 是被追踪的
        assert "f.txt" not in status

    def test_checkout_optimization_mtime(self, git_env):
        """
        验证：对于未发生变更的文件，checkout_tree 不会更新其 mtime。
        这证明了 read-tree -u 的 diff 优化生效了。
        """
        repo, db = git_env

        # 1. 创建状态 A: 包含一个不变文件和一个变动文件
        common_file = repo / "common.txt"
        common_file.write_text("I am constant")
        
        changing_file = repo / "change.txt"
        changing_file.write_text("v1")

        hash_a = db.get_tree_hash()

        # 2. 创建状态 B: common 不变，change 变
        changing_file.write_text("v2")
        hash_b = db.get_tree_hash()

        # 3. 切换回 A
        db.checkout_tree(hash_a)
        
        # 记录 common.txt 的 mtime
        # 为了防止文件系统时间分辨率问题（有些是秒级），我们强制 sleep 一下
        time.sleep(1.1) 
        mtime_before = common_file.stat().st_mtime

        # 4. 切换到 B
        # 理论上 common.txt 的 blob hash 没变，git 应该跳过它
        db.checkout_tree(new_tree_hash=hash_b, old_tree_hash=hash_a)

        # 5. 验证
        mtime_after = common_file.stat().st_mtime
        
        assert mtime_after == mtime_before, \
            "Unchanged file was touched! Optimization failed."
        
        assert changing_file.read_text() == "v2", "Changed file was not updated."

~~~~~

### 下一步建议
运行测试，确保修复有效且未引入回归。如果一切顺利，我们就可以确信这次性能优化是安全着陆了。
