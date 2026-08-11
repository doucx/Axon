我们将针对剩余的 7 个 Ruff 提示点进行二次修复：
1. **`TRY401` 修复**：`logger.exception` 会自动记录并格式化当前捕获的异常追踪栈（traceback），因此在日志字符串模板中再次拼接 `{e}` 对象是冗余的，需将其从字符串中移除。
2. **`G201` 遗漏点修正**：在 `cache.py` 和 `helpers.py` 中将残留的 `logger.error(..., exc_info=True)` 改为 `logger.exception(...)`。
3. **`F401` 清理**：移除 `tui.py` 中未再使用的 `Optional` 导入。

## [WIP] fix: 清理 TRY401、G201 及未使用的 Optional 导入

### 错误分析

1. **`TRY401`**：`logger.exception(...)` 默认开启 `exc_info=True` 并在输出追加异常文本，在日志消息中显式包含 `{e}` 属于冗余信息。
2. **`G201`**：`cache.py` (line 34) 和 `helpers.py` (line 49) 仍存在 `logger.error(..., exc_info=True)` 调用。
3. **`F401`**：`tui.py` 中的 `Optional` 在改用 `| None` 后未被引入使用，触发了 unused import 警告。

### 用户需求

彻底清理所有 Ruff 在二次扫描时报出的 7 处剩余 Warning/Error，达到干净通过的预期。

### 评论

消除 `TRY401` 和无用导入能够让代码实现干净、精炼的 Python 标准形态。

### 目标

1. 在 `controller.py`、`tui.py` 和 `state_machine.py` 中移除 `logger.exception` 消息体中的 `{e}` 变量拼接。
2. 修复 `cache.py` 与 `helpers.py` 中的 `logger.error` 为 `logger.exception`。
3. 移除 `tui.py` 中未使用的 `Optional` 导入。

### 基本原理

通过 `patch_file` 精确重构上述文件，补齐剩余 7 处静态问题点。

### 标签

#intent/fix #flow/ready #priority/high #comp/cli #comp/engine #comp/runtime #scope/dx #ai/instruct #task/domain/tooling #task/object/lint-rules #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 清理 `controller.py` 中 `logger.exception` 冗余的 `{e}` 拼接

~~~~~act
patch_file
packages/pyquipu-application/src/quipu/application/controller.py
~~~~~
~~~~~python
    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )

    except Exception as e:
        logger.exception(f"运行时错误: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
    finally:
~~~~~
~~~~~python
    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )

    except Exception as e:
        logger.exception("运行时错误")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
    finally:
~~~~~

~~~~~act
patch_file
packages/pyquipu-application/src/quipu/application/controller.py
~~~~~
~~~~~python
    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )
    except Exception as e:
        logger.exception(f"运行时错误: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
~~~~~
~~~~~python
    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )
    except Exception as e:
        logger.exception("运行时错误")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
~~~~~

#### Acts 2: 修正 `cache.py` 与 `helpers.py` 中的 `logger.error`

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/commands/cache.py
~~~~~
~~~~~python
        bus.success(L.cache.sync.success)
    except Exception as e:
        logger.error("数据同步失败", exc_info=True)
        bus.error(L.cache.sync.error, error=str(e))
        ctx.exit(1)
~~~~~
~~~~~python
        bus.success(L.cache.sync.success)
    except Exception as e:
        logger.exception("数据同步失败")
        bus.error(L.cache.sync.error, error=str(e))
        ctx.exit(1)
~~~~~

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/commands/helpers.py
~~~~~
~~~~~python
        bus.success(L.navigation.success.visit, short_hash=target_hash[:7])
    except Exception as e:
        logger.error(f"导航操作失败 (目标哈希: {target_hash[:12]})", exc_info=True)
        bus.error(L.navigation.error.generic, error=str(e))
        ctx.exit(1)
~~~~~
~~~~~python
        bus.success(L.navigation.success.visit, short_hash=target_hash[:7])
    except Exception as e:
        logger.exception(f"导航操作失败 (目标哈希: {target_hash[:12]})")
        bus.error(L.navigation.error.generic, error=str(e))
        ctx.exit(1)
~~~~~

#### Acts 3: 清理 `tui.py` 中未使用的 `Optional` 导入与 TRY401 问题

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
import logging
from enum import Enum, auto
from pathlib import Path
from typing import ClassVar, Optional

from quipu.application.factory import create_engine
~~~~~
~~~~~python
import logging
from enum import Enum, auto
from pathlib import Path
from typing import ClassVar

from quipu.application.factory import create_engine
~~~~~

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
            except LookupError:
                # LookupError 捕获 RowKeyError 等
                logger.warning(f"DEBUG: Row key {row_key} not found in DataTable.")

        except Exception as e:
            logger.exception(f"DEBUG: Failed to focus current node: {e}")

    def _update_loading_preview(self):
~~~~~
~~~~~python
            except LookupError:
                # LookupError 捕获 RowKeyError 等
                logger.warning(f"DEBUG: Row key {row_key} not found in DataTable.")

        except Exception as e:
            logger.exception("DEBUG: Failed to focus current node")

    def _update_loading_preview(self):
~~~~~

#### Acts 4: 清理 `state_machine.py` 中的 TRY401 问题

~~~~~act
patch_file
packages/pyquipu-engine/src/quipu/engine/state_machine.py
~~~~~
~~~~~python
        # 如果使用 SQLite，先进行数据补水
        if self.db_manager:
            try:
                user_id = self._get_current_user_id()
                hydrator = Hydrator(self.git_db, self.db_manager)
                hydrator.sync(local_user_id=user_id)
            except Exception as e:
                logger.exception(f"❌ 自动数据补水失败: {e}")

        all_nodes = self.reader.load_all_nodes()
~~~~~
~~~~~python
        # 如果使用 SQLite，先进行数据补水
        if self.db_manager:
            try:
                user_id = self._get_current_user_id()
                hydrator = Hydrator(self.git_db, self.db_manager)
                hydrator.sync(local_user_id=user_id)
            except Exception as e:
                logger.exception("❌ 自动数据补水失败")

        all_nodes = self.reader.load_all_nodes()
~~~~~

### 下一步建议

1. 应用此计划中的指令块。
2. 重新运行 `ruff check .` 验证是否全部通过。
