# chore 构建双环境旁路基础设施

## 目标
建立基于 `uv` 的双活开发环境基础设施。
1.  **Stable 环境 (`.envs/stable`)**: 安装代码的静态快照，作为执行工具 (`qx`)，用于修改源码。
2.  **Dev 环境 (`.envs/dev`)**: 安装代码的动态链接 (`-e`)，作为被测对象 (`qd`)，用于测试和验证。
3.  提供自动化脚本管理这两个环境的生命周期（初始化、晋升、重置）。

## 基本原理
为了解决“工具与对象不分”导致的死锁风险，通过物理隔离运行环境来实现“旁路修复”。
*   引入 `pyproject.toml` 定义 Workspace，利用 `uv` 的工作区特性管理依赖。
*   使用 `bootstrap.py` 封装 `uv` 命令，屏蔽环境构建的复杂性。
*   通过 Shell 脚本注入别名 (`qx`/`qd`)，建立符合直觉的操作流。

## 标签
 #chore #infra #dev-experience

---

## Script

### Act 1: 配置 Workspace 与 Git 忽略规则

定义根目录的 `pyproject.toml` 以启用 `uv` 的 workspace 模式，并更新 `.gitignore` 以排除新的环境目录。

~~~~~act
write_file pyproject.toml
~~~~~

~~~~~toml
[project]
name = "quipu-monorepo"
version = "0.1.0"
description = "Quipu Development Monorepo"
requires-python = ">=3.10"
dependencies = []

