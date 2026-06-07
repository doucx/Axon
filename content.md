这个错误是因为在 `remote.py` 中虽然导入了 `logging` 模块，但没有定义 `logger` 变量。根据 Quipu 的架构原则，面向用户的反馈应当优先使用 `bus`（消息总线）进行，因为它支持本地化和多端渲染。

我们将修正这个问题，并使用 `L.cache.sync.error` 来提供本地化的错误反馈。

## [WIP] fix(cli): 修正 sync 自动补水逻辑中的未定义变量错误

### 错误分析
在上一版本中，我在 `remote.py` 的异常处理块中错误地引用了未定义的 `logger` 变量（F821）。同时，为了符合项目的 UI 规范，应当使用 `bus.warning` 替代 `logger.warning`。

### 用户需求
确保 `quipu sync` 命令中的自动补水逻辑能够稳定运行，并提供正确的本地化反馈。

### 目标
1. 修正 `remote.py` 中的 `logger` 变量未定义错误。
2. 将硬编码的错误消息改为使用 `bus` 和 `L` 指针。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #concept/sync #ai/instruct #task/domain/cli #task/object/sync-hydration #task/action/fix-bug #task/state/continue

---

### Script

#### Acts 1: 修正 `remote.py` 中的反馈逻辑

我们将 `logger.warning` 替换为 `bus.warning`，并关联到 `L.cache.sync.error`。

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/commands/remote.py
~~~~~
~~~~~python.old
            try:
                with engine_context(work_dir):
                    pass
                bus.success(L.cache.sync.success)
            except Exception as e:
                logger.warning(f"自动数据补水失败: {e}")

        except RuntimeError as e:
~~~~~
~~~~~python.new
            try:
                with engine_context(work_dir):
                    pass
                bus.success(L.cache.sync.success)
            except Exception as e:
                # 使用 bus 进行本地化告警反馈
                bus.warning(L.cache.sync.error, error=str(e))

        except RuntimeError as e:
~~~~~

### 下一步建议
- **执行验证**: 在本地环境运行一次 `qs sync`（如果配置了远程），观察在补水阶段的输出是否正确。
- **Lint 检查**: 建议运行 `ruff check .` 确保没有其他的 `Undefined name` 错误。
- **提交变更**: 完成修复后，建议对 CLI 部分的改进进行一次 `quipu save`。
