import pytest
import subprocess
from pathlib import Path
from core.controller import run_axon

@pytest.fixture
def project_with_subdir(tmp_path):
    """
    创建一个标准的 Git 项目结构，包含一个子目录。
    root/
      .git/
      plan.md
      src/
        (empty)
    """
    # 1. 初始化项目根目录和 Git
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)

    # 2. 创建子目录和 Plan 文件
    subdir = root / "src"
    subdir.mkdir()
    
    plan_content = """
~~~act
write_file
~~~
~~~path
result.txt
~~~
~~~content
Success from subdir
~~~
"""
    (root / "plan.md").write_text(plan_content, "utf-8")
    
    return root, subdir

class TestRootInvariance:
    """
    测试 Axon 的核心特性：根目录不变性。
    无论用户从项目的哪个子目录运行命令，Axon 的行为都应该与在项目根目录运行时完全一致。
    """
    def test_run_from_subdir_maintains_root_context(self, project_with_subdir):
        """
        验证：当从子目录 (`src/`) 启动 Axon 时，
        它应该能自动发现项目根，并在根目录下正确执行操作和记录历史。
        """
        project_root, subdir = project_with_subdir
        
        # 关键测试点：我们使用子目录 `subdir` 作为 `work_dir` 来调用 run_axon，
        # 模拟 `cd src; axon run ../plan.md` 的场景。
        # plan.md 本身在根目录，其内容引用的路径 'result.txt' 也是相对于根目录的。
        
        # 注意：controller 层不负责解析 `../`，所以我们传 plan 的内容而不是路径
        plan_content = (project_root / "plan.md").read_text("utf-8")
        
        result = run_axon(
            content=plan_content,
            work_dir=subdir,  # <--- 从子目录运行
            yolo=True
        )

        # 1. 验证操作的正确性
        assert result.success is True, f"从子目录运行失败: {result.message}"
        
        # Executor 应该基于项目根来解析路径，所以 'result.txt' 应该在根目录创建
        expected_file = project_root / "result.txt"
        assert expected_file.exists(), "文件应该在项目根目录创建，而不是子目录"
        assert expected_file.read_text("utf-8") == "Success from subdir"

        # 2. 验证 Engine 状态记录的正确性
        history_dir = project_root / ".axon" / "history"
        assert history_dir.exists(), "历史目录应在项目根目录创建"
        
        history_files = list(history_dir.glob("*.md"))
        assert len(history_files) >= 1, "应至少生成一个历史节点"
        
        # 验证生成的 Plan Node 内容正确，证明 Engine 在正确的上下文中计算了 Tree Hash
        # (简单验证，更复杂的 hash 比较需要固定文件时间戳等，这里验证文件存在即可)
        assert any("plan" in f.read_text("utf-8") for f in history_files)