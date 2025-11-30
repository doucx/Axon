好的，我将创建一个计划，用于在项目中建立 CI (持续集成) 流程。

这个计划将创建 GitHub Actions 所需的目录和工作流文件，其内容基于我们刚刚讨论的设计。

## [WIP] chore: 添加基础的 CI/CD 工作流配置

### 用户需求
项目目前没有 CI/CD 流程，需要创建一个 GitHub Actions 工作流文件 (`.github/workflows/ci.yml`)。该工作流应能自动化代码检查 (Ruff)、测试 (Pytest) 和打包验证 (`uv build`)，以确保代码库的质量和稳定性。

### 评论
这是项目走向成熟和开放协作的关键一步。通过自动化测试和代码检查，我们可以确保每次提交的质量，并为未来的贡献者提供一个安全网，极大地提升了项目的健壮性和开发效率。

### 目标
1.  创建 `.github/workflows` 目录结构（如果不存在）。
2.  在上述目录中创建一个名为 `ci.yml` 的文件。
3.  将完整的 CI 配置写入该文件，配置应包含 `quality-checks` 和 `build-wheels` 两个核心作业。

### 基本原理
此 CI 流程的设计严格遵循了项目 `bootstrap.py` 脚本所建立的“双环境旁路”哲学。
-   `quality-checks` 作业精确模拟了 `dev` 环境的创建和测试流程，确保 CI 环境与本地开发环境的一致性。
-   `build-wheels` 作业则模拟了 `promote` 命令的核心构建步骤，验证了所有包的打包配置是否正确，确保项目始终处于可发布状态。
这种设计保证了本地和远程的质量门禁是统一的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/ci-workflow #task/action/creation #task/state/begin

---

### Script

#### Acts 1: 创建目录结构

首先，确保 GitHub Actions 所需的目录 `.github/workflows` 存在。使用 `mkdir -p` 可以安全地创建目录，如果已存在则不执行任何操作。

~~~~~act
run_command
mkdir -p .github/workflows
~~~~~

#### Acts 2: 写入 CI 工作流配置文件

接下来，我们将完整的 CI 工作流配置写入 `ci.yml` 文件。

~~~~~act
write_file .github/workflows/ci.yml
~~~~~
~~~~~yaml
name: Quipu CI

# 触发条件：
# 1. 推送到任何分支
# 2. 创建或更新到 main 分支的 Pull Request
on:
  push:
    branches:
      - "**"
  pull_request:
    branches:
      - main

jobs:
  quality-checks:
    # 在最新的 Ubuntu 环境上运行
    runs-on: ubuntu-latest
    
    # 定义测试矩阵，以支持未来在多个 Python 版本上测试
    strategy:
      matrix:
        python-version: ["3.11"] # 可以扩展为 ["3.10", "3.11", "3.12"]

    steps:
      # 步骤 1: 检出代码
      - name: Checkout repository
        uses: actions/checkout@v4

      # 步骤 2: 设置 Python 环境
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      # 步骤 3: 安装 uv (项目的核心依赖)
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
        
      # 步骤 4: 创建虚拟环境并安装开发依赖
      #   这模拟了 `bootstrap.py` 中创建 dev 环境的过程
      - name: Create venv and install dev dependencies
        run: |
          # 激活 uv
          source $HOME/.cargo/env
          # 创建虚拟环境
          uv venv .envs/dev
          # 安装开发和测试工具，以及所有本地包（可编辑模式）
          uv pip install -p .envs/dev \
            -e packages/quipu-interfaces \
            -e packages/quipu-common \
            -e packages/quipu-engine \
            -e packages/quipu-runtime \
            -e packages/quipu-cli \
            pytest pytest-cov ruff pytest-timeout

      # 步骤 5: 运行 Ruff (代码风格检查和静态分析)
      #   使用 --check 标志，如果代码格式不正确，CI 会失败
      - name: Run Ruff Linter and Formatter Check
        run: |
          source .envs/dev/bin/activate
          ruff check .
          ruff format --check .

      # 步骤 6: 运行 Pytest
      #   pytest 会自动读取 pyproject.toml 中的配置
      - name: Run Pytest with Coverage
        run: |
          source .envs/dev/bin/activate
          pytest
          
  build-wheels:
    # 模拟 `promote` 流程，确保所有包都可以被成功打包
    runs-on: ubuntu-latest
    name: Verify Package Builds
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Build wheels for all packages
        run: |
          source $HOME/.cargo/env
          # 创建用于存放 wheel 的目录
          mkdir -p dist
          # 遍历所有 packages 目录并构建 wheel
          for pkg_dir in packages/*; do
            if [ -d "$pkg_dir" ]; then
              echo "Building wheel for $pkg_dir..."
              uv build "$pkg_dir" --out-dir dist
            fi
          done

      - name: List built wheels
        run: ls -l dist
~~~~~

### 下一步建议
- **提交与推送**: 执行此计划后，请将新创建的 `.github/workflows/ci.yml` 文件提交到你的 Git 仓库并推送到 GitHub。GitHub Actions 将自动检测到该文件并开始运行工作流。
- **创建 `[COMMIT]` 节点**: 在验证 CI 流程可以成功运行后，可以创建一个 `[COMMIT]` 节点，正式将此 CI 配置固化到项目历史中。
