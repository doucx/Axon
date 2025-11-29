# Quipu: 面向 AI 时代的“过程考古学”

**Quipu 不是一个版本控制系统。它是一个为 AI 而非人类设计的、旨在记录其所有成功与失败操作的“思维-现实”转录机。**

<!--[![CI/CD](https://github.com/quipu-dev/pyquipu/actions/workflows/ci.yml/badge.svg)](https://github.com/quipu-dev/pyquipu/actions/workflows/ci.yml)
这里还需要加一个 CI 的图标，等 CI 弄好再说-->

<!--[![PyPI version](https://img.shields.io/pypi/v/pyquipu.svg)](https://pypi.org/project/pyquipu/)-->
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![tested with pytest](https://img.shields.io/badge/tested%20with-pytest-0099d8.svg)](https://pytest.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## 核心理念：从“建筑学”到“生物学”

在 Git 统治的时代，软件开发被视为**建筑学**。我们关注的是最终的蓝图（代码库），每一次提交（`commit`）都应是一块完美的砖石。所有废弃的草稿、失败的尝试、脚手架，都在 `git squash` 中被清除，被视为“噪音”。Git 记录了一座宏伟大厦是如何被一块块**完美**的砖石堆砌起来的。

**Quipu 认为，在 AI 时代，软件开发演变成了生物学。**

一个软件项目是一株有机生长的藤蔓。它会伸出触须（AI 的一次尝试），可能会枯萎（报错、逻辑错误），可能会绕路（重构），最终找到阳光（功能实现）。

Git 记录了完美的“最终建筑”，而 Quipu 则像一台飞行记录仪，忠实地记录了藤蔓生长的“完整生态”——包括所有成功的、失败的、被抛弃的路径。**这份完整的“过程”记录提供了一个终极安全网，彻底解放了开发者，使其可以无畏地进行实验**。这些被 Git 视为“暗物质”的中间过程，正是我们理解 AI 如何“思考”并训练下一代 AI 的关键养料。

## 核心工作流：人机协作的四步循环

Quipu 的核心是围绕一个清晰、可审计的人机协作循环设计的。在这个循环中，人类的角色从“代码工匠”转变为“意图园丁”。

<!--这里需要放一个workflow.svg-->

#### 1. **需求 (The Need)**
**人类**使用自然语言向 **AI** 描述一个具体的开发任务。
> **“我需要创建一个 `install.py` 脚本，它可以自动构建所有 `quipu-*` 包并将其安装到一个隔离的环境中。”**

#### 2. **计划 (The Plan)**
**AI** 将人类的需求转化为一个详尽、可执行的 `Plan.md` 文件。这个文件不仅包含机器可执行的指令 (`act`)，更重要的是，它包含了 AI 对需求的理解、设计思路和基本原理的自然语言解释。

#### 3. **审查 (The Review)**
**人类**打开 `Plan.md` 进行审查。**关键在于，我们审查的不是底层代码的细枝末节，而是 AI 的高级“意图”**。
*   AI 的目标是否正确？
*   它选择的实现路径是否合理？
*   它是否预见到了潜在的风险？

**`Plan.md` 不是用来手写的，它是用来审查的。**
它是 AI 生成的、供人类审计的协作契约，是人与 AI 之间无歧义的“通用语” (Lingua Franca)。

#### 4. **执行与固化 (Execute & Solidify)**
在审查通过后，人类执行一个简单的命令：
```bash
quipu run Plan.md
```
Quipu 的 `runtime` 会解析并执行计划中的所有指令，完成对文件系统的修改。与此同时，Quipu 的 `engine` 会将这次操作的**完整过程**（包括 `Plan.md` 本身和它造成的文件系统状态变更）作为一个不可变的“思想化石”，固化到项目的历史图谱中。

这个循环不断重复，每一次迭代都留下了清晰、可追溯、富含上下文的“过程考古学”记录。

## 主要特性

*   **📜 文学化操作 (Literate Operations)**: 通过人类可读的 `Plan.md` 文件驱动所有文件系统变更。

*   **🌿 不可变历史图谱**: 使用 Git 底层技术，将每一次操作的“因（输入状态）”、“果（输出状态）”和“过程（计划）”完整记录下来，形成一个有向无环图 (DAG)。

*   **📸 全工作区快照 (Full Workspace Snapshots)**: Quipu 的每一个历史节点都是对**整个工作区**的完整快照，而非仅仅是暂存文件。它通过独立的“影子索引”实现，**完全不干扰你正常的 Git 暂存区 (`.git/index`)**，让你可以在使用 Quipu 的同时，无缝衔接传统的 `git add`/`git commit` 工作流。

*   **🕰️ 沉浸式时空穿梭 (Immersive Time Travel)**: 整个历史图谱不仅可视，而且完全可交互。这让你**无需担心失败**。
    *   **UI 模式 (推荐)**: 打开 `quipu ui`，在可视化的历史图谱中选中任何一个过去的节点，按下 `c` (checkout)，你的整个工作区就会瞬间恢复到那个时间点的状态。
    *   **CLI 模式**: 通过 `quipu checkout <hash>` 命令，可以精确跳转到任意历史状态。
    *   任何实验，无论多么激进，都是完全可逆的。

*   **💻 交互式 TUI**: 内置一个高性能的终端用户界面 (`quipu ui`)，让你像浏览网页一样直观地探索、导航和理解复杂的开发历史。

*   **⚡️ 无状态执行器**: `quipu axon` 命令提供了一个纯粹的、无状态的 Markdown 指令执行器，可轻松集成到 CI/CD 或其他自动化脚本中，而不产生任何历史记录。

*   **🧩 模块化架构**: `engine`（记录时间）与 `runtime`（推动时间）完全解耦，确保了系统的长期可扩展性。

## 快速上手

### 1. 安装

安装过程依赖于 `uv`，一个极速的 Python 包安装器。请先确保已安装 `uv`。

**步骤一：安装 uv**

请根据你的操作系统选择相应的命令来安装 `uv`：

- **对于 macOS, Linux, 或 WSL:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **对于 Windows (使用 PowerShell):**
  ```powershell
  irm https://astral.sh/uv/install.ps1 | iex
  ```

安装完成后，你可以通过运行 `uv --version` 来验证是否安装成功。

**步骤二：安装 Quipu**

克隆仓库后，运行一键式安装脚本。它会使用 `uv` 将 Quipu 安装到一个独立、隔离的环境 (`~/.quipu_app`) 中，不会污染你的全局 Python 环境。
```bash
git clone https://github.com/quipu-dev/pyquipu.git
cd pyquipu
./install_quipu.py
```
安装完成后，请根据脚本末尾的提示将 `~/.quipu_app/bin` 添加到你的 `PATH` 环境变量中。

### 2. 你的第一个 Plan
假设你想创建一个简单的 "Hello World" 文件。

**步骤 1: 描述需求 (人类 -> AI)**
告诉你的 AI 助手：
> “请创建一个名为 `hello.txt` 的文件，内容是 `Hello, Quipu!`。”

**步骤 2: 生成计划 (AI -> 人类)**
AI 会为你生成一个 `plan.md` 文件：
```markdown
## [WIP] feat: 创建 hello world 文件

### 用户需求
在当前目录下创建一个名为 `hello.txt` 的文件，并写入指定内容。

### 目标
1.  创建一个新的 `hello.txt` 文件。
2.  文件内容应为 "Hello, Quipu!"。

---
### Script
#### Acts 1: 写入文件
~~~~~act
write_file hello.txt
~~~~~
~~~~~text
Hello, Quipu!
~~~~~
```
<!--这里需要包含Plan.md的模板的作用-->
**步骤 3: 审查并执行 (人类)**
你审查了这份计划，确认它符合你的意图。现在执行它：
```bash
quipu run plan.md
```

**步骤 4: 验证历史与时空穿梭**
文件 `hello.txt` 被创建了。更重要的是，这个过程被记录了下来。你可以通过 TUI 查看：
```bash
quipu ui
```
你将在历史图谱中看到一个新节点，其标题为 `[WIP] feat: 创建 hello world 文件`。你可以随时选中这个节点，按下 `c`，瞬间回到这个文件刚刚被创建时的世界。

## 贡献

Quipu 是一个正在积极演进的项目。我们认为，在 AI 时代，最有价值的贡献形式也在发生变化：
1.  **贡献更好的提示词 (Prompts)**: 帮助我们构建更丰富的 `Plan.md` 模板，让 AI 生成的历史记录携带更多可分析的语义信息。
2.  **贡献新的 `act` 插件**: 扩展 Quipu 的能力边界。
3.  **性能与稳定性改进**: 优化 Quipu 的核心引擎与 TUI。

请查阅我们的贡献指南（即将推出）以了解更多信息。

## 许可证

本项目采用 [Apache 2.0](https://github.com/quipu-dev/pyquipu/blob/main/LICENSE) 许可证。
