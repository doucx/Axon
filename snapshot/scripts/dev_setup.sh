#!/bin/bash

# 获取项目根目录 (scripts/ 的上一级)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 定义可执行文件路径
STABLE_BIN="$ROOT_DIR/.envs/stable/bin/quipu"
DEV_BIN="$ROOT_DIR/.envs/dev/bin/quipu"

# 别名定义
# qs: Quipu Stable (PyPI 发行版，不受本地源码变动影响)
alias qs="$STABLE_BIN"

# qd: Quipu Dev (本地可编辑源码版，实时反映代码修改)
alias qd="$DEV_BIN"

# qtest: 运行测试
alias qtest="$ROOT_DIR/.envs/dev/bin/pytest"

# ruff: 代码格式化与检查
alias ruff="$ROOT_DIR/.envs/dev/bin/ruff"

echo "✅ Quipu 开发环境已激活 (Bash)"
echo "  🔹 qs [...]  -> Stable 稳定版 (PyPI 安装，用于作为基础设施)"
echo "  🔸 qd [...]  -> Dev 开发版 (本地源码，用于实时调试与测试)"
echo "  🧪 qtest     -> 运行测试"
echo "  💅 ruff      -> 代码格式化与检查"