好的，我们将开始实施开发环境配置脚本的重构与路径清理。

## [WIP] refactor(scripts): 重构开发环境配置脚本与 Shell 别名

### 用户需求
1. 删除重构前的 `scripts/bootstrap.py`（包括移除 `qpromote`/`promote` 逻辑）。
2. 在 `scripts/` 目录下新增一键开发环境配置脚本 `scripts/setup_dev.py`：
   - `stable` 环境：直接从 PyPI 安装 `pyquipu-cli` 作为独立隔离的基础工具（`qs`）。
   - `dev` 环境：使用 `uv pip install -e .[dev]` 安装本地 Worktree 的可编辑开发包（`qd`）。
3. 更新 `scripts/dev_setup.sh` 和 `scripts/dev_setup.fish`，将虚拟环境路径定位到项目根目录的 `.envs`，并移除 `qpromote` 别名。
4. 更新 CI 工作流注释和 `DEVELOPING.md` 指南文档，保持与新开发流程的一致性。

### 评论
将基础设施与本地开发代码彻底解耦（通过 PyPI 安装 stable 版本作为自举操作工具）极大简化了开发流程，消除了繁琐的 `qpromote` 打包推送环节。同时将环境配置脚本统一收纳至 `scripts/` 目录，保证了根目录的整洁。

### 目标
1. 删除 `scripts/bootstrap.py`。
2. 创建 `scripts/setup_dev.py` 实现全新的环境配置命令。
3. 调整 `scripts/dev_setup.sh` 及 `scripts/dev_setup.fish` 的别名配置。
4. 更新 `.github/workflows/ci.yml` 中的注释及 `DEVELOPING.md` 手册。

### 基本原理
- 使用 `scripts/setup_dev.py` 替代原有的 `bootstrap.py`，精简命令体系。
- `qs`（Stable）直接由 PyPI 安装，确保本地源码即使存在语法错误或编译故障，也不影响使用 `qs run` 执行修复计划。
- Shell 别名激活脚本自动向上计算项目根路径 `$ROOT_DIR`，确保无论在何处 `source` 均可准确定位 `.envs`。

### 标签
#intent/refine #flow/ready #priority/medium #comp/build #concept/config #scope/dx #ai/instruct #task/domain/testing #task/object/dev-environment #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 删除废弃的 bootstrap.py

~~~~~act
delete_file
scripts/bootstrap.py
~~~~~

#### Acts 2: 创建 scripts/setup_dev.py 脚本

~~~~~act
write_file
scripts/setup_dev.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# 路径计算 (scripts/ -> 项目根目录)
SCRIPTS_DIR = Path(__file__).parent.resolve()
ROOT_DIR = SCRIPTS_DIR.parent
ENVS_DIR = ROOT_DIR / ".envs"
STABLE_DIR = ENVS_DIR / "stable"
DEV_DIR = ENVS_DIR / "dev"


