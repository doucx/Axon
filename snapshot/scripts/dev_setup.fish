#!/usr/bin/env fish

# 获取项目根目录 (scripts/ 的上一级)
set SCRIPT_DIR (dirname (status --current-filename))
set ROOT_DIR (cd "$SCRIPT_DIR/.."; and pwd)

# 定义可执行文件路径
set STABLE_BIN "$ROOT_DIR/.envs/stable/bin/quipu"
set DEV_BIN "$ROOT_DIR/.envs/dev/bin/quipu"

# 别名定义
alias qs "$STABLE_BIN"
alias qd "$DEV_BIN"
alias qtest "$ROOT_DIR/.envs/dev/bin/pytest"
alias ruff "$ROOT_DIR/.envs/dev/bin/ruff"

echo "✅ Quipu 开发环境已激活 (Fish)"
echo "  🔹 qs [...]  -> Stable 稳定版 (PyPI 安装，用于作为基础设施)"
echo "  🔸 qd [...]  -> Dev 开发版 (本地源码，用于实时调试与测试)"
echo "  🧪 qtest     -> 运行测试"
echo "  💅 ruff      -> 代码格式化与检查"