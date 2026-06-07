你的洞察非常敏锐！这确实暴露了本地环境与 CI 环境在**资源加载路径**上的不对称：
1.  **在本地**：因为是在源码工作区运行，`bus.py` 能成功通过相对路径查找到 `.json` 语言包，因此输出了翻译后的中文（如“用法示例”）。
2.  **在远端 CI**：由于包是通过 `uv` 编译/打包安装的，非 Python 的资源文件（`.json`）可能未被正确打包进 Wheel，导致 `needle` 优雅降级退回了原始的 Key（如 `run.info.usageHint`）。

你提出的**“引入测试专用 `raw` 语言模式”**想法极其优雅。这不仅能一举解决本地与远端断言不一致的问题，还能让所有测试代码彻底与具体的翻译文本解耦（避免未来翻译变动导致测试大面积失效）。

我将立即实施这个方案：
1.  **在 `bus.py` 中支持 `raw`/`keys` 模式**：如果语言设置为 `raw` 或 `keys`，直接绕过 I18N 资源加载，直接输出原始 Key。
2.  **在根 `conftest.py` 中强制激活该模式**：在 pytest 启动时，将 `QUIPU_LANG` 设为 `raw`。

## [WIP] fix(i18n): 引入 raw 语言模式以统一本地与 CI 的测试断言

### 用户需求

解决本地测试（输出中文）与 CI 测试（退回 Key）的渲染差异，确保测试断言在任何环境下都使用稳定的 Key 标识符。

### 评论
这是一个优秀的架构决定。测试应当验证“正确的信号是否被发出”（即 Key），而不应当验证“信号具体如何翻译成某种人类语言”。这使测试套件具有极高的鲁棒性。

### 目标

1.  修改 `packages/pyquipu-common/src/quipu/common/bus.py`，增加对 `raw` 和 `keys` 语言模式的显式支持，使其在不加载翻译文件的情况下直接降级返回原始 Key。
2.  修改根目录下的 `conftest.py`，在测试初始化前，强制将 `QUIPU_LANG` 环境变量设为 `"raw"`。

### 基本原理
通过在根 `conftest.py` 的最顶部设置 `os.environ["QUIPU_LANG"] = "raw"`，可以确保在任何测试用例导入 `quipu` 模块之前，该环境变量已被注入。当 `bus.py` 初始化时，它会检测到该值并直接将 `_nexus` 绑定到无翻译的 `global_nexus`，从而在本地也完美模拟出 CI 环境下的“Key 降级”状态。

### 标签
#intent/refine #flow/ready #priority/critical #comp/common #comp/tests #concept/config #scope/dx #ai/brainstorm #task/domain/testing #task/object/i18n-raw-mode #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 让消息总线支持 `raw` / `keys` 降级模式

我们修改 `bus.py`，使其在检测到 `raw` 或 `keys` 语言设置时，不加载任何 I18N 资源，从而直接向外输出原始消息 Key。

~~~~~act
patch_file
packages/pyquipu-common/src/quipu/common/bus.py
~~~~~
~~~~~python.old
# --- 3. 初始化资源 ---
_assets_root = Path(__file__).parent / "assets"
_lang = _detect_lang()

_factory = I18NFactoryOperator(_assets_root)
_quipu_i18n = _factory(_lang)

_nexus = OverlayOperator([_quipu_i18n, global_nexus])
~~~~~
~~~~~python.new
# --- 3. 初始化资源 ---
_assets_root = Path(__file__).parent / "assets"
_lang = _detect_lang()

if _lang in ("raw", "keys"):
    # "raw" 或 "keys" 模式下，不加载任何本地化翻译，让总线直接输出原始 Key。
    # 这对于在本地和 CI 等不同环境下保持测试断言的一致性至关重要。
    _nexus = global_nexus
else:
    _factory = I18NFactoryOperator(_assets_root)
    _quipu_i18n = _factory(_lang)
    _nexus = OverlayOperator([_quipu_i18n, global_nexus])
~~~~~

#### Acts 2: 在测试入口强制注入 `raw` 语言环境变量

修改根目录下的 `conftest.py`，确保在任何测试启动前，环境已被锁定为 `raw` 模式。

~~~~~act
patch_file
conftest.py
~~~~~
~~~~~python.old
from quipu.test_utils.fixtures import engine_instance, git_workspace, runner

__all__ = ["runner", "git_workspace", "engine_instance"]
~~~~~
~~~~~python.new
import os
# 强制整个测试环境使用 "raw" 语言模式，使本地与 CI 的 I18N 输出完全一致
os.environ["QUIPU_LANG"] = "raw"

from quipu.test_utils.fixtures import engine_instance, git_workspace, runner

__all__ = ["runner", "git_workspace", "engine_instance"]
~~~~~

### 下一步建议

1.  **在本地运行测试**：运行 `pytest`。现在本地的总线应该已经切换到了 `raw` 模式，之前报错的 5 个测试用例应该会完美通过。
2.  **移除硬编码的防线**：此后编写任何新测试时，都可以放心地断言 `L.xxx.xxx` 指针对应的 Key，再也无需担心翻译文件的变动或缺失。
