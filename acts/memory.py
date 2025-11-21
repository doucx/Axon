import logging
from typing import List
from datetime import datetime
from core.executor import Executor, ExecutionError

logger = logging.getLogger(__name__)

def register(executor: Executor):
    """注册记忆与日志操作"""
    executor.register("log_thought", _log_thought, arg_mode="block_only")

def _log_thought(executor: Executor, args: List[str]):
    """
    Act: log_thought
    Args: [content]
    说明: 将思维过程追加到 .axon/memory.md 文件中，用于长期记忆。
    """
    if len(args) < 1:
        raise ExecutionError("log_thought 需要内容参数")
    
    content = args[0]
    
    # 确保 .axon 目录存在
    memory_dir = executor.root_dir / ".axon"
    memory_dir.mkdir(exist_ok=True)
    
    memory_file = memory_dir / "memory.md"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## [{timestamp}]\n{content}\n"
    
    # 这种纯日志操作通常不需要确认，直接写入
    with open(memory_file, "a", encoding="utf-8") as f:
        f.write(entry)
        
    logger.info(f"🧠 [Memory] 思维已记录到 .axon/memory.md")