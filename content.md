# refactor: 明确并统一项目根目录的发现逻辑

## 用户需求
项目中有两个功能相似但目的不同的 `find_project_root` 函数，这造成了命名上的混淆和少量的代码逻辑重复。需要对它们进行重构以提高代码的清晰度和可维护性。

## 评论
这是一个典型的“架构异味”改进。通过精确地重命名函数来反映其真实意图（一个是查找用户项目的 Git 根，另一个是查找 Quipu 开发时的源码根），我们可以消除歧义，让代码库更易于理解。这是一个高性价比的重构。

## 目标
1.  将 `quipu.cli.utils.find_project_root` 重命名为 `find_git_repository_root`，使其职责更加明确。
2.  更新所有调用该函数的地方，使用新的名称。
3.  将 `quipu.cli.config._find_project_root` 重命名为 `_find_development_monorepo_root`，以明确其仅用于开发环境的特殊目的。
4.  确保重构后所有功能正常。

## 基本原理
我们采纳了“在原位改进”的方案。此方案的核心是通过精确命名来区分两个函数的不同职责，而不是进行不必要的代码移动或创建新的共享包。这解决了最核心的“命名混淆”问题，同时保持了架构的简洁性。

*   `find_git_repository_root` 是一个**外向型**工具，用于在运行时定位用户的工作区根目录（以 `.git` 为标记）。
*   `_find_development_monorepo_root` 是一个**内向型**工具，用于在开发模式下定位 Quipu 项目自身的根目录，以便加载配置等资源。

## 标签
#intent/refine #flow/ready #priority/medium #comp/cli #concept/config #scope/dx #ai/instruct

---

## Script

### Acts 1: 重命名用户侧的根目录查找函数

此阶段将 `quipu.cli.utils.find_project_root` 重命名为 `find_git_repository_root`，并更新所有调用它的地方。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/utils.py
~~~~~
~~~~~python
def find_project_root(start_path: Path) -> Optional[Path]:
    """向上递归查找包含 .git 的目录作为项目根目录"""
~~~~~
~~~~~python
def find_git_repository_root(start_path: Path) -> Optional[Path]:
    """向上递归查找包含 .git 的目录作为项目根目录"""
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/factory.py
~~~~~
~~~~~python
from quipu.core.config import ConfigManager
from .utils import find_project_root
~~~~~
~~~~~python
from quipu.core.config import ConfigManager
from .utils import find_git_repository_root
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/factory.py
~~~~~
~~~~~python
    # 1. 尝试查找真正的项目根目录 (包含 .git 的目录)
    project_root = find_project_root(work_dir)
    if not project_root:
~~~~~
~~~~~python
    # 1. 尝试查找真正的项目根目录 (包含 .git 的目录)
    project_root = find_git_repository_root(work_dir)
    if not project_root:
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~path
from .config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
from .factory import create_engine
from .utils import find_project_root
from quipu.core.plugin_loader import load_plugins
~~~~~
~~~~~path
from .config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
from .factory import create_engine
from .utils import find_git_repository_root
from quipu.core.plugin_loader import load_plugins
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python
    # Sync 必须在 git 项目根目录执行
    sync_dir = find_project_root(work_dir) or work_dir
    config = ConfigManager(sync_dir)
~~~~~
~~~~~python
    # Sync 必须在 git 项目根目录执行
    sync_dir = find_git_repository_root(work_dir) or work_dir
    config = ConfigManager(sync_dir)
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/plugin_manager.py
~~~~~
~~~~~python
from quipu.core.executor import Executor
from quipu.core.plugin_loader import load_plugins
from .utils import find_project_root
~~~~~
~~~~~python
from quipu.core.executor import Executor
from quipu.core.plugin_loader import load_plugins
from .utils import find_git_repository_root
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/plugin_manager.py
~~~~~
~~~~~python
        # 3. Project Root (Highest priority)
        project_root_for_plugins = find_project_root(work_dir)
        if project_root_for_plugins:
~~~~~
~~~~~python
        # 3. Project Root (Highest priority)
        project_root_for_plugins = find_git_repository_root(work_dir)
        if project_root_for_plugins:
~~~~~

### Acts 2: 重命名开发环境的根目录查找函数

此阶段在 `config.py` 内部重命名私有函数 `_find_project_root` 为 `_find_development_monorepo_root`，以明确其用途。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/config.py
~~~~~
~~~~~python
def _find_project_root() -> Path:
    """
    向上递归查找项目根目录。
    依据：存在 'acts' 目录 或 顶层 'pyproject.toml'。
    """
~~~~~
~~~~~python
def _find_development_monorepo_root() -> Path:
    """
    向上递归查找 Quipu 开发时的项目根目录 (monorepo root)。
    依据：存在 'packages' 目录和顶层 'pyproject.toml'。
    """
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/config.py
~~~~~
~~~~~python
# 项目根目录（代码所在位置）
PROJECT_ROOT: Path = _find_project_root()
~~~~~
~~~~~python
# 项目根目录（代码所在位置）
PROJECT_ROOT: Path = _find_development_monorepo_root()
~~~~~
