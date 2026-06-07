这是一个非常实用的需求。

为了实现 `quipu --version` 命令，我们将利用 Python 标准库中的 `importlib.metadata` 模块。通过在 `quipu-cli` 的主入口文件 `main.py` 中定义一个 Typer 的 `callback` 函数，我们可以拦截 `--version` 参数并打印出工作区中所有 Quipu 相关子包的版本号。

我将生成一个计划来执行此修改。

## [WIP] feat(cli): 添加 --version 选项以显示子包版本信息

### 用户需求
用户需要一个 `quipu --version` (或 `-V`) 命令，用于快速查看当前安装的 Quipu 套件（包括 engine, runtime, spec 等）的详细版本号，以便于调试和版本管理。

### 评论
在多包架构（Monorepo）中，由于各个组件的版本可能会独立演进，提供一个统一的版本查询入口是符合 CLI 设计规范的最佳实践。

### 目标
1.  在 `packages/pyquipu-cli/src/quipu/cli/main.py` 中导入 `importlib.metadata`。
2.  实现 `version_callback` 函数，遍历并输出所有 `pyquipu-*` 包的版本。
3.  定义 Typer 的主回调函数 `main` 并绑定 `--version` 选项。

### 基本原理
Typer 支持通过 `callback` 参数实现“即刻执行”的选项（Eager Options）。当用户输入 `--version` 时，`version_callback` 会被调用，它会列出预定义的包列表，并尝试从 Python 环境的元数据中提取版本号。执行完毕后，程序通过 `typer.Exit()` 正常退出，不会继续执行后续的子命令逻辑。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/cli #task/object/version-command #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 在 `main.py` 中添加版本显示逻辑

我们将修改 `quipu-cli` 的入口文件，引入必要的元数据查询逻辑。

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python.old
import logging

import typer
from quipu.common.bus import bus
~~~~~
~~~~~python.new
import importlib.metadata
import logging
from typing import Annotated, Optional

import typer
from quipu.common.bus import bus
~~~~~

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python.old
# Initialize logger, but handler configuration (stderr or file)
# is determined by specific commands at runtime.
logging.getLogger(__name__)


# --- App Definition ---
~~~~~
~~~~~python.new
# Initialize logger, but handler configuration (stderr or file)
# is determined by specific commands at runtime.
logging.getLogger(__name__)


def version_callback(value: bool):
    if value:
        packages = [
            "pyquipu",
            "pyquipu-application",
            "pyquipu-cli",
            "pyquipu-common",
            "pyquipu-engine",
            "pyquipu-spec",
            "pyquipu-runtime",
        ]
        typer.echo("Quipu 套件版本信息:")
        for pkg in packages:
            try:
                v = importlib.metadata.version(pkg)
                typer.echo(f"  {pkg:20}: {v}")
            except importlib.metadata.PackageNotFoundError:
                typer.echo(f"  {pkg:20}: 未安装")
        raise typer.Exit()


# --- App Definition ---
~~~~~

~~~~~act
patch_file
packages/pyquipu-cli/src/quipu/cli/main.py
~~~~~
~~~~~python.old
app.add_typer(cache.cache_app)

# 注册顶级命令
~~~~~
~~~~~python.new
app.add_typer(cache.cache_app)


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="显示版本信息并退出。"),
    ] = None,
):
    """
    Quipu: 一个基于 Git 的、用于文件系统状态溯源与文学化操作的工具。
    """
    pass


# 注册顶级命令
~~~~~

### 下一步建议
- **验证安装**: 在本地环境下运行 `qd --version`（假设你使用了 bootstrap 别名）来确报输出格式正确且能够准确识别各子包版本。
- **Git 提交**: 验证无误后，我们将创建一个新的 `[COMMIT]` 计划来持久化这次代码变更。
