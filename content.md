~~~~~act
replace
~~~~~
~~~~~path
main.py
~~~~~
~~~old
import typer
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

# --- 轻量级导入 (保留在顶层) ---
from logger_config import setup_logging
from config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
~~~
~~~new
# --- 性能优化: 伪造 pkg_resources 模块 ---
# Typer 在启动时会尝试导入 pkg_resources，这是一个非常缓慢的操作。
# 通过在 sys.modules 中提前插入一个空的伪模块，我们可以欺骗 Typer，
# 让它跳过这个耗时的导入过程，从而大幅提升启动速度。
# 这个技巧是安全的，因为 Axon 的核心功能不依赖 pkg_resources 提供的任何特性。
import sys
import types
if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = types.ModuleType("pkg_resources")
# --- 优化结束 ---

import typer
import logging
from pathlib import Path
from typing import Annotated, Optional

# --- 轻量级导入 (保留在顶层) ---
from logger_config import setup_logging
from config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE, PROJECT_ROOT
~~~

~~~~~act
end
~~~~~