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