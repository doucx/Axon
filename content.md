# 📸 Snapshot Capture

### 💬 备注:
sed -i.bak 's/Axon/Quipu/g' examples/install_demo_plugins.md tests/engine/test_git_db.py tests/engine/test_head_tracking.py tests/integration/test_workspace_invariance.py tests/integration/test_cli_workflow.py packages/quipu-cli/src/quipu/cli/main.py packages/quipu-interfaces/src/quipu/core/models.py packages/quipu-engine/src/quipu/core/state_machine.py packages/quipu-interfaces/src/quipu/core/result.py packages/quipu-engine/src/quipu/core/git_db.py

检测到工作区发生变更。

### 📝 变更文件摘要:
```
examples/install_demo_plugins.md                     | 10 +++++-----
 packages/quipu-cli/src/quipu/cli/main.py             | 20 ++++++++++----------
 packages/quipu-engine/src/quipu/core/git_db.py       |  4 ++--
 .../quipu-engine/src/quipu/core/state_machine.py     |  4 ++--
 packages/quipu-interfaces/src/quipu/core/models.py   |  2 +-
 packages/quipu-interfaces/src/quipu/core/result.py   |  2 +-
 tests/engine/test_git_db.py                          |  8 ++++----
 tests/engine/test_head_tracking.py                   |  2 +-
 tests/integration/test_cli_workflow.py               |  4 ++--
 tests/integration/test_workspace_invariance.py       |  6 +++---
 10 files changed, 31 insertions(+), 31 deletions(-)
```