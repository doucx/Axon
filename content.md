# test: 为 SQLiteHistoryReader 添加单元测试

## 用户需求
在实现了 `SQLiteHistoryReader` 之后，现有的测试套件虽然能够通过，但对该类的直接覆盖率（71%）不足。需要补充专门的单元测试来验证其功能的正确性和健壮性，特别是图谱构建和通读缓存机制。

## 评论
这是一个良好的开发实践。为核心数据读取逻辑添加独立的单元测试，可以确保其在各种边缘情况下的行为符合预期，并防止未来的重构破坏其功能。这将使系统更加可靠。

## 目标
1.  创建一个新的测试文件 `tests/test_sqlite_reader.py`。
2.  在该文件中，为 `SQLiteHistoryReader` 的 `load_all_nodes` 方法编写测试，覆盖线性历史和分叉历史的场景。
3.  为 `get_node_content` 方法编写一个关键测试，验证“通读缓存”策略是否成功执行，包括从未缓存状态到已缓存状态的转换。

## 基本原理
测试将使用一个预设的 `pytest` 夹具 (fixture)，该夹具会创建一个临时的 Git 仓库和一个空的 SQLite 数据库。

1.  **数据准备**: 我们将使用 `GitObjectHistoryWriter` 和 `Hydrator` 向 Git 和数据库中写入测试数据，模拟一个真实的使用场景。
2.  **`load_all_nodes` 测试**: 调用读取器的加载方法，然后断言返回的节点列表在数量、父子关系和内容上是否与预期一致。
3.  **`get_node_content` 测试**:
    *   首先，我们将创建一个“冷数据”节点（通过补水机制，使其 `plan_md_cache` 为 `NULL`）。
    *   然后，调用 `get_node_content` 方法。
    *   断言返回的内容是正确的。
    *   最关键的一步是：**直接连接到 SQLite 数据库，查询该节点的 `plan_md_cache` 字段，断言它已经被成功回填**。

## 标签
#intent/tooling #flow/ready #priority/high
#comp/engine #comp/tests
#concept/history #concept/state
#scope/core #scope/dx
#ai/instruct
#task/domain/storage
#task/object/sqlite-backend
#task/action/integration
#task/state/continue
#task/status/active

---

## Script

### Acts 1: 创建 `SQLiteHistoryReader` 的测试文件

我们将创建 `tests/test_sqlite_reader.py` 文件，并填充必要的测试用例。

~~~~~act
write_file tests/test_sqlite_reader.py
~~~~~
~~~~~python
import pytest
import subprocess
from pathlib import Path

from quipu.core.git_db import GitDB
from quipu.core.sqlite_db import DatabaseManager
from quipu.core.hydrator import Hydrator
from quipu.core.git_object_storage import GitObjectHistoryWriter
from quipu.core.sqlite_storage import SQLiteHistoryReader


@pytest.fixture
def sqlite_reader_setup(tmp_path: Path):
    """
    创建一个包含 Git 仓库、DB 管理器、Writer 和 Reader 的测试环境。
    """
    repo_path = tmp_path / "sql_read_repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@quipu.dev"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Quipu Test"], cwd=repo_path, check=True)

    git_db = GitDB(repo_path)
    db_manager = DatabaseManager(repo_path)
    db_manager.init_schema()
    
    # Git-only writer to create commits
    git_writer = GitObjectHistoryWriter(git_db)
    # The reader we want to test
    reader = SQLiteHistoryReader(db_manager, git_db)
    # Hydrator to populate the DB from Git commits
    hydrator = Hydrator(git_db, db_manager)

    return reader, git_writer, hydrator, db_manager, repo_path, git_db


