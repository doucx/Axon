# 📸 Snapshot Capture

### 💬 备注:
ruff

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/quipu-cli/src/quipu/cli/logger_config.py  | 13 ++++----
 packages/quipu-cli/src/quipu/cli/main.py           |  4 ++-
 packages/quipu-cli/src/quipu/cli/tui.py            |  4 ++-
 packages/quipu-interfaces/src/quipu/core/models.py |  2 +-
 tests/cli/test_tui_logic.py                        |  3 +-
 tests/cli/test_tui_reachability.py                 |  3 +-
 tests/cli/test_view_model.py                       |  8 +++--
 tests/engine/sqlite/test_reader.py                 | 38 +++++++++++-----------
 tests/helpers.py                                   | 26 +++++++--------
 tests/integration/test_cli_workflow.py             |  6 ++--
 10 files changed, 56 insertions(+), 51 deletions(-)
```