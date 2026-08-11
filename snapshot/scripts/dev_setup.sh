#!/bin/bash

# 获取脚本所在目录的绝对路径
# BASH_SOURCE[0] 是 bash 中获取当前脚本路径的标准方法
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 定义 Python 解释器路径
STABLE_PYTHON="$SCRIPT_DIR/.envs/stable/bin/python"
DEV_PYTHON="$SCRIPT_DIR/.envs/dev/bin/python"
STABLE_BIN="$SCRIPT_DIR/.envs/stable/bin/quipu"
DEV_BIN="$SCRIPT_DIR/.envs/dev/bin/quipu"

# qs: Quipu Execute (Stable)
alias qs="$STABLE_BIN"

# qd: Quipu Dev (Development)
alias qd="$DEV_BIN"

# qtest: 运行测试
alias qtest="$SCRIPT_DIR/.envs/dev/bin/pytest"

# ruff: 代码格式化与检查
alias ruff="$SCRIPT_DIR/.envs/dev/bin/ruff"

# qpromote: 晋升代码
alias qpromote="$STABLE_PYTHON $SCRIPT_DIR/bootstrap.py promote"

echo "✅ Quipu 开发环境已激活 (Bash)"
echo "  🔹 qs [...]  -> 稳定版 (用于干活)"
echo "  🔸 qd [...]  -> 开发版 (用于调试)"
echo "  🧪 qtest     -> 运行测试"
echo "  💅 ruff      -> 代码格式化与检查"
echo "  🚀 qpromote  -> 将当前代码快照更新到 qs"