class TestSQLiteHistoryReader:
    def test_load_linear_history_from_db(self, sqlite_reader_setup):
        """测试从 DB 加载一个简单的线性历史。"""
        reader, git_writer, hydrator, _, repo, git_db = sqlite_reader_setup

        # 1. 在 Git 中创建两个节点
        (repo / "a.txt").touch()
        hash_a = git_db.get_tree_hash()
        node_a_git = git_writer.create_node("plan", "genesis", hash_a, "Content A")
        
        (repo / "b.txt").touch()
        hash_b = git_db.get_tree_hash()
        node_b_git = git_writer.create_node("plan", hash_a, hash_b, "Content B")

        # 2. 补水到数据库
        hydrator.sync()
        
        # 3. 使用 SQLite Reader 读取
        nodes = reader.load_all_nodes()
        
        # 4. 验证
        assert len(nodes) == 2
        nodes_by_summary = {n.summary: n for n in nodes}
        node_a = nodes_by_summary["Content A"]
        node_b = nodes_by_summary["Content B"]
        
        assert node_b.parent == node_a
        assert node_a.children == [node_b]
        assert node_b.input_tree == node_a.output_tree

    def test_read_through_cache(self, sqlite_reader_setup):
        """测试通读缓存是否能正确工作（从未缓存到已缓存）。"""
        reader, git_writer, hydrator, db_manager, repo, git_db = sqlite_reader_setup

        # 1. 在 Git 中创建节点
        (repo / "c.txt").touch()
        hash_c = git_db.get_tree_hash()
        node_c_git = git_writer.create_node("plan", "genesis", hash_c, "Cache Test Content")
        commit_hash_c = node_c_git.filename.name

        # 2. 补水 (这将创建一个 plan_md_cache 为 NULL 的记录)
        hydrator.sync()

        # 3. 验证初始状态：缓存为 NULL
        conn = db_manager._get_conn()
        cursor = conn.execute("SELECT plan_md_cache FROM nodes WHERE commit_hash = ?", (commit_hash_c,))
        row = cursor.fetchone()
        assert row["plan_md_cache"] is None, "Cache should be NULL for cold data."

        # 4. 使用 Reader 加载节点并触发 get_node_content
        nodes = reader.load_all_nodes()
        node_c = [n for n in nodes if n.filename.name == commit_hash_c][0]
        
        # 首次读取前，内存中的 content 应该是空的
        assert node_c.content == ""
        
        # 触发读取
        content = reader.get_node_content(node_c)
        assert content == "Cache Test Content"
        
        # 5. 再次验证数据库：缓存应该已被回填
        cursor_after = conn.execute("SELECT plan_md_cache FROM nodes WHERE commit_hash = ?", (commit_hash_c,))
        row_after = cursor_after.fetchone()
        assert row_after["plan_md_cache"] == "Cache Test Content", "Cache was not written back to DB."
~~~~~

## 附表：测试覆盖率分析

==================================================================== tests coverage ====================================================================
___________________________________________________ coverage: platform linux, python 3.13.5-final-0 ____________________________________________________

