# fix-test 修复因存储层重构导致的系列测试失败

## 用户需求
在实现了 `QDPS v1.0` 存储架构并将其作为默认后端后，`pytest` 测试套件中出现大量失败和错误。需要修复这些测试，确保它们在新架构下能够正确运行，并同时修复测试暴露出的相关代码缺陷。

## 评论
这是存储层重构后的必要收尾工作。测试失败的主要原因是许多旧测试用例直接依赖于文件系统存储 (`.quipu/history/*.md`) 的具体实现细节，而新架构不再创建这些文件。修复这些测试不仅能恢复 CI 的健康状态，还能强制我们编写更健壮、与存储后端解耦的测试代码。

## 目标
1.  修复所有在 `pytest` 输出中报告的 `FAILED` 和 `ERROR` 状态的测试。
2.  解决测试暴露出的 `Engine` 初始化、历史文件名解析以及摘要 (Summary) 生成逻辑中的缺陷。
3.  重构依赖旧存储实现的测试夹具 (fixtures) 和断言，使其与存储后端无关。

## 基本原理
本次修复将遵循以下策略：
1.  **修复核心缺陷**: 首先修复代码中的明显缺陷，如 `.quipu` 目录未及时创建、历史文件名 `regex` 过于严格、摘要生成逻辑不健壮等问题。
2.  **重构测试夹具**: 修改 `tests/test_integration_v2.py` 中的 `populated_workspace` 夹具，使其不再直接检查文件系统，而是通过 `Engine` 和 `HistoryReader` 接口来获取历史节点信息。
3.  **更新测试断言**: 将所有直接检查 `.quipu/history` 目录或文件的断言，替换为通过 `Engine` API 验证历史状态。

## 标签
#comp/tests #comp/engine #fix #scope/dx

---

## Script

### Acts 1: 修复 Engine 初始化与历史解析缺陷

首先，修复 `Engine` 初始化时 `.quipu` 目录不存在的问题，并放宽旧历史文件名的解析规则以提高兼容性。

~~~~~act
replace packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~

~~~~~python
        self.root_dir = root_dir.resolve()
        self.quipu_dir = self.root_dir / ".quipu"
        self.history_dir = self.quipu_dir / "history"
        self.head_file = self.quipu_dir / "HEAD"

        self.nav_log_file = self.quipu_dir / "nav_log"
        self.nav_ptr_file = self.quipu_dir / "nav_ptr"

        quipu_gitignore = self.quipu_dir / ".gitignore"
        if not quipu_gitignore.exists():
~~~~~

~~~~~python
        self.root_dir = root_dir.resolve()
        self.quipu_dir = self.root_dir / ".quipu"
        self.quipu_dir.mkdir(exist_ok=True)  # 确保 .quipu 目录存在
        self.history_dir = self.quipu_dir / "history"
        self.head_file = self.quipu_dir / "HEAD"

        self.nav_log_file = self.quipu_dir / "nav_log"
        self.nav_ptr_file = self.quipu_dir / "nav_ptr"

        quipu_gitignore = self.quipu_dir / ".gitignore"
        if not quipu_gitignore.exists():
~~~~~

~~~~~act
replace packages/quipu-engine/src/quipu/core/history.py
~~~~~

~~~~~python
logger = logging.getLogger(__name__)

FILENAME_PATTERN = re.compile(
    r"([0-9a-f]{40}|_{40})_([0-9a-f]{40})_(\d{14})\.md"
)

def _parse_frontmatter(text: str) -> tuple[Dict, str]:
~~~~~

~~~~~python
logger = logging.getLogger(__name__)

# 放宽对 input_hash 的校验，以兼容损坏或非标准的历史文件名
FILENAME_PATTERN = re.compile(
    r"(.+?)_([0-9a-f]{40})_(\d{14})\.md"
)

def _parse_frontmatter(text: str) -> tuple[Dict, str]:
~~~~~

### Acts 2: 改进摘要 (Summary) 生成逻辑

统一并增强 `history.py` (旧格式) 和 `git_object_storage.py` (新格式) 中的摘要生成逻辑，使其更智能地从 `plan` 内容中提取信息。

~~~~~act
replace packages/quipu-engine/src/quipu/core/history.py
~~~~~

~~~~~python
                summary = temp_summary or "Plan executed"
            elif node_type == 'capture':
                # Prioritize user message from the body
~~~~~

~~~~~python
                summary = temp_summary
                if not summary:
                    # Fallback: find first non-empty line
                    summary = next((line.strip() for line in body_content.strip().split('\n') if line.strip()), "Plan executed")
            elif node_type == 'capture':
                # Prioritize user message from the body
~~~~~

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_object_storage.py
~~~~~

~~~~~python
            match = re.search(r"^\s*#{1,6}\s+(.*)", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            
            return "Plan executed"

        elif node_type == "capture":
            user_message = (kwargs.get("message") or "").strip()
~~~~~

~~~~~python
            match = re.search(r"^\s*#{1,6}\s+(.*)", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            
            # Fallback to the first non-empty line
            first_line = next((line.strip() for line in content.strip().splitlines() if line.strip()), "Plan executed")
            return (first_line[:75] + '...') if len(first_line) > 75 else first_line

        elif node_type == "capture":
            user_message = (kwargs.get("message") or "").strip()
~~~~~

### Acts 3: 重构核心集成测试

修改 `test_integration_v2.py` 和其他相关测试，使其不再依赖文件系统存储的具体实现。

~~~~~act
replace tests/test_integration_v2.py
~~~~~

~~~~~python
class TestController:

    def test_run_quipu_success(self, workspace):
        """测试正常执行流程"""
        plan = """
~~~act
write_file
~~~
~~~path
hello.txt
~~~
~~~content
Hello Quipu
~~~
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
        
        assert result.success is True
        assert result.exit_code == 0
        assert (workspace / "hello.txt").exists()
        
        # 验证 Engine 是否生成了 Plan 节点
        history_dir = workspace / ".quipu" / "history"
        assert history_dir.exists()
        assert len(list(history_dir.glob("*.md"))) >= 1
~~~~~

~~~~~python
class TestController:

    def test_run_quipu_success(self, workspace):
        """测试正常执行流程"""
        from quipu.cli.main import _setup_engine
        plan = """
~~~act
write_file
~~~
~~~path
hello.txt
~~~
~~~content
Hello Quipu
~~~
"""
        result = run_quipu(content=plan, work_dir=workspace, yolo=True)
        
        assert result.success is True
        assert result.exit_code == 0
        assert (workspace / "hello.txt").exists()
        
        # 验证 Engine 是否生成了 Plan 节点 (后端无关)
        engine = _setup_engine(workspace)
        nodes = engine.reader.load_all_nodes()
        assert len(nodes) >= 1
~~~~~

~~~~~act
replace tests/test_integration_v2.py
~~~~~

~~~~~python
class TestCheckoutCLI:

    @pytest.fixture
    def populated_workspace(self, workspace):
        """
        Create a workspace with two distinct, non-overlapping history nodes.
        State A contains only a.txt.
        State B contains only b.txt.
        """
        # State A: Create a.txt
        plan_a = "~~~act\nwrite_file a.txt\n~~~\n~~~content\nState A\n~~~"
        run_quipu(content=plan_a, work_dir=workspace, yolo=True)
        
        # Find the hash for State A. It's the latest one at this point.
        history_nodes_a = list(sorted((workspace / ".quipu" / "history").glob("*.md"), key=lambda p: p.stat().st_mtime))
        hash_a = history_nodes_a[-1].name.split("_")[1]

        # Manually create State B by removing a.txt and adding b.txt
        # This ensures State B is distinct from State A, not an addition.
        (workspace / "a.txt").unlink()
        plan_b = "~~~act\nwrite_file b.txt\n~~~\n~~~content\nState B\n~~~"
        run_quipu(content=plan_b, work_dir=workspace, yolo=True)

        # Find the hash for State B. It's the newest node now.
        history_nodes_b = list(sorted((workspace / ".quipu" / "history").glob("*.md"), key=lambda p: p.stat().st_mtime))
        hash_b = history_nodes_b[-1].name.split("_")[1]
        
        # The workspace is now physically in State B before the test starts.
        return workspace, hash_a, hash_b
~~~~~

~~~~~python
class TestCheckoutCLI:

    @pytest.fixture
    def populated_workspace(self, workspace):
        """
        Create a workspace with two distinct, non-overlapping history nodes.
        State A contains only a.txt.
        State B contains only b.txt.
        This fixture is backend-agnostic.
        """
        from quipu.cli.main import _setup_engine

        # State A: Create a.txt
        plan_a = "~~~act\nwrite_file a.txt\n~~~\n~~~content\nState A\n~~~"
        run_quipu(content=plan_a, work_dir=workspace, yolo=True)
        
        engine_after_a = _setup_engine(workspace)
        nodes_after_a = sorted(engine_after_a.reader.load_all_nodes(), key=lambda n: n.timestamp)
        node_a = nodes_after_a[-1]
        hash_a = node_a.output_tree

        # Manually create State B by removing a.txt and adding b.txt
        (workspace / "a.txt").unlink()
        plan_b = "~~~act\nwrite_file b.txt\n~~~\n~~~content\nState B\n~~~"
        run_quipu(content=plan_b, work_dir=workspace, yolo=True)

        engine_after_b = _setup_engine(workspace)
        nodes_after_b = sorted(engine_after_b.reader.load_all_nodes(), key=lambda n: n.timestamp)
        node_b = nodes_after_b[-1]
        hash_b = node_b.output_tree
        
        return workspace, hash_a, hash_b
~~~~~

~~~~~act
replace tests/test_idempotent_node.py
~~~~~

~~~~~python
        # 此处 Engine 的实例化仅用于验证，非测试核心
        reader = FileSystemHistoryReader(history_dir)
        writer = FileSystemHistoryWriter(history_dir)
        engine = Engine(workspace, reader=reader, writer=writer)

        nodes_1 = list(history_dir.glob("*.md"))
        assert len(nodes_1) == 1
        
        # 3. 执行一个无变更的操作 (State A -> State A)
        # 例如读取文件或运行 ls
        plan_2 = "~~~act\nread_file a.txt\n~~~"
        result = run_quipu(plan_2, workspace, yolo=True)
        
        assert result.success is True
        
        # 4. 验证是否生成了新节点
        nodes_2 = list(history_dir.glob("*.md"))
        assert len(nodes_2) == 2
        
        # 验证新节点的 input == output
        # 加载最新的节点
        latest_file = max(nodes_2, key=lambda p: p.stat().st_mtime)
        content = latest_file.read_text("utf-8")
        
        # 简单的字符串检查
        import yaml
        parts = content.split("---")
        meta = yaml.safe_load(parts[1])
        
        assert meta["input_tree"] == meta["output_tree"]
        assert meta["type"] == "plan"
~~~~~

~~~~~python
        # 使用正确的 Engine 设置来验证
        from quipu.cli.main import _setup_engine
        engine1 = _setup_engine(workspace)
        nodes1 = engine1.reader.load_all_nodes()
        assert len(nodes1) >= 1
        
        # 3. 执行一个无变更的操作 (State A -> State A)
        plan_2 = "~~~act\nread_file a.txt\n~~~"
        result = run_quipu(plan_2, workspace, yolo=True)
        
        assert result.success is True
        
        # 4. 验证是否生成了新节点
        engine2 = _setup_engine(workspace)
        nodes2 = sorted(engine2.reader.load_all_nodes(), key=lambda n: n.timestamp)
        assert len(nodes2) == len(nodes1) + 1
        
        # 验证新节点的 input == output
        latest_node = nodes2[-1]
        assert latest_node.input_tree == latest_node.output_tree
        assert latest_node.node_type == "plan"
~~~~~

~~~~~act
replace tests/test_root_invariance.py
~~~~~

~~~~~python
        # 2. 验证 Engine 状态记录的正确性
        history_dir = project_root / ".quipu" / "history"
        assert history_dir.exists(), "历史目录应在项目根目录创建"
        
        history_files = list(history_dir.glob("*.md"))
        assert len(history_files) >= 1, "应至少生成一个历史节点"
        
        # 验证生成的 Plan Node 内容正确，证明 Engine 在正确的上下文中计算了 Tree Hash
        # (简单验证，更复杂的 hash 比较需要固定文件时间戳等，这里验证文件存在即可)
        assert any("plan" in f.read_text("utf-8") for f in history_files)
~~~~~

~~~~~python
        # 2. 验证 Engine 状态记录的正确性 (后端无关)
        from quipu.cli.main import _setup_engine
        engine = _setup_engine(project_root)
        nodes = engine.reader.load_all_nodes()
        
        # 应该有一个 drift capture 节点和一个 plan 节点
        assert len(nodes) >= 2, "应至少生成捕获节点和计划节点"
        
        plan_nodes = [n for n in nodes if n.node_type == 'plan']
        assert len(plan_nodes) >= 1, "应至少有一个 plan 节点"
        assert "Success from subdir" in plan_nodes[-1].content
~~~~~