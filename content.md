# test: 为 GitObjectHistoryWriter 和 GitDB 增强功能添加测试

## 用户需求
分析为新实现的 `GitObjectHistoryWriter` 模块创建测试的必要性，并在确定需要后，编写相应的测试用例。

## 评论
这是确保新存储层稳定性的关键步骤。新模块包含了复杂的业务逻辑（摘要生成）和对底层 `GitDB` 的精密编排，这些都必须经过严格验证。通过编写测试，我们可以确保：
1.  `GitDB` 的新辅助方法 `get_diff_name_status` 能正确解析 Git 输出。
2.  `_generate_summary` 方法能为不同类型的节点和场景生成符合预期的摘要。
3.  `create_node` 的完整流程能正确地创建符合 `QDPS v1.0` 规范的 Git 对象 (Commit, Tree, Blobs) 。
4.  未来的重构不会意外破坏这一核心功能。

## 目标
1.  为 `quipu.core.git_db.GitDB` 中新增的 `get_diff_name_status` 方法添加测试用例。
2.  为 `quipu.core.git_object_storage.GitObjectHistoryWriter` 的 `_generate_summary` 方法编写全面的单元测试。
3.  为 `GitObjectHistoryWriter.create_node` 方法编写一个集成测试，验证其能正确地在 Git 仓库中创建符合规范的历史节点。

## 基本原理
我们将遵循标准的测试实践，利用 `pytest` 框架和固件 (fixtures) 来创建一个隔离的、可重复的测试环境。
*   对于 `GitDB` 的测试，我们将在一个临时的 Git 仓库中创建两种不同的状态，然后调用 `get_diff_name_status` 并断言其输出的准确性。
*   对于 `_generate_summary` 的单元测试，我们将通过 `pytest.mark.parametrize` 高效地覆盖多种输入情况，并使用 `mocker` 来模拟 `git_db` 的行为，从而将业务逻辑与底层 Git 操作解耦。
*   对于 `create_node` 的集成测试，我们将真实地调用该方法，然后使用 `subprocess` 执行 `git` 命令来检查生成的 Commit、Tree 和 Blob 对象的内容，确保它们完全符合 `QDPS v1.0` 规范。

## 标签
#comp/engine #comp/tests #concept/history #scope/dx

---

## Script

### Acts 1: 为 `GitDB.get_diff_name_status` 添加测试

我们将增强 `tests/test_git_db.py` 文件，为新增的 `get_diff_name_status` 方法添加一个测试用例，验证其能否正确解析文件变更状态。

~~~~~act
replace
~~~~~
~~~~~path
tests/test_git_db.py
~~~~~
~~~~~python
        assert (quipu_dir / "preserve.me").exists(), ".quipu directory should be preserved"
~~~~~
~~~~~python
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
~~~~~

### Acts 2: 创建新的测试文件 `test_storage_writer.py`

为了更好地组织代码，我们将为所有 `HistoryWriter` 的实现创建一个专门的测试文件。

~~~~~act
write_file
~~~~~
~~~~~path
tests/test_storage_writer.py
~~~~~
~~~~~python
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from quipu.core.git_db import GitDB
from quipu.core.git_object_storage import GitObjectHistoryWriter

@pytest.fixture
def git_writer_setup(tmp_path):
    """
    创建一个包含 Git 仓库、GitDB 和 GitObjectHistoryWriter 实例的测试环境。
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)
    
    git_db = GitDB(repo_path)
    writer = GitObjectHistoryWriter(git_db)
    
    return writer, git_db, repo_path

class TestGitObjectHistoryWriterUnit:
    """对 GitObjectHistoryWriter 的内部逻辑进行单元测试。"""

    @pytest.mark.parametrize(
        "node_type, content, kwargs, expected_summary",
        [
            ("plan", "# feat: Implement feature\nDetails here.", {}, "feat: Implement feature"),
            ("plan", "Just a simple plan content line.", {}, "Just a simple plan content line."),
            ("capture", "", {"message": "Initial capture"}, "Capture: No changes detected"),
            ("capture", "", {"message": "UI fix"}, "UI fix Capture: No changes detected"),
            ("capture", "", {}, "Capture: M file1.py, A file2.js ... and 1 more files"),
        ]
    )
    def test_generate_summary(self, mocker, node_type, content, kwargs, expected_summary):
        mock_git_db = MagicMock(spec=GitDB)
        mock_git_db.get_diff_name_status.return_value = [
            ("M", "path/to/file1.py"), 
            ("A", "file2.js"), 
            ("D", "old.css")
        ]
        
        if "No changes" in expected_summary:
            mock_git_db.get_diff_name_status.return_value = []

        writer = GitObjectHistoryWriter(mock_git_db)
        summary = writer._generate_summary(node_type, content, "hash_a", "hash_b", **kwargs)
        
        assert summary == expected_summary

class TestGitObjectHistoryWriterIntegration:
    """对 GitObjectHistoryWriter 与真实 Git 仓库的交互进行集成测试。"""
    
    def test_create_node_end_to_end(self, git_writer_setup):
        writer, git_db, repo_path = git_writer_setup

        # 1. 准备工作区状态
        (repo_path / "main.py").write_text("print('hello')", "utf-8")
        output_tree = git_db.get_tree_hash()
        
        # 2. 调用 create_node
        plan_content = "# feat: Initial implementation\nThis is the first version."
        node = writer.create_node(
            node_type="plan",
            input_tree="4b825dc642cb6eb9a060e54bf8d69288fbee4904", # Empty tree
            output_tree=output_tree,
            content=plan_content,
        )

        # 3. 验证 Git 状态
        # 3.1 检查引用是否更新
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "refs/quipu/history"], cwd=repo_path, text=True
        ).strip()
        assert len(commit_hash) == 40

        # 3.2 检查 Commit 内容
        commit_data = subprocess.check_output(
            ["git", "cat-file", "-p", commit_hash], cwd=repo_path, text=True
        )
        assert f"tree " in commit_data
        assert "feat: Initial implementation" in commit_data
        assert f"X-Quipu-Output-Tree: {output_tree}" in commit_data
        
        # 3.3 检查 Tree 内容
        tree_hash = commit_data.splitlines()[0].split(" ")[1]
        tree_data = subprocess.check_output(
            ["git", "ls-tree", tree_hash], cwd=repo_path, text=True
        )
        assert "metadata.json" in tree_data
        assert "content.md" in tree_data

        # 3.4 检查 Blob 内容
        meta_blob_hash = [line.split()[2] for line in tree_data.splitlines() if "metadata.json" in line][0]
        meta_content_str = subprocess.check_output(
            ["git", "cat-file", "blob", meta_blob_hash], cwd=repo_path, text=True
        )
        meta_data = json.loads(meta_content_str)
        
        assert meta_data["meta_version"] == "1.0"
        assert meta_data["type"] == "plan"
        assert meta_data["summary"] == "feat: Initial implementation"
        assert meta_data["generator"]["id"] == "manual"
~~~~~