这是一个非常实用的改进。通过在 `sync` 命令执行完毕后自动调用引擎的对齐逻辑，我们可以确保从远程仓库拉取的新引用（Refs）能够立即被 SQLite 后端索引，从而让用户在 TUI 或 `log` 命令中无缝看到更新后的历史，无需再手动运行 `quipu cache sync`。

## [WIP] feat(cli): 自动在 sync 操作后执行数据补水

### 用户需求
用户在执行 `quipu sync` 后，希望本地的 SQLite 缓存能自动感知并同步远程拉取的历史节点，而不需要额外手动执行缓存同步命令。

### 评论
这符合“工具应尽量减少用户心智负担”的设计原则。由于 `Engine.align()` 已经内置了补水逻辑，我们只需要在 `sync` 完成后安全地唤起引擎上下文即可。

### 目标
1. 在 `remote.py` 中引入 `engine_context`。
2. 在 `sync` 命令逻辑末尾（Git 操作成功后）添加自动补水块。
3. 确保补水过程中的异常被捕获为警告，不影响 `sync` 本身的成功反馈。

### 基本原理
`quipu` 的 `engine_context` 在初始化 `Engine` 时会默认执行 `align()`。对于配置了 SQLite 存储的项目，`align()` 会自动触发 `Hydrator.sync()`。我们将此逻辑集成到 `sync` 命令的末尾，使得远程引用的更新能够即时反映到本地数据库中。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #concept/sync #scope/ux #ai/instruct #task/domain/cli #task/object/sync-hydration #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 更新 `remote.py` 的导入逻辑

我们需要引入 `engine_context` 来操作引擎。

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/commands/remote.py
~~~~~
~~~~~python.old
from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging
~~~~~
~~~~~python.new
from ..config import DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from .helpers import engine_context
~~~~~

#### Acts 2: 在 `sync` 命令末尾植入自动补水逻辑

在完成所有 Git 同步动作后，触发一次静默的引擎对齐。

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/commands/remote.py
~~~~~
~~~~~python.old
            bus.info(L.sync.run.info.cacheHint)

        except RuntimeError as e:
~~~~~
~~~~~python.new
            # --- 自动数据补水 ---
            # 确保远程拉取的引用立即被 SQLite 索引
            bus.info(L.cache.sync.info.hydrating)
            try:
                with engine_context(work_dir):
                    pass
                bus.success(L.cache.sync.success)
            except Exception as e:
                logger.warning(f"自动数据补水失败: {e}")

        except RuntimeError as e:
~~~~~

### 下一步建议
- **功能测试**: 运行 `quipu sync` 并观察日志中是否出现了 `💧 正在执行增量数据补水...` 的提示。
- **UI 验证**: 在一个有远程更新的项目中执行 `sync`，然后直接打开 `quipu ui`，检查新节点是否已出现在列表且未置灰。
- **提交变更**: 验证无误后，可以使用 `quipu save` 将此逻辑改进记录到 Quipu 历史中。
