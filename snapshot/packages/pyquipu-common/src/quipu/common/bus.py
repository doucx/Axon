import os
from pathlib import Path
from typing import Optional, Protocol

from needle.bus import FeedbackBus
from needle.operators import I18NFactoryOperator, OverlayOperator
from needle.runtime import nexus as global_nexus
from needle.spec import RendererProtocol


# --- 1. 定义扩展协议 ---
# 我们扩展 Needle 的 RendererProtocol，要求它支持 data() 方法
class QuipuRendererProtocol(RendererProtocol, Protocol):
    def data(self, data_string: str) -> None: ...


# --- 2. 定义支持 data 的 Bus 子类 ---
class QuipuBus(FeedbackBus):
    _renderer: Optional[QuipuRendererProtocol]  # type: ignore

    def data(self, data_string: str) -> None:
        if self._renderer and hasattr(self._renderer, "data"):
            self._renderer.data(data_string)


def _detect_lang() -> str:
    env_lang = os.getenv("QUIPU_LANG") or os.getenv("NEEDLE_LANG")
    if env_lang:
        return env_lang

    sys_lang = os.getenv("LANG")
    if sys_lang:
        base_lang = sys_lang.split(".")[0].split("_")[0]
        if base_lang:
            return base_lang

    return "zh"


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

# --- 4. 实例化自定义 Bus ---
bus = QuipuBus()
bus.set_operator(_nexus)

__all__ = ["bus", "QuipuBus", "QuipuRendererProtocol"]
