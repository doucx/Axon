# Quipu: "Process Archaeology" for the AI Era

**Quipu is not a version control system. It is a "thought-to-reality" transcriber designed for AI, not humans, to record all its operations—successes and failures alike.**


<!--[![CI/CD](https://github.com/quipu-dev/pyquipu/actions/workflows/ci.yml/badge.svg)](https://github.com/quipu-dev/pyquipu/actions/workflows/ci.yml)
Need to add a CI badge here once CI is set up-->

<!--[![PyPI version](https://img.shields.io/pypi/v/pyquipu.svg)](https://pypi.org/project/pyquipu/)-->
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![tested with pytest](https://img.shields.io/badge/tested%20with-pytest-0099d8.svg)](https://pytest.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Core Philosophy: From "Architecture" to "Biology"

In the era dominated by Git, software development is seen as **architecture**. We focus on the final blueprint (the codebase), where every `commit` is expected to be a perfect brick. All discarded drafts, failed attempts, and scaffolding are purged with `git squash`, dismissed as "noise." Git records how a grand edifice is built, one **perfect** brick at a time.

**Quipu posits that in the AI era, software development evolves into biology.**

A software project is an organically growing vine. It sends out tendrils (an AI's attempt), which might wither (errors, logic flaws), take detours (refactoring), and eventually find the sunlight (feature implementation).

While Git records the perfect "final architecture," Quipu acts like a flight recorder, faithfully documenting the "complete ecosystem" of the vine's growth—including all successful, failed, and abandoned paths. **This complete "process" record provides an ultimate safety net, liberating developers to experiment fearlessly**. These intermediate processes, considered "dark matter" by Git, are the very nutrients essential for understanding how an AI "thinks" and for training the next generation of AI.

## Core Workflow: The Four-Step Human-AI Collaboration Loop

Quipu's core is designed around a clear, auditable loop of human-AI collaboration. In this loop, the human's role shifts from a "code artisan" to an "intent gardener."

<!-- A workflow.svg image should be placed here -->

#### 1. **The Need**
The **human** describes a specific development task to the **AI** in natural language.
> **“I need to create an `install.py` script that can automatically build all `quipu-*` packages and install them into an isolated environment.”**

#### 2. **The Plan**
The **AI** translates the human's need into a detailed, executable `Plan.md` file. This file not only contains machine-executable directives (`act`) but, more importantly, includes the AI's understanding of the need, its design rationale, and its reasoning in natural language.

#### 3. **The Review**
The **human** opens `Plan.md` for review. **Crucially, we are not reviewing the minutiae of low-level code, but the AI's high-level "intent."**
*   Is the AI's objective correct?
*   Is its chosen implementation path reasonable?
*   Has it anticipated potential risks?

**`Plan.md` is not meant to be handwritten; it is meant to be reviewed.**
It is an AI-generated, human-auditable contract for collaboration—an unambiguous Lingua Franca between human and AI.

#### 4. **Execute & Solidify**
After the review is approved, the human executes a simple command:
```bash
quipu run Plan.md
```
Quipu's `runtime` parses and executes all directives in the plan, completing the modifications to the filesystem. Simultaneously, Quipu's `engine` solidifies the **entire process** of this operation (including the `Plan.md` itself and the resulting filesystem state change) as an immutable "thought fossil" in the project's history graph.

This loop repeats, with each iteration leaving behind a clear, traceable, and context-rich record for "process archaeology."

## Key Features

*   **📜 Literate Operations**: Drive all filesystem changes through human-readable `Plan.md` files.

*   **🌿 Immutable History Graph**: Uses Git's underlying technology to completely record the "cause (input state)," "effect (output state)," and "process (the plan)" of every operation, forming a Directed Acyclic Graph (DAG).

*   **📸 Full Workspace Snapshots**: Every historical node in Quipu is a complete snapshot of the **entire workspace**, not just staged files. It achieves this through an independent "shadow index," which **does not interfere with your normal Git staging area (`.git/index`)**. This allows you to seamlessly integrate the traditional `git add`/`git commit` workflow while using Quipu.

*   **🕰️ Immersive Time Travel**: The entire history graph is not just visible but fully interactive. This lets you **experiment without fear of failure**.
    *   **UI Mode (Recommended)**: Open `quipu ui`, select any past node in the visual history graph, and press `c` (checkout). Your entire workspace will instantly revert to the state of that point in time.
    *   **CLI Mode**: Use the `quipu checkout <hash>` command to jump to any specific historical state.
    *   Any experiment, no matter how radical, is completely reversible.

*   **💻 Interactive TUI**: A built-in, high-performance Terminal User Interface (`quipu ui`) that lets you intuitively explore, navigate, and understand complex development histories as if you were browsing a webpage.

*   **⚡️ Stateless Executor**: The `quipu axon` command provides a pure, stateless Markdown directive executor that can be easily integrated into CI/CD or other automation scripts without creating any historical records.

*   **🧩 Modular Architecture**: The `engine` (records time) and `runtime` (advances time) are fully decoupled, ensuring the system's long-term extensibility.

## Quick Start

### 1. Installation

The installation process relies on `uv`, an extremely fast Python package installer. Please ensure you have `uv` installed first.

**Step 1: Install uv**

Choose the appropriate command for your operating system to install `uv`:

- **For macOS, Linux, or WSL:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **For Windows (using PowerShell):**
  ```powershell
  irm https://astral.sh/uv/install.ps1 | iex
  ```

After installation, you can verify it was successful by running `uv --version`.

**Step 2: Install Quipu**

After cloning the repository, run the one-click installation script. It will use `uv` to install Quipu into a separate, isolated environment (`~/.quipu_app`), so it won't pollute your global Python environment.
```bash
git clone https://github.com/quipu-dev/pyquipu.git
cd pyquipu
./install_quipu.py
```
Once the installation is complete, please follow the prompt at the end of the script to add `~/.quipu_app/bin` to your `PATH` environment variable.

### 2. Your First Plan
Let's say you want to create a simple "Hello World" file.

**Step 1: Describe the Need (Human -> AI)**
Tell your AI assistant:
> "Please create a file named `hello.txt` with the content `Hello, Quipu!`."

**Step 2: Generate the Plan (AI -> Human)**
The AI will generate a `plan.md` file for you:
```markdown
## [WIP] feat: Create hello world file

### User Need
Create a file named `hello.txt` in the current directory and write the specified content to it.

### Goal
1.  Create a new file `hello.txt`.
2.  The file content should be "Hello, Quipu!".

---
### Script
#### Acts 1: Write file
~~~~~act
write_file hello.txt
~~~~~
~~~~~text
Hello, Quipu!
~~~~~
```

**Step 3: Review and Execute (Human)**
You review the plan and confirm it matches your intent. Now, execute it:
```bash
quipu run plan.md
```

**Step 4: Verify History & Time Travel**
The file `hello.txt` is created. More importantly, this process has been recorded. You can view it with the TUI:
```bash
quipu ui
```
You will see a new node in the history graph with the title `[WIP] feat: Create hello world file`. You can select this node at any time and press `c` to instantly return to the world as it was when this file was first created.

## Contributing

Quipu is an actively evolving project. We believe that in the AI era, the most valuable forms of contribution are also changing:
1.  **Contribute better prompts**: Help us build a richer set of `Plan.md` templates, enabling AI-generated history to carry more analyzable semantic information.
2.  **Contribute new `act` plugins**: Expand the boundaries of what Quipu can do.
3.  **Performance and stability improvements**: Optimize Quipu's core engine and TUI.

Please consult our contribution guidelines (coming soon) for more information.

## License

This project is licensed under the [Apache 2.0](https://github.com/quipu-dev/pyquipu/blob/main/LICENSE) License.