def check_uv():
    """检查 uv 是否已安装"""
    if not shutil.which("uv"):
        print("❌ 错误: 未找到 'uv'。请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)


def create_venv(path: Path):
    """创建虚拟环境"""
    if path.exists():
        print(f"🔄 清理旧环境: {path}")
        shutil.rmtree(path)

    print(f"🔨 创建虚拟环境: {path.relative_to(ROOT_DIR)}")
    subprocess.run(["uv", "venv", str(path)], check=True, capture_output=True)


def setup_stable():
    """配置 Stable 环境 (直接从 PyPI 安装发行的 pyquipu-cli)"""
    print(f"📦 [Stable] 正在从 PyPI 安装最新发布的 pyquipu-cli 到 {STABLE_DIR.relative_to(ROOT_DIR)}...")
    create_venv(STABLE_DIR)
    try:
        subprocess.run(
            ["uv", "pip", "install", "-p", str(STABLE_DIR), "pyquipu-cli"],
            check=True
        )
        print("✅ [Stable] 环境安装完成！")
    except subprocess.CalledProcessError:
        print("⚠️ [Stable] 安装失败（可能 PyPI 上尚未发布或网络异常）。但不影响开发环境使用。")


def setup_dev():
    """配置 Dev 环境 (本地 Working Tree 可编辑模式)"""
    print(f"📦 [Dev] 正在以可编辑模式安装本地开发环境到 {DEV_DIR.relative_to(ROOT_DIR)}...")
    create_venv(DEV_DIR)
    install_cmd = ["uv", "pip", "install", "-p", str(DEV_DIR), "-e", f"{ROOT_DIR}[dev]"]
    subprocess.run(install_cmd, check=True)
    print("✅ [Dev] 环境安装完成！")


def main():
    check_uv()
    parser = argparse.ArgumentParser(description="Quipu 开发环境一键配置脚本")
    parser.add_argument("--only-dev", action="store_true", help="仅配置/更新 Dev 环境")
    parser.add_argument("--only-stable", action="store_true", help="仅配置/更新 Stable 环境")

    args = parser.parse_args()

    ENVS_DIR.mkdir(exist_ok=True)

    if args.only_dev:
        setup_dev()
    elif args.only_stable:
        setup_stable()
    else:
        setup_stable()
        print()
        setup_dev()

    print("\n🎉 开发环境配置完毕！请激活 Shell 别名：")
    print("  Bash/Zsh: source scripts/dev_setup.sh")
    print("  Fish:     source scripts/dev_setup.fish")


if __name__ == "__main__":
    main()
~~~~~

#### Acts 3: 更新 bash 和 fish 激活脚本

~~~~~act
write_file
scripts/dev_setup.sh
~~~~~
~~~~~bash
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
~~~~~

~~~~~act
write_file
scripts/dev_setup.fish
~~~~~
~~~~~fish
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
~~~~~

#### Acts 4: 更新 CI/CD 工作流与开发文档

~~~~~act
patch_file
.github/workflows/ci.yml
~~~~~
~~~~~yaml.old
      # 步骤 4: 创建虚拟环境并安装开发依赖
      #   这模拟了 `bootstrap.py` 中创建 dev 环境的过程
      - name: Create venv and install dev dependencies
~~~~~
~~~~~yaml.new
      # 步骤 4: 创建虚拟环境并安装开发依赖
      #   这模拟了 `setup_dev.py` 中创建 dev 环境的过程
      - name: Create venv and install dev dependencies
~~~~~

~~~~~act
write_file
DEVELOPING.md
~~~~~
~~~~~markdown
# Quipu 开发指南 (The Quipu Development Workflow)

本文档介绍了如何在一个“依靠 Quipu 构建 Quipu”的自举环境中安全、高效地工作。

## 核心概念：双环境隔离 (Dual-Environment Separation)

为了解决“修改工具本身会导致工具崩溃”的死锁问题，我们维护了两个隔离的环境：

1.  **🔵 Stable 环境 (`qs`)**:
    *   **角色**: 医生/基础设施。
    *   **本质**: 直接从 PyPI 安装的线上稳定发布版 (`pyquipu-cli`)。
    *   **用途**: **你的生产力工具**。用它来执行 Plan 文件、重构源码和代码修改。它完全独立于你正在编辑的本地代码，不会因调试中断。
2.  **🟢 Dev 环境 (`qd`)**:
    *   **角色**: 病人/被测对象。
    *   **本质**: 当前本地源码的可编辑安装 (`uv pip install -e .[dev]`)。
    *   **用途**: **你的测试对象**。用它来跑测试、手动调试、验证新功能。它实时反映本地源码的修改。

---

## 快速开始

### 1. 初始化环境

首次克隆项目或更新依赖后，在根目录执行：

```bash
# 1. 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 一键构建开发环境
python3 scripts/setup_dev.py

# 3. 激活别名 (建议加入 .bashrc 或 .zshrc)
source scripts/dev_setup.sh
```

对于 fish：

```fish
# 激活别名 (建议加入 .config/fish/config.fish)
source scripts/dev_setup.fish
```

### 2. 常用命令速查

| 别名 | 完整命令 | 用途 |
| :--- | :--- | :--- |
| **`qs`** | `.envs/stable/bin/quipu` | **稳定执行工具**。用这个来跑 `Plan.md` 修改代码。 |
| **`qd`** | `.envs/dev/bin/quipu` | **开发调试对象**。用这个来测试本地代码新特性。 |
| **`qtest`** | `.envs/dev/bin/pytest` | **运行测试**。运行项目的单元与集成测试。 |
| **`ruff`** | `.envs/dev/bin/ruff` | **代码检查与格式化**。静态检查和代码美化。 |

---

## 标准开发循环 (The Loop)

### 场景 A：常规功能开发

1.  **编写计划**: 创建 `feat_xxx.md`。
2.  **执行修改**: 使用 **Stable** 环境执行计划。
    ```bash
    qs run feat_xxx.md
    ```
3.  **验证**: 使用 **Dev** 环境运行测试。
    ```bash
    qtest tests/test_new_feat.py
    ```

### 场景 B：依赖更新或新包注册

如果你在 `packages/` 中新增了子包或修改了依赖，只需重新运行：
```bash
python3 scripts/setup_dev.py --only-dev
```

---

## 故障排除

### Q: 我把代码改坏了，`qd` 报错，但我需要用 Quipu 来修复它。
**A**: 这正是双环境存在的意义！`qs` 是通过 PyPI 安装的独立稳定版本，不会受本地源码破坏的影响。你可以继续使用 `qs run fix_bug.md` 来修改源代码。

### Q: `qtest` 找不到我新加的包？
**A**: 如果你添加了新的 `packages/` 子目录，请运行 `python3 scripts/setup_dev.py --only-dev` 来注册新的 Editable Install。
~~~~~

### 下一步建议
1. 执行本 Plan 以更新配置脚本与开发指南。
2. 在终端运行 `python3 scripts/setup_dev.py` 重新生成全新的隔离环境。
3. 重新加载别名脚本（`source scripts/dev_setup.sh`），测试 `qs` 和 `qd` 是否符合预期。
