分析正确。

这是一个典型的 Python 包分发问题。当你通过 `pip install`（或 `uv pip install`）安装一个项目时，构建工具 (`setuptools`) 默认只会打包 `.py` 文件。像 `locales/` 这样的数据目录，以及里面的 `.json` 文件，被认为是“非代码文件”，因此在构建 `wheel` 文件时被忽略了。

当你在 `~/.quipu_app/` 中运行安装好的程序时，它的代码位于 `.../site-packages/quipu/...`，但 `locales` 目录并未被复制到那里，导致 `find_locales_dir` 函数（它从当前文件位置向上查找）失败。

解决方案是双重的：
1.  **物理上**将 `locales` 目录移动到它逻辑上所属的包 (`quipu-common`) 的源文件树中。
2.  **配置上**告知 `setuptools` 在构建时将这个数据目录包含进去。

我将生成一个计划来执行这个修复。

## [WIP] fix(common): 正确打包国际化语言文件以供安装后使用

### 错误分析
用户在运行通过 `install_quipu.py` 安装的 `quipu` 程序时，遇到了 `Could not find the 'locales' directory` 的错误。

根本原因是 `quipu-common` 包在构建时没有包含 `locales` 这个数据目录。`setuptools` 默认不打包非 Python 文件。此外，`locales` 目录位于项目根目录，处于任何一个独立包的源码树之外，这使得标准的打包工具无法找到它。`find_locales_dir` 函数的向上查找逻辑也只在 monorepo 开发环境中有效，在安装到 `site-packages` 后便会失效。

### 用户需求
确保通过 `install_quipu.py` 或任何 `pip install` 方式安装的 `quipu` 程序能够找到并加载其语言文件，从而正常显示所有用户界面文本。

### 评论
这是一个关键的修复，它解决了让 Quipu 成为一个可独立分发应用程序的核心障碍。通过将数据文件与使用它的代码进行绑定，并正确配置打包元数据，我们确保了应用在任何环境下都能自洽地运行。

### 目标
1.  将项目根目录的 `locales` 文件夹移动到 `quipu-common` 包的源文件内部，具体路径为 `packages/quipu-common/src/quipu/common/locales`。
2.  修改 `packages/quipu-common/pyproject.toml` 文件，使用 `[tool.setuptools.package-data]` 指令来确保 `locales` 目录及其内容被包含在最终分发的 `wheel` 文件中。
3.  重构 `packages/quipu-common/src/quipu/common/messaging/messages.py` 中的 `find_locales_dir` 函数，使其直接查找与自身相对的路径，而不是向上遍历文件系统。这使得查找逻辑在开发环境和安装环境中都能稳定工作。

### 基本原理
Python 打包的最佳实践是将数据文件放置在包的内部，并使用 `package_data` 或 `include_package_data` 选项进行声明。通过将 `locales` 目录变成 `quipu.common` 包的一部分，并更新查找逻辑为相对路径查找，我们创建了一个健壮且可移植的解决方案，不再依赖于项目的外部目录结构。

### 标签
#intent/fix #flow/ready #priority/critical #comp/common #comp/build #concept/config #scope/core #ai/instruct #task/domain/build #task/object/packaging #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 移动 `locales` 目录并更新打包配置

我们将执行目录移动，然后修改 `quipu-common` 的 `pyproject.toml` 以包含这些新的数据文件。

~~~~~act
move_file
locales
packages/quipu-common/src/quipu/common/locales
~~~~~

~~~~~act
patch_file
packages/quipu-common/pyproject.toml
~~~~~
~~~~~toml
[tool.setuptools.packages.find]
where = ["src"]
namespaces = true
~~~~~
~~~~~toml
[tool.setuptools.packages.find]
where = ["src"]
namespaces = true

[tool.setuptools.package-data]
"quipu.common" = ["locales/zh/*.json"]
~~~~~

#### Acts 2: 简化并固化 `find_locales_dir` 的查找逻辑

现在 `locales` 目录的位置是确定的，我们可以极大地简化查找函数，使其更可靠。

~~~~~act
patch_file
packages/quipu-common/src/quipu/common/messaging/messages.py
~~~~~
~~~~~python
def find_locales_dir() -> Path | None:
    """
    Find the 'locales' directory, searching upwards from this file.
    This allows finding the directory both in development (monorepo root)
    and in installed environments (site-packages).
    """
    current = Path(__file__).resolve()
    # In a monorepo dev setup, it's at the project root.
    for parent in [current] + list(current.parents):
        locales_path = parent / "locales"
        if locales_path.is_dir():
            logger.debug(f"Found locales directory at: {locales_path}")
            return locales_path

    logger.warning("Could not find the 'locales' directory.")
    return None
~~~~~
~~~~~python
def find_locales_dir() -> Path | None:
    """
    Find the 'locales' directory located relative to this file.
    This is robust for both development and installed package environments.
    """
    try:
        # The 'locales' directory is now part of the quipu.common package data
        locales_path = Path(__file__).parent.parent / "locales"
        if locales_path.is_dir():
            logger.debug(f"Found locales directory at: {locales_path}")
            return locales_path
    except Exception as e:
        logger.error(f"Error finding locales directory: {e}")

    logger.warning("Could not find the 'locales' directory.")
    return None
~~~~~

### 下一步建议
我们已经完成了代码和结构的修改。现在，你需要重新安装 Quipu 来验证修复是否生效。

1.  **运行安装脚本**:
    ```bash
    ./install_quipu.py
    ```
2.  **验证**: 再次运行之前的命令，并确认错误消息不再出现。
    ```bash
    /home/doucx/.quipu_app/bin/quipu ui
    ```

如果一切正常，我们就可以提交这个修复。
