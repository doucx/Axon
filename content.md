# fix 修复 pyproject.toml 中的 Workspace 依赖配置

## 目标
解决 `bootstrap.py init` 失败的问题。
错误原因：`uv` 在 Workspace 模式下，要求成员包之间的依赖必须在 `pyproject.toml` 中显式声明为 `workspace = true`，或者通过 `tool.uv.sources` 指定，否则无法解析本地路径依赖。

## 基本原理
我们需要更新各个子包 (`packages/*/pyproject.toml`) 的依赖声明，将所有内部依赖（如 `quipu-interfaces`）标记为 Workspace 成员。这告诉 `uv` 不要去 PyPI 找这些包，而是直接链接到本地 Workspace 中的对应源码。

## 标签
 #fix #infra #config

---

## Script

### Act 1: 修复 quipu-engine 的依赖配置

`quipu-engine` 依赖 `quipu-interfaces`。

~~~~~act
replace packages/quipu-engine/pyproject.toml
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "pyyaml>=6.0",
]
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "pyyaml>=6.0",
]

[tool.uv.sources]
quipu-interfaces = { workspace = true }
~~~~~

### Act 2: 修复 quipu-runtime 的依赖配置

`quipu-runtime` 依赖 `quipu-interfaces`。

~~~~~act
replace packages/quipu-runtime/pyproject.toml
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "typer>=0.9.0"
]
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "typer>=0.9.0"
]

[tool.uv.sources]
quipu-interfaces = { workspace = true }
~~~~~

### Act 3: 修复 quipu-cli 的依赖配置

`quipu-cli` 依赖 `quipu-interfaces`, `quipu-engine`, `quipu-runtime`。

~~~~~act
replace packages/quipu-cli/pyproject.toml
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "quipu-engine",
    "quipu-runtime",
    "typer>=0.9.0",
    "textual>=0.58.0",
]
~~~~~

~~~~~toml
dependencies = [
    "quipu-interfaces",
    "quipu-engine",
    "quipu-runtime",
    "typer>=0.9.0",
    "textual>=0.58.0",
]

[tool.uv.sources]
quipu-interfaces = { workspace = true }
quipu-engine = { workspace = true }
quipu-runtime = { workspace = true }
~~~~~