[tool.uv]
# 将 packages 下的所有包纳入工作区管理
workspace.members = ["packages/*"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
~~~~~

~~~~~act
append_file .gitignore
~~~~~

~~~~~text

# --- Quipu Dev Infra ---
.envs/
.uv/
sandbox/
*.egg-info/
__pycache__/
.pytest_cache/
.coverage
htmlcov/
~~~~~

### Act 2: 创建环境管理脚本 (Bootstrap)

编写 `bootstrap.py`，负责检测 `uv`，创建双环境，以及处理“晋升”逻辑（将 Dev 代码快照刷新到 Stable）。

~~~~~act
write_file bootstrap.py
~~~~~

~~~~~python
#!/usr/bin/env python3
import shutil
import subprocess
import sys
import argparse
from pathlib import Path

# 配置
ROOT_DIR = Path(__file__).parent
ENVS_DIR = ROOT_DIR / ".envs"
STABLE_DIR = ENVS_DIR / "stable"
DEV_DIR = ENVS_DIR / "dev"

PACKAGES = [
    "packages/quipu-interfaces",
    "packages/quipu-engine",
    "packages/quipu-runtime",
    "packages/quipu-cli",
]

def check_uv():
    """检查 uv 是否安装"""
    if not shutil.which("uv"):
        print("❌ 错误: 未找到 'uv'。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

def create_venv(path: Path):
    """创建虚拟环境"""
    if path.exists():
        print(f"🔄 清理旧环境: {path}")
        shutil.rmtree(path)
    
    print(f"🔨 创建虚拟环境: {path}")
    subprocess.run(["uv", "venv", str(path)], check=True)

def install_packages(env_path: Path, editable: bool):
    """安装包到指定环境"""
    pip_cmd = ["uv", "pip", "install", "-p", str(env_path)]
    
    # 安装测试依赖 (pytest 等) 到 dev 环境
    if editable:
        pip_cmd.extend(["pytest", "pytest-cov"])

    # 构建包路径列表
    args = []
    for pkg in PACKAGES:
        pkg_path = ROOT_DIR / pkg
        if editable:
            args.append("-e")
        args.append(str(pkg_path))
    
    print(f"📦 安装依赖到 {env_path.name} (Editable={editable})...")
    subprocess.run(pip_cmd + args, check=True)

def setup():
    """初始化双环境"""
    ENVS_DIR.mkdir(exist_ok=True)
    
    # 1. Setup Stable (Static Snapshot)
    create_venv(STABLE_DIR)
    install_packages(STABLE_DIR, editable=False)
    
    # 2. Setup Dev (Dynamic Link)
    create_venv(DEV_DIR)
    install_packages(DEV_DIR, editable=True)
    
    print("\n✅ 环境初始化完成！")
    print_usage()

def promote():
    """将当前源码晋升为 Stable 工具"""
    print("🚀 正在晋升 Dev 代码到 Stable 环境...")
    
    # 1. 简单的自测 (可选，这里先跳过，由用户自觉保证)
    
    # 2. 重建 Stable
    create_venv(STABLE_DIR)
    install_packages(STABLE_DIR, editable=False)
    
    print("\n✅ 晋升完成！现在的 'qx' 已经是最新代码的快照。")

def print_usage():
    print("-" * 50)
    print("请运行以下命令激活别名:")
    print("  source dev_setup.sh")
    print("-" * 50)
    print("命令说明:")
    print("  qx <args>   -> 使用 Stable 版 Quipu (工具)")
    print("  qd <args>   -> 使用 Dev 版 Quipu (被测对象)")
    print("-" * 50)

def main():
    check_uv()
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("init", help="初始化所有环境")
    subparsers.add_parser("promote", help="将当前源码重新安装到 Stable 环境")
    
    args = parser.parse_args()
    if args.command == "init":
        setup()
    elif args.command == "promote":
        promote()
    else:
        # 默认行为
        if not STABLE_DIR.exists() or not DEV_DIR.exists():
            setup()
        else:
            print_usage()

if __name__ == "__main__":
    main()
~~~~~

### Act 3: 创建 Shell 激活脚本

创建一个方便的 Shell 脚本，用于定义 `qx` 和 `qd` 别名，以及常用的快捷指令。

~~~~~act
write_file dev_setup.sh
~~~~~

~~~~~bash
#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 定义 Python 解释器路径
STABLE_PYTHON="$SCRIPT_DIR/.envs/stable/bin/python"
DEV_PYTHON="$SCRIPT_DIR/.envs/dev/bin/python"
STABLE_BIN="$SCRIPT_DIR/.envs/stable/bin/quipu"
DEV_BIN="$SCRIPT_DIR/.envs/dev/bin/quipu"

# 别名定义

# qx: Quipu Execute (Stable)
# 用于执行 Act，修改源码
alias qx="'$STABLE_BIN'"

# qd: Quipu Dev (Development)
# 用于手动测试，调试
alias qd="'$DEV_BIN'"

# qtest: 运行测试
alias qtest="'$SCRIPT_DIR/.envs/dev/bin/pytest'"

# qpromote: 晋升代码
alias qpromote="'$SCRIPT_DIR/.envs/stable/bin/python' '$SCRIPT_DIR/bootstrap.py' promote"

echo "✅ Quipu 开发环境已激活"
echo "  🔹 qx [...]  -> 稳定版 (用于干活)"
echo "  🔸 qd [...]  -> 开发版 (用于调试)"
echo "  🧪 qtest     -> 运行测试"
echo "  🚀 qpromote  -> 将当前代码快照更新到 qx"
~~~~~

### Act 4: 创建沙盒验证脚本 (Verify Sandbox)

创建一个脚本，专门用于给 `qd` 提供一个安全的、隔离的目录来运行，防止其破坏根目录配置。

~~~~~act
write_file verify_sandbox.py
~~~~~

~~~~~python
#!/usr/bin/env python3
import shutil
import subprocess
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent
SANDBOX_DIR = ROOT_DIR / "sandbox"
DEV_QUIPU = ROOT_DIR / ".envs" / "dev" / "bin" / "quipu"

def setup_sandbox():
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)
    SANDBOX_DIR.mkdir()
    
    print(f"📦 初始化沙盒: {SANDBOX_DIR}")
    # 初始化 Git (Engine 需要)
    subprocess.run(["git", "init"], cwd=SANDBOX_DIR, check=True, capture_output=True)
    # 配置 Git 用户
    subprocess.run(["git", "config", "user.email", "sandbox@quipu.dev"], cwd=SANDBOX_DIR, check=True)
    subprocess.run(["git", "config", "user.name", "Sandbox Bot"], cwd=SANDBOX_DIR, check=True)

def run_test_plan():
    plan_content = """
~~~act
write_file
~~~
~~~path
hello.txt
~~~
~~~content
Hello from Sandbox
~~~
"""
    plan_path = SANDBOX_DIR / "test_plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")
    
    print("▶️  在沙盒中执行 qd run ...")
    try:
        subprocess.run(
            [str(DEV_QUIPU), "run", "test_plan.md", "--yolo"], 
            cwd=SANDBOX_DIR, 
            check=True
        )
        print("✅ 执行成功")
    except subprocess.CalledProcessError:
        print("❌ 执行失败")
        exit(1)

def verify_result():
    target = SANDBOX_DIR / "hello.txt"
    history = SANDBOX_DIR / ".quipu" / "history"
    
    if target.exists() and target.read_text() == "Hello from Sandbox":
        print("✅ 文件创建验证通过")
    else:
        print("❌ 文件创建验证失败")
        exit(1)
        
    if history.exists() and list(history.glob("*.md")):
        print("✅ 历史记录验证通过")
    else:
        print("❌ 历史记录验证失败")
        exit(1)

def main():
    if not DEV_QUIPU.exists():
        print("❌ 未找到 Dev 环境，请先运行 bootstrap.py")
        exit(1)
        
    setup_sandbox()
    run_test_plan()
    verify_result()
    print("\n🎉 沙盒验证全部通过！代码逻辑基本正常。")

if __name__ == "__main__":
    main()
~~~~~