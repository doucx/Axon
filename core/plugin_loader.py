import importlib
import logging
from pathlib import Path
from .executor import Executor

logger = logging.getLogger(__name__)

def load_plugins(executor: Executor, plugin_dir: Path):
    """
    动态扫描、导入并注册所有插件模块。
    约定：每个插件模块文件必须包含一个名为 'register' 的函数。
    """
    logger.info(f"🔍 正在从 '{plugin_dir.name}' 目录加载插件...")
    
    # 确保插件目录是一个 Python 包
    if not (plugin_dir / "__init__.py").exists():
        logger.warning(f"插件目录 '{plugin_dir}' 不是一个有效的包 (缺少 __init__.py)，跳过加载。")
        return

    for file_path in plugin_dir.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        module_name = f"{plugin_dir.name}.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
            
            # 查找约定的 'register' 函数
            if hasattr(module, "register"):
                register_func = getattr(module, "register")
                register_func(executor)
                logger.debug(f"✅ 成功加载插件: {module_name}")
            else:
                logger.warning(f"⚠️  在模块 {module_name} 中未找到 'register' 函数，跳过。")
        except Exception as e:
            logger.error(f"❌ 加载插件 {module_name} 失败: {e}")
