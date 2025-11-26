import logging
from pathlib import Path
from typing import Optional

from quipu.core.state_machine import Engine
from quipu.core.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.core.git_db import GitDB
from quipu.core.config import ConfigManager
from .utils import find_git_repository_root

logger = logging.getLogger(__name__)


def create_engine(work_dir: Path) -> Engine:
    """
    实例化完整的 Engine 堆栈。

    会自动向上查找项目根目录 (Git Root) 来初始化 Engine。
    如果找不到 Git Root，则回退到 work_dir。
    此工厂现在由配置驱动，以决定使用何种存储后端。
    """
    # 1. 尝试查找真正的项目根目录 (包含 .git 的目录)
    project_root = find_git_repository_root(work_dir)
    if not project_root:
        project_root = work_dir

    # 2. 加载配置
    config = ConfigManager(project_root)
    storage_type = config.get("storage.type", "git_object")

    # 3. 创建 GitDB 实例，这是多种存储格式可能共用的基础
    git_db = GitDB(project_root)

    # 4. 根据配置选择存储后端
    if storage_type == "git_object":
        logger.debug("Using Git Object storage format.")
        reader = GitObjectHistoryReader(git_db)
        writer = GitObjectHistoryWriter(git_db)
    else:
        # 未来可以扩展其他类型，例如 file_system, sqlite
        raise NotImplementedError(f"Storage type '{storage_type}' is not supported.")

    # 5. 注入依赖并实例化 Engine
    engine = Engine(project_root, db=git_db, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱

    return engine
