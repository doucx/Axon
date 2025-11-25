# feat-core: 实现持久化本地忽略规则以保护环境文件

## 目标
防止 `quipu checkout` 和 `quipu discard` 等命令删除用户本地的、未被版本控制的开发环境文件 (例如 `.envs/`, `.idea/`, `o.md`)，即使 `.gitignore` 文件在不同历史状态间发生变化。

## 基本原理
当前问题在于，当 `checkout` 操作还原了一个不包含特定忽略规则的旧版 `.gitignore` 文件后，`git clean` 就会删除那些之前被忽略但现在未被忽略的文件。

解决方案是利用 Git 的一个标准功能：`.git/info/exclude` 文件。这个文件中的忽略规则只对本地仓库生效，不会被提交，因此它独立于任何历史状态。它为我们提供了一个完美的“本地配置”与“项目状态”的分离层。

本计划将实现以下自动化流程：
1.  在 `.quipu/config.yml` 中引入一个新的配置项 `sync.persistent_ignores`，允许用户定义他们希望在所有历史状态下都保持忽略的文件和目录。
2.  `quipu-engine` 的 `Engine` 在初始化时，会自动读取此配置。
3.  `Engine` 会将这些规则写入到 `.git/info/exclude` 文件的一个由 Quipu 管理的特定块中。
4.  这样，当 `git clean` 运行时，它会同时参考项目当前的 `.gitignore` 和持久化的 `.git/info/exclude` 规则，从而保护用户的本地环境文件不被误删。

## 标签
#feat #core #git #config

---

## Script

### Act 1: 在 `quipu-engine` 中定义配置项与默认值

我们将向 `ConfigManager` 添加一组新的默认配置，用于定义持久化忽略规则。用户可以在他们自己的 `.quipu/config.yml` 文件中覆盖或扩展这些规则。

~~~~~act
replace packages/quipu-engine/src/quipu/core/config.py
~~~~~

~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "sync": {
        "remote_name": "origin"
    },
    "list_files": {
        "ignore_patterns": [".git", "__pycache__", ".idea", ".vscode", "node_modules", ".quipu"]
    }
}
~~~~~

~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "sync": {
        "remote_name": "origin",
        "persistent_ignores": [
            ".idea",
            ".vscode",
            ".envs",
            "__pycache__",
            "node_modules",
            "o.md"
        ]
    },
    "list_files": {
        "ignore_patterns": [".git", "__pycache__", ".idea", ".vscode", "node_modules", ".quipu"]
    }
}
~~~~~

### Act 2: 在 `Engine` 初始化时自动同步忽略规则

我们将修改 `Engine` 类，使其在初始化时自动执行将配置同步到 `.git/info/exclude` 的逻辑。这确保了在执行任何操作之前，本地环境都是受保护的。

~~~~~act
replace packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~

~~~~~python
import logging
from pathlib import Path
from typing import Dict, Optional
import yaml
from datetime import datetime

from .git_db import GitDB
from .history import load_history_graph
from quipu.core.models import QuipuNode

logger = logging.getLogger(__name__)

class Engine:
    """
    Axon 状态引擎。
    负责协调 Git 物理状态和 Axon 逻辑图谱。
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
~~~~~

~~~~~python
import logging
from pathlib import Path
from typing import Dict, Optional
import yaml
import re
from datetime import datetime

from .git_db import GitDB
from .history import load_history_graph
from .config import ConfigManager
from quipu.core.models import QuipuNode

logger = logging.getLogger(__name__)

class Engine:
    """
    Axon 状态引擎。
    负责协调 Git 物理状态和 Axon 逻辑图谱。
    """

    def _sync_persistent_ignores(self):
        """将 config.yml 中的持久化忽略规则同步到 .git/info/exclude。"""
        try:
            config = ConfigManager(self.root_dir)
            patterns = config.get("sync.persistent_ignores", [])
            if not patterns:
                return

            exclude_file = self.root_dir / ".git" / "info" / "exclude"
            exclude_file.parent.mkdir(exist_ok=True)

            header = "# --- Managed by Quipu ---"
            footer = "# --- End Managed by Quipu ---"
            
            content = ""
            if exclude_file.exists():
                content = exclude_file.read_text("utf-8")

            # 使用 re.DOTALL (s) 标志来匹配包括换行符在内的任何字符
            managed_block_pattern = re.compile(rf"{re.escape(header)}.*{re.escape(footer)}", re.DOTALL)
            
            new_block = f"{header}\n" + "\n".join(patterns) + f"\n{footer}"

            new_content, count = managed_block_pattern.subn(new_block, content)
            if count == 0:
                # 如果没有找到匹配项，则在末尾追加
                if content and not content.endswith("\n"):
                    content += "\n"
                new_content = content + "\n" + new_block + "\n"
            
            if new_content != content:
                exclude_file.write_text(new_content, "utf-8")
                logger.debug("✅ .git/info/exclude 已更新。")

        except Exception as e:
            logger.warning(f"⚠️  无法同步持久化忽略规则: {e}")

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
~~~~~

### Act 3: 在 `Engine` 构造函数中调用同步方法

现在，我们将确保在 `Engine` 实例化时调用这个新的同步方法。

~~~~~act
replace packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~

~~~~~python
        self.git_db = GitDB(self.root_dir)
        self.history_graph: Dict[str, QuipuNode] = {}
        self.current_node: Optional[QuipuNode] = None
~~~~~

~~~~~python
        self.git_db = GitDB(self.root_dir)
        self.history_graph: Dict[str, QuipuNode] = {}
        self.current_node: Optional[QuipuNode] = None

        # 自动同步本地配置，如持久化忽略规则
        self._sync_persistent_ignores()
~~~~~