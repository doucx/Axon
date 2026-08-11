# 📸 Snapshot Capture

### 💬 备注:
ruff

检测到工作区发生变更。

### 📝 变更文件摘要:
```
conftest.py                                        |  2 +-
 .../src/quipu/application/controller.py            | 12 ++++----
 .../src/quipu/application/utils.py                 |  3 +-
 .../pyquipu-cli/src/quipu/cli/commands/axon.py     |  4 +--
 .../pyquipu-cli/src/quipu/cli/commands/export.py   | 22 +++++++-------
 .../pyquipu-cli/src/quipu/cli/commands/helpers.py  | 12 ++++----
 .../pyquipu-cli/src/quipu/cli/commands/query.py    | 14 ++++-----
 .../pyquipu-cli/src/quipu/cli/commands/remote.py   | 12 ++++----
 packages/pyquipu-cli/src/quipu/cli/commands/run.py | 15 +++++-----
 .../pyquipu-cli/src/quipu/cli/commands/show.py     |  6 ++--
 packages/pyquipu-cli/src/quipu/cli/commands/ui.py  |  2 +-
 .../src/quipu/cli/commands/workspace.py            |  4 +--
 packages/pyquipu-cli/src/quipu/cli/main.py         |  5 ++--
 packages/pyquipu-cli/src/quipu/cli/tui.py          | 12 ++++----
 packages/pyquipu-cli/src/quipu/cli/ui_utils.py     |  5 ++--
 packages/pyquipu-cli/src/quipu/cli/view_model.py   | 23 +++++++--------
 .../tests/integration/test_cli_interaction.py      |  2 +-
 .../tests/integration/test_navigation_commands.py  |  4 +--
 .../tests/integration/test_query_commands.py       |  2 +-
 .../tests/integration/test_workspace_commands.py   |  2 +-
 packages/pyquipu-cli/tests/unit/test_view_model.py | 27 +++++++++--------
 packages/pyquipu-common/src/quipu/common/bus.py    |  6 ++--
 packages/pyquipu-engine/src/quipu/engine/config.py |  8 ++---
 packages/pyquipu-engine/src/quipu/engine/git_db.py | 23 +++++++--------
 .../src/quipu/engine/git_object_storage.py         | 34 +++++++++++-----------
 .../pyquipu-engine/src/quipu/engine/hydrator.py    | 24 +++++++--------
 .../pyquipu-engine/src/quipu/engine/sqlite_db.py   |  9 +++---
 .../src/quipu/engine/sqlite_storage.py             | 24 +++++++--------
 .../src/quipu/engine/state_machine.py              | 30 +++++++++----------
 .../tests/integration/sqlite/test_reader.py        |  6 ++--
 ...
 64 files changed, 321 insertions(+), 326 deletions(-)
```