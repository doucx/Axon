我们将为在本次修复中修改了源码的包以及元包（Meta-package）递增版本号：
- `pyquipu-application`: `0.3.0` -> `0.3.1`
- `pyquipu-engine`: `0.3.0` -> `0.3.1`
- `pyquipu-cli`: `0.3.2` -> `0.3.3`
- `pyquipu` (元包): `0.3.0` -> `0.3.1`（并同步更新其子包依赖约束）
- `VERSION` 文件更新为最新 CLI 版本 `0.3.3`

## [WIP] bump: 为所有变更影响的包更新版本号

### 用户需求

为本次代码变更涉及到的各个 Package 提升版本号（Patch Bump）。

### 评论

通过语义化版本递增，能够准确标识出每个子包的变更历史，保障 Monorepo 内各模块版本发布与依赖演进的清晰可靠。

### 目标

1. 将 `pyquipu-application` 版本更新为 `0.3.1`。
2. 将 `pyquipu-engine` 版本更新为 `0.3.1`。
3. 将 `pyquipu-cli` 版本更新为 `0.3.3`。
4. 将 `pyquipu` 版本更新为 `0.3.1` 并更新依赖条件。
5. 更新根目录下的 `VERSION` 文件为 `0.3.3`。

### 基本原理

通过针对对应 `pyproject.toml` 文件的 `patch_file` 精确升级版本，以及使用 `write_file` 刷新全局 `VERSION` 文件。

### 标签

#intent/build #flow/ready #priority/medium #comp/build #concept/config #scope/core #ai/instruct #task/domain/tooling #task/object/version-bump #task/action/update #task/state/begin

---

### Script

#### Acts 1: 更新 `pyquipu-application` 版本号

~~~~~act
patch_file
packages/pyquipu-application/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-application"
version = "0.3.0"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "Core application logic for Quipu, orchestrating engine and runtime."
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-application"
version = "0.3.1"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "Core application logic for Quipu, orchestrating engine and runtime."
~~~~~

#### Acts 2: 更新 `pyquipu-engine` 版本号

~~~~~act
patch_file
packages/pyquipu-engine/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-engine"
version = "0.3.0"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "The state and history engine for Quipu, powered by Git plumbing."
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-engine"
version = "0.3.1"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "The state and history engine for Quipu, powered by Git plumbing."
~~~~~

#### Acts 3: 更新 `pyquipu-cli` 版本号

~~~~~act
patch_file
packages/pyquipu-cli/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-cli"
version = "0.3.2"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "The command-line interface for Quipu."
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyquipu-cli"
version = "0.3.3"
authors = [{ name="doucx", email="doucxldh@gmail.com" }]
description = "The command-line interface for Quipu."
~~~~~

#### Acts 4: 更新 `pyquipu` 元包版本号及依赖

~~~~~act
patch_file
packages/pyquipu/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "pyquipu"
version = "0.3.0"
description = "Quipu: Process Archaeology for the AI Era (Meta-package)"
~~~~~
~~~~~toml
[project]
name = "pyquipu"
version = "0.3.1"
description = "Quipu: Process Archaeology for the AI Era (Meta-package)"
~~~~~

~~~~~act
patch_file
packages/pyquipu/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
    "pyquipu-application ~= 0.3.0",
    "pyquipu-cli ~= 0.3.0",
    "pyquipu-common ~= 0.2.0",
    "pyquipu-engine ~= 0.3.0",
    "pyquipu-spec ~= 0.1.1",
    "pyquipu-runtime ~= 0.3.0",
]
~~~~~
~~~~~toml
dependencies = [
    "pyquipu-application ~= 0.3.1",
    "pyquipu-cli ~= 0.3.3",
    "pyquipu-common ~= 0.2.0",
    "pyquipu-engine ~= 0.3.1",
    "pyquipu-spec ~= 0.1.1",
    "pyquipu-runtime ~= 0.3.0",
]
~~~~~

#### Acts 5: 更新全局 `VERSION` 文件

~~~~~act
write_file
VERSION
~~~~~
~~~~~text
0.3.3
~~~~~

### 下一步建议

在版本号更新完成后，可以运行 `uv sync` 或相关打包构建工具校验各个包的依赖解析。
