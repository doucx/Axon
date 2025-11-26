import json
import logging
from typing import Any

from quipu.core.models import QuipuNode
from quipu.core.storage import HistoryReader, HistoryWriter
from quipu.core.git_object_storage import GitObjectHistoryWriter
from .sqlite_db import DatabaseManager

logger = logging.getLogger(__name__)


class SQLiteHistoryWriter(HistoryWriter):
    """
    一个实现“双写”的历史写入器。
    1. 委托 GitObjectHistoryWriter 将节点写入 Git。
    2. 将元数据和关系写入 SQLite。
    """

    def __init__(self, git_writer: GitObjectHistoryWriter, db_manager: DatabaseManager):
        self.git_writer = git_writer
        self.db_manager = db_manager

    def create_node(
        self,
        node_type: str,
        input_tree: str,
        output_tree: str,
        content: str,
        **kwargs: Any,
    ) -> QuipuNode:
        # 步骤 1: 调用底层 Git 写入器创建 Git Commit
        # 它会返回一个包含所有必要信息的 QuipuNode 实例
        git_node = self.git_writer.create_node(
            node_type, input_tree, output_tree, content, **kwargs
        )
        commit_hash = git_node.filename.name

        # 步骤 2: 将元数据写入 SQLite
        try:
            # 2.1 提取元数据 (从 Git 写入器内部逻辑中获取)
            # 这部分有些重复，未来可以优化 writer 的返回值
            start_time = kwargs.get("start_time", git_node.timestamp.timestamp())
            summary = self.git_writer._generate_summary(
                node_type, content, input_tree, output_tree, **kwargs
            )
            metadata = {
                "meta_version": "1.0",
                "summary": summary,
                "type": node_type,
                "generator": self.git_writer._get_generator_info(),
                "env": self.git_writer._get_env_info(),
                "exec": {"start": start_time, "duration_ms": 0}, # 持续时间暂时无法精确计算
            }
            meta_json_str = json.dumps(metadata)

            # 2.2 写入 'nodes' 表
            self.db_manager.execute_write(
                """
                INSERT OR REPLACE INTO nodes 
                (commit_hash, output_tree, node_type, timestamp, summary, generator_id, meta_json, plan_md_cache)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit_hash,
                    output_tree,
                    node_type,
                    start_time,
                    summary,
                    metadata["generator"]["id"],
                    meta_json_str,
                    content,  # 热缓存: 新创建的节点内容直接写入缓存
                ),
            )

            # 2.3 写入 'edges' 表
            parent_commit = self.git_writer.git_db.get_commit_by_output_tree(input_tree)
            if parent_commit:
                self.db_manager.execute_write(
                    "INSERT OR IGNORE INTO edges (child_hash, parent_hash) VALUES (?, ?)",
                    (commit_hash, parent_commit),
                )
            
            # 2.4 (未来) 写入 'private_data' 表
            # intent = kwargs.get("intent_md")
            # if intent: ...

            logger.debug(f"✅ 节点元数据 {commit_hash[:7]} 已写入 SQLite。")

        except Exception as e:
            # 关键：如果数据库写入失败，我们不能回滚 Git 提交，
            # 但必须记录一个严重警告，提示需要进行数据补水。
            logger.error(f"⚠️  严重: Git 节点 {commit_hash[:7]} 已创建，但写入 SQLite 失败: {e}")
            logger.warning("   -> 下次启动或 `sync` 时将通过补水机制修复。")

        # 无论数据库写入是否成功，都返回从 Git 创建的节点
        return git_node