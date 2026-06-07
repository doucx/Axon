import os

# 强制整个测试环境使用 "raw" 语言模式，使本地与 CI 的 I18N 输出完全一致
os.environ["QUIPU_LANG"] = "raw"

from quipu.test_utils.fixtures import engine_instance, git_workspace, runner

__all__ = ["runner", "git_workspace", "engine_instance"]
