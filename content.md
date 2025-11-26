# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
bootstrap.py                                       |  48 ++--
 dev_setup.fish                                     |   8 +-
 dev_setup.sh                                       |   2 +-
 packages/quipu-cli/src/quipu/cli/config.py         |   4 +-
 packages/quipu-cli/src/quipu/cli/controller.py     |  59 ++--
 packages/quipu-cli/src/quipu/cli/factory.py        |  10 +-
 packages/quipu-cli/src/quipu/cli/logger_config.py  |   6 +-
 packages/quipu-cli/src/quipu/cli/main.py           | 301 +++++++++++----------
 packages/quipu-cli/src/quipu/cli/tui.py            |  93 ++++---
 packages/quipu-engine/src/quipu/core/config.py     |  27 +-
 packages/quipu-engine/src/quipu/core/git_db.py     | 114 ++++----
 .../src/quipu/core/git_object_storage.py           |  98 ++++---
 .../quipu-engine/src/quipu/core/state_machine.py   |  35 +--
 .../quipu-interfaces/src/quipu/core/exceptions.py  |   5 +
 packages/quipu-interfaces/src/quipu/core/models.py |  16 +-
 packages/quipu-interfaces/src/quipu/core/result.py |   4 +-
 .../quipu-interfaces/src/quipu/core/storage.py     |   2 +-
 packages/quipu-interfaces/src/quipu/core/types.py  |   8 +-
 packages/quipu-runtime/src/quipu/acts/__init__.py  |   3 +-
 packages/quipu-runtime/src/quipu/acts/basic.py     |  51 ++--
 packages/quipu-runtime/src/quipu/acts/check.py     |  19 +-
 packages/quipu-runtime/src/quipu/acts/git.py       |  26 +-
 packages/quipu-runtime/src/quipu/acts/memory.py    |  16 +-
 packages/quipu-runtime/src/quipu/acts/read.py      |  48 ++--
 packages/quipu-runtime/src/quipu/acts/refactor.py  |  19 +-
 packages/quipu-runtime/src/quipu/acts/shell.py     |  22 +-
 packages/quipu-runtime/src/quipu/core/executor.py  |  80 +++---
 packages/quipu-runtime/src/quipu/core/parser.py    |  50 ++--
 .../quipu-runtime/src/quipu/core/plugin_loader.py  |  11 +-
 tests/conftest.py                                  |   4 +-
 tests/test_arg_strategy.py                         |  40 +--
 tests/test_auto_detect.py                          |   3 +-
 tests/test_branching.py                            |  26 +-
 tests/test_check.py                                |  23 +-
 tests/test_engine.py                               | 104 ++++---
 tests/test_git.py                                  |  33 ++-
 tests/test_git_db.py                               | 144 +++++-----
 tests/test_head_and_root.py                        |  48 ++--
 tests/test_idempotent_node.py                      |  18 +-
 tests/test_integration_v2.py                       |  75 ++---
 tests/test_isolation.py                            |  26 +-
 tests/test_navigation.py                           |  84 +++---
 tests/test_ops.py                                  |  70 ++---
 tests/test_plugins.py                              |  18 +-
 tests/test_read.py                                 |  33 +--
 tests/test_root_invariance.py                      |  26 +-
 tests/test_storage_integration.py                  |  44 +--
 tests/test_storage_reader.py                       |  88 +++---
 tests/test_storage_writer.py                       |  41 +--
 tests/test_ui_logic.py                             |  49 ++--
 tests/test_ui_reachability.py                      |  56 ++--
 ui/__init__.py                                     |   2 +-
 verify_sandbox.py                                  |  23 +-
 53 files changed, 1175 insertions(+), 1088 deletions(-)
```