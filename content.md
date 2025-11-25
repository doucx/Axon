# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
acts/basic.py                                          |  2 +-
 acts/check.py                                          |  2 +-
 acts/git.py                                            |  4 ++--
 acts/memory.py                                         |  2 +-
 acts/read.py                                           |  4 ++--
 acts/refactor.py                                       |  2 +-
 acts/shell.py                                          |  2 +-
 packages/quipu-cli/src/quipu/cli/controller.py         | 14 +++++++-------
 packages/quipu-cli/src/quipu/cli/logger_config.py      |  2 +-
 packages/quipu-cli/src/quipu/cli/main.py               | 18 +++++++++---------
 packages/quipu-engine/src/quipu/core/git_db.py         |  2 +-
 packages/quipu-engine/src/quipu/core/history.py        |  2 +-
 packages/quipu-engine/src/quipu/core/state_machine.py  |  6 +++---
 packages/quipu-interfaces/src/quipu/core/types.py      |  4 ++--
 packages/quipu-runtime/src/quipu/core/executor.py      |  4 ++--
 packages/quipu-runtime/src/quipu/core/parser.py        |  2 +-
 packages/quipu-runtime/src/quipu/core/plugin_loader.py |  2 +-
 tests/conftest.py                                      |  2 +-
 tests/test_arg_strategy.py                             |  2 +-
 tests/test_auto_detect.py                              |  2 +-
 tests/test_check.py                                    |  5 +++--
 tests/test_engine.py                                   |  6 +++---
 tests/test_git.py                                      |  2 +-
 tests/test_git_db.py                                   |  2 +-
 tests/test_graph_loader.py                             |  2 +-
 tests/test_head_and_root.py                            |  4 ++--
 tests/test_idempotent_node.py                          |  4 ++--
 tests/test_integration_v2.py                           |  6 +++---
 tests/test_ops.py                                      |  6 +++---
 tests/test_plugins.py                                  |  6 +++---
 tests/test_read.py                                     |  4 ++--
 tests/test_root_invariance.py                          |  2 +-
 tests/test_ui_logic.py                                 |  2 +-
 33 files changed, 66 insertions(+), 65 deletions(-)
```