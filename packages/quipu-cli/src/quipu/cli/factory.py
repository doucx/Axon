import logging
from pathlib import Path
from typing import Optional

from quipu.core.state_machine import Engine

from quipu.core.git_object_storage import GitObjectHistoryReader, GitObjectHistoryWriter
from quipu.core.git_db import GitDB

logger = logging.getLogger(__name__)

def find_project_root(start_path: Path) -> Optional[Path]:
    """向上递归查找包含 .git 的目录作为项目根目录"""
    try:
        current = start_path.resolve()
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent
    except Exception:
        pass
    return None

def resolve_root(work_dir: Path) -> Path:
    """解析项目根目录，如果未找到则回退到 work_dir"""
    root = find_project_root(work_dir)
    return root if root else work_dir

def create_engine(work_dir: Path) -> Engine:
    """
    实例化完整的 Engine 堆栈。
    自动检测存储格式 (Git Object vs. File System) 并加载相应后端。
    该函数会自动调用 engine.align() 来加载历史图谱。
    """
    real_root = resolve_root(work_dir)
    
    # 1. 创建 GitDB 实例
    # 假设工作区是一个有效的 git 仓库。如果不是，GitDB 初始化可能会抛出异常。
    git_db = GitDB(real_root)
    
    # 2. 默认使用 Git Object 存储
    logger.debug("Defaulting to Git Object storage format.")
    reader = GitObjectHistoryReader(git_db)
    writer = GitObjectHistoryWriter(git_db)

    # 3. 注入依赖并实例化 Engine
    engine = Engine(real_root, reader=reader, writer=writer)
    engine.align()  # 对齐以加载历史图谱
    
    return engine