Name                                                         Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------------------
packages/quipu-cli/src/quipu/cli/config.py                      19      4    79%   21-26
packages/quipu-cli/src/quipu/cli/controller.py                  88     19    78%   63-80, 110, 133, 166-168
packages/quipu-cli/src/quipu/cli/factory.py                     37      6    84%   15-18, 43, 54
packages/quipu-cli/src/quipu/cli/logger_config.py               12      4    67%   15-20
packages/quipu-cli/src/quipu/cli/main.py                       434    234    46%   36-54, 60-65, 74-76, 95-138, 180-182, 202-203, 235-272, 296-328, 355-358, 382-385, 400-416, 428-450, 461-479, 490-508, 531-533, 553-555, 575-576, 629-630, 639-640, 642-643, 645-647, 668, 686-694, 712-734, 738
packages/quipu-cli/src/quipu/cli/plugin_manager.py              26      6    77%   27, 40-45
packages/quipu-cli/src/quipu/cli/tui.py                        161    102    37%   116-126, 129, 134, 137, 140-141, 145-166, 169-170, 174-176, 181-192, 195-248, 254-266, 271-277, 280-291
packages/quipu-cli/src/quipu/cli/utils.py                       13      2    85%   15-16
packages/quipu-engine/src/quipu/core/config.py                  42      9    79%   39-40, 42-47, 69
packages/quipu-engine/src/quipu/core/git_db.py                 180     31    83%   21, 31, 57-60, 81-82, 113-116, 164-168, 199, 280, 290, 300-301, 306-308, 316-318, 332-333, 348
packages/quipu-engine/src/quipu/core/git_object_storage.py     182     21    88%   45, 50, 58, 86, 105-106, 121, 132-133, 164-165, 190, 201, 208, 216, 226-228, 251-252, 299
packages/quipu-engine/src/quipu/core/hydrator.py                73      8    89%   81-82, 86-87, 91-92, 111-112
packages/quipu-engine/src/quipu/core/sqlite_db.py               76     18    76%   28-30, 98-100, 108-110, 118-120, 133-135, 144-146
packages/quipu-engine/src/quipu/core/sqlite_storage.py          72     21    71%   57-65, 80-99, 179-183
packages/quipu-engine/src/quipu/core/state_machine.py          228     30    87%   16-17, 34, 53, 60-61, 84-85, 110-111, 121-122, 126-127, 131, 133, 140-141, 148-149, 160-161, 196-197, 249-251, 271-273
packages/quipu-interfaces/src/quipu/core/exceptions.py           6      0   100%
packages/quipu-interfaces/src/quipu/core/models.py              25      3    88%   46-48
packages/quipu-interfaces/src/quipu/core/result.py               9      0   100%
packages/quipu-interfaces/src/quipu/core/storage.py             14      3    79%   18, 26, 57
packages/quipu-interfaces/src/quipu/core/types.py               22      0   100%
packages/quipu-runtime/src/quipu/acts/__init__.py                9      0   100%
packages/quipu-runtime/src/quipu/acts/basic.py                  98     37    62%   25-26, 30-31, 50-53, 62, 71-74, 77-78, 83-86, 97, 103, 107-108, 116-117, 121-124, 135, 146-147, 152-153, 158-161
packages/quipu-runtime/src/quipu/acts/check.py                  34      3    91%   23, 31, 51
packages/quipu-runtime/src/quipu/acts/git.py                    60     16    73%   20-23, 36-43, 65, 70, 81, 87-88, 91-92
packages/quipu-runtime/src/quipu/acts/memory.py                 22     14    36%   20-39
packages/quipu-runtime/src/quipu/acts/read.py                  115     45    61%   29-30, 46-47, 51, 63, 65-66, 75-76, 106, 110, 112, 118-121, 129-162
packages/quipu-runtime/src/quipu/acts/refactor.py               50     40    20%   20-42, 50-77
packages/quipu-runtime/src/quipu/acts/shell.py                  26     18    31%   19-45
packages/quipu-runtime/src/quipu/core/executor.py              107     26    76%   36-39, 69-70, 73, 76, 83, 92-94, 105, 118-136, 155-156, 162-163
packages/quipu-runtime/src/quipu/core/parser.py                 63      4    94%   16, 66-67, 133
packages/quipu-runtime/src/quipu/core/plugin_loader.py          31      5    84%   18, 24-25, 31, 56
------------------------------------------------------------------------------------------
TOTAL                                                         2334    729    69%
================================================================= 128 passed in 5.53s ==================================================================


### 测试覆盖率分析

1.  **核心变更文件**:
    *   `packages/quipu-engine/src/quipu/core/sqlite_storage.py`: **71% 覆盖率**。这是本次任务的核心文件，包含了新实现的 `SQLiteHistoryReader`。71% 的覆盖率表明主要路径可能已通过集成测试覆盖，但存在未经测试的分支和边缘情况。
    *   `packages/quipu-cli/src/quipu/cli/factory.py`: **84% 覆盖率**。覆盖率较高，缺失的部分主要是错误处理分支，可以接受。

2.  **判断**:
    `sqlite_storage.py` 的覆盖率不够理想。特别是，我们没有专门的单元测试来验证 `SQLiteHistoryReader` 的以下关键逻辑：
    *   从数据库正确重建父子关系图谱的逻辑。
    *   “通读缓存” (`get_node_content`) 机制是否能在缓存未命中时正确从 Git 读取数据，并成功**回填**到数据库中。

当前的集成测试虽然能验证端到端的成功流程，但无法精确地隔离和验证 `SQLiteHistoryReader` 自身的健壮性。因此，在提交代码之前，有必要为这个新类创建专门的单元测试。

### 结论
需要创建新的测试来专门验证 `SQLiteHistoryReader`。

我将为你生成一份创建这些测试的可执行计划。

