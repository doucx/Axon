## [WIP] fix(build): 更新 Ruff 配置以遵循新的 lint 小节格式

### 错误分析
在运行 `ruff format .` 时，Ruff 工具链发出了一条弃用警告。警告指出，顶层的 Linter 设置（如 `select`）已被弃用，应迁移到专门的 `[tool.ruff.lint]` 小节中。

当前的 `pyproject.toml` 文件仍在使用旧的配置格式，这可能导致在未来版本的 Ruff 中出现兼容性问题。

### 用户需求
修改根目录下的 `pyproject.toml` 文件，将 `select` 配置项从 `[tool.ruff]` 移动到 `[tool.ruff.lint]`，以消除弃用警告并使配置与最新规范保持一致。

### 评论
这是一个简单的配置维护任务，遵循工具链的最佳实践可以确保项目的长期健康和可维护性。将配置项按功能（lint, format）分组也使得配置文件本身更具可读性。

### 目标
1.  在 `pyproject.toml` 中，将 `select = ["E", "F", "I"]` 这一行移动到 `[tool.ruff.lint]` 小节下。

### 基本原理
直接使用 `patch_file` 指令，将包含旧配置的整个 `[tool.ruff]` 块替换为符合新规范的格式化块。这样可以原子性地完成更新，确保配置文件的正确性。

### 标签
#intent/fix #flow/ready #priority/low #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/ruff-config #task/action/update #task/state/begin

---

### Script

#### Acts 1: 修正 `pyproject.toml` 中的 Ruff 配置

我们将整个 `[tool.ruff]` 块替换为新的、结构正确的版本。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.ruff]
line-length = 120
target-version = "py38"
select = ["E", "F", "I"] # Pycodestyle Errors, Pyflakes, isort

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
~~~~~
~~~~~toml
[tool.ruff]
line-length = 120
target-version = "py38"

[tool.ruff.lint]
select = ["E", "F", "I"] # Pycodestyle Errors, Pyflakes, isort

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
~~~~~

### 下一步建议
配置已更新。你可以再次运行 `.envs/dev/bin/ruff format .` 或 `.envs/dev/bin/ruff check .`，确认警告信息已经消失。之后，我们就可以提交这次配置修正。

---

好的，这个日志信息非常清晰。它指出了一个配置问题，并且你的 `git commit` 失败是因为 `ruff format` 运行后没有产生任何文件变更，这是一个幂等操作。

我来解释一下 `lint` 是什么，以及如何根据警告信息来修正你的配置。

### 1. `lint` 是什么？

`Lint` 或 `Linter` 是一个**静态代码分析工具**。你可以把它想象成代码的“拼写和语法检查器”。

它在你运行代码**之前**，通过阅读你的源代码来发现潜在的问题，包括：
*   **潜在的 Bug**：比如，你可能把 `==` 写成了 `=`，或者定义了一个从未使用过的变量。
*   **代码风格问题**：比如，代码行太长，`import` 语句顺序不符合规范，或者缩进错误。
*   **不推荐的写法**：比如，使用了一些过时或不安全的函数。

在你的项目中，**Ruff** 是一个集成了 `Linter` 和 `Formatter`（代码格式化工具）的现代高性能工具。
*   `ruff check .` 或 `ruff .` 会执行 **linting**，找出并报告问题。
*   `ruff format .` 会执行 **formatting**，自动修正代码风格问题。

### 2. 如何配置？(解决你的警告)

Ruff 的警告信息非常明确：
> `warning: The top-level linter settings are deprecated in favour of their counterparts in the 'lint' section. Please update... 'select' -> 'lint.select'`

这说明 Ruff 正在将其配置文件（`pyproject.toml`）组织得更有条理。以前，所有配置项都直接放在 `[tool.ruff]` 下面。现在，它把 Linter 相关的配置放到了一个专门的 `[tool.ruff.lint]` 小节里，把 Formatter 相关的配置放到了 `[tool.ruff.format]` 小节里。

你的 `pyproject.toml` 当前的配置是这样的：
```toml
[tool.ruff]
line-length = 120
target-version = "py38"
select = ["E", "F", "I"] # Pycodestyle Errors, Pyflakes, isort

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true
```
你需要做的就是把 `select` 这个配置项移动到一个新的 `[tool.ruff.lint]` 小节中。

我将生成一个计划来执行这个修正。

