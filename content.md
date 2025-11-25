# fix-test: Repair storage backend selection for the `run` command

## 用户需求
在修复了 `Engine` 初始化逻辑和测试辅助函数后，集成测试仍然失败。失败日志表明，`quipu run` 命令似乎总是回退到旧的文件系统存储后端，即使在全新的项目中也是如此，这与预期行为不符。我需要彻底修复这个问题，使 `run` 命令能够正确地采用新的 Git 对象存储。

## 评论
经过分析，问题的根源在于 `quipu.cli.controller.run_quipu` 函数中硬编码了旧的 `FileSystemHistoryReader/Writer`，完全绕过了在 `main.py` 中为其他命令实现的动态后端选择逻辑。这是一个架构层面的疏忽。

本次修复将把动态后端选择的逻辑直接植入 `run_quipu` 函数中，消除其硬编码依赖。虽然这会在 `controller.py` 和 `main.py` 之间造成暂时的代码重复，但这是解决当前测试失败最直接、风险最低的方法。它能确保所有与历史记录交互的命令（无论是 `run` 还是 `save`, `log` 等）都遵循一致的存储策略选择规则。

## 目标
1.  修改 `quipu.cli.controller.run_quipu` 函数，移除其对 `FileSystemHistoryReader/Writer` 的硬编码实例化。
2.  将 `main.py` 中的 `_setup_engine` 函数体内的后端检测逻辑复制到 `run_quipu` 中，使其能够根据项目状态（是否存在 Git 引用或旧的历史目录）动态选择 `GitObject` 或 `FileSystem` 存储实现。
3.  更新 `quipu.cli.controller.py` 的导入语句，以包含新逻辑所需的 `GitDB` 和 `GitObjectHistoryReader/Writer`。
4.  确保修复后，`tests/test_storage_integration.py` 中的所有测试用例都能通过。

## 基本原理
`quipu run` 命令的核心业务逻辑封装在 `run_quipu` 函数中。此前的测试失败表明，该函数创建 `Engine` 实例时，写死了使用旧的文件系统存储，导致无论项目状态如何，都无法触发新的 Git 对象存储机制。

修复方案是直接将正确的后端选择逻辑——即优先检查 `refs/quipu/history`，其次检查 `.quipu/history/` 目录，最后默认使用新格式——替换掉 `run_quipu` 函数中错误的、硬编码的部分。这样，当 `quipu run` 在一个新项目上执行时，它将正确地选择 `GitObjectHistoryWriter`，该 `Writer` 会创建 `refs/quipu/history` 引用，从而使后续的测试断言能够成功。对于包含旧历史的项目，它依然能够正确回退到 `FileSystemHistoryWriter`，保证了向后兼容性。

## 标签
#comp/cli #comp/engine #concept/history #scope/core

---

## Script

### Acts 1: 在 `run_quipu` 控制器中实现动态存储后端选择

我们将替换 `controller.py` 中 `run_quipu` 函数内部硬编码的 `Engine` 初始化部分，并添加必要的模块导入。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/controller.py
~~~~~
~~~~~python
from quipu.core.plugin_loader import load_plugins
from quipu.core.file_system_storage import FileSystemHistoryReader, FileSystemHistoryWriter

# 从配置导入，注意为了解耦，未来可能需要将 config 注入而不是直接导入
from .config import PROJECT_ROOT
~~~~~
~~~~~python
from quipu.core.plugin_loader import load_plugins
from quipu.core.file_system_storage import FileSystemHistoryReader, FileSystemHistoryWriter
from quipu.core.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.core.git_db import GitDB

# 从配置导入，注意为了解耦，未来可能需要将 config 注入而不是直接导入
from .config import PROJECT_ROOT
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/controller.py
~~~~~
~~~~~python
        # --- Phase 1: Engine Initialization & Perception ---
        # 注意：所有核心组件都必须使用规范化后的 project_root 初始化！
        history_dir = project_root / ".quipu" / "history"
        reader = FileSystemHistoryReader(history_dir)
        writer = FileSystemHistoryWriter(history_dir)
        engine = Engine(project_root, reader=reader, writer=writer)

        status = engine.align() # "CLEAN", "DIRTY", "ORPHAN"
~~~~~
~~~~~python
        # --- Phase 1: Engine Initialization & Perception ---
        # 注意：所有核心组件都必须使用规范化后的 project_root 初始化！
        git_db = GitDB(project_root)
        if git_db.has_quipu_ref():
            logger.debug("Detected Git Object storage format.")
            reader = GitObjectHistoryReader(git_db)
            writer = GitObjectHistoryWriter(git_db)
        elif (project_root / ".quipu" / "history").exists():
            logger.debug("Detected File System storage format (legacy).")
            history_dir = project_root / ".quipu" / "history"
            reader = FileSystemHistoryReader(history_dir)
            writer = FileSystemHistoryWriter(history_dir)
        else:
            logger.debug("No existing history found. Defaulting to Git Object storage format.")
            reader = GitObjectHistoryReader(git_db)
            writer = GitObjectHistoryWriter(git_db)

        engine = Engine(project_root, reader=reader, writer=writer)
        status = engine.align() # "CLEAN", "DIRTY", "ORPHAN"
~~~~~