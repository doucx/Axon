# env-standardize 标准化开发环境配置

## 目标
将开发环境的安装方式固化为标准文件，并移除根目录 `pyproject.toml` 中的包定义以消除隐患。

## 基本原理
通过移除 `[project]` 部分，根目录将不再被 `pip` 视为一个软件包，从而物理上杜绝了“安装根包导致依赖冲突”的可能性。同时，`dev-requirements.txt` 提供了清晰、可重复的开发环境搭建方式。

## 标签
#chore #env #standardization

---

## Script

### Act 1: 创建标准开发依赖清单

创建 `dev-requirements.txt`，显式列出所有子包的 Editable 安装路径。这是以后初始化环境的唯一真理来源。

~~~~~act
write_file
~~~~~

~~~~~path
dev-requirements.txt
~~~~~

~~~~~text
-e packages/quipu-interfaces
-e packages/quipu-engine
-e packages/quipu-runtime
-e packages/quipu-cli
~~~~~

### Act 2: 净化根目录配置

修改 `pyproject.toml`，删除 `[project]` 及其相关部分，仅保留 `[tool.*]` 配置。这将防止根目录被意外安装。

~~~~~act
replace
~~~~~

~~~~~path
pyproject.toml
~~~~~

~~~~~toml
[project]
name = "quipu-dev"
version = "0.1.0"
description = "Metapackage for the Quipu monorepo development environment."
requires-python = ">=3.8"
dependencies = [
    "quipu-interfaces @ file:./packages/quipu-interfaces",
    "quipu-engine @ file:./packages/quipu-engine",
    "quipu-runtime @ file:./packages/quipu-runtime",
    "quipu-cli @ file:./packages/quipu-cli",
]

[project.scripts]
quipu = "quipu.cli.main:app"

[tool.setuptools]
py-modules = []

[tool.pytest.ini_options]
~~~~~

~~~~~toml
# Root configuration for tools only.
# To install the development environment, run: pip install -r dev-requirements.txt

[tool.pytest.ini_options]
~~~~~

### Act 3: 删除遗留的构建信息

清理可能残留的 `quipu_dev.egg-info`，避免 pip 仍然认为它是一个包。

~~~~~act
run_command
~~~~~

~~~~~bash
rm -rf quipu_dev.egg-info
~~~~~

### Act 4: 验证操作流程

模拟一次标准的“新环境搭建”流程：使用新生成的 `dev-requirements.txt` 进行安装，并运行测试。

~~~~~act
run_command
~~~~~

~~~~~bash
pip install -r dev-requirements.txt && pytest
~~~~~