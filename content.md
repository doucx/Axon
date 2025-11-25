# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.gitignore                                    |  64 ++++
 README.md                                     |  41 +++
 TODO.md                                       |  81 +++++
 acts/__init__.py                              |   1 +
 acts/basic.py                                 | 131 ++++++++
 acts/check.py                                 |  61 ++++
 acts/git.py                                   |  96 ++++++
 acts/memory.py                                |  37 +++
 acts/read.py                                  | 150 +++++++++
 acts/refactor.py                              |  74 +++++
 acts/shell.py                                 |  49 +++
 axon                                          |  18 ++
 config.py                                     |  18 ++
 core/__init__.py                              |   1 +
 core/config_manager.py                        |  76 +++++
 core/controller.py                            | 166 ++++++++++
 core/engine.py                                | 201 ++++++++++++
 core/exceptions.py                            |  11 +
 core/executor.py                              | 159 ++++++++++
 core/git_db.py                                | 161 ++++++++++
 core/history.py                               |  69 ++++
 core/models.py                                |  32 ++
 core/parser.py                                | 148 +++++++++
 core/plugin_loader.py                         |  58 ++++
 core/result.py                                |  14 +
 core/types.py                                 |  46 +++
 docs/01_introduction.md                       |  24 ++
 docs/02_getting_started.md                    |  56 ++++
 docs/03_user_guide/01_core_concepts.md        |  49 +++
 docs/03_user_guide/02_cli_reference.md        |  72 +++++
 docs/03_user_guide/03_acts_reference.md       | 101 ++++++
 docs/04_prompting_guide.md                    |  64 ++++
 docs/05_developer_guide/01_architecture.md    |  33 ++
 docs/05_developer_guide/02_adding_new_acts.md |  62 ++++
 examples/install_demo_plugins.md              | 167 ++++++++++
 logger_config.py                              |  22 ++
 main.py                                       | 437 ++++++++++++++++++++++++++
 pytest.ini                                    |   5 +
 requirements.txt                              |   4 +
 tests/__init__.py                             |   1 +
 tests/conftest.py                             |  23 ++
 tests/test_arg_strategy.py                    |  90 ++++++
 tests/test_auto_detect.py                     |  78 +++++
 tests/test_check.py                           |  50 +++
 tests/test_engine.py                          | 190 +++++++++++
 tests/test_git.py                             |  87 +++++
 tests/test_git_db.py                          | 158 ++++++++++
 tests/test_integration_v2.py                  | 243 ++++++++++++++
 tests/test_ops.py                             | 166 ++++++++++
 tests/test_plugins.py                         |  73 +++++
 tests/test_read.py                            |  89 ++++++
 tests/test_root_invariance.py                 |  82 +++++
 52 files changed, 4389 insertions(+)
```