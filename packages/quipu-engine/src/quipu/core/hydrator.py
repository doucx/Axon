import json
import logging
import re
from typing import List, Dict, Set, Tuple

from .git_db import GitDB
from .sqlite_db import DatabaseManager
from .git_object_storage import GitObjectHistoryReader  # Reuse parsing logic

logger = logging.getLogger(__name__)


class Hydrator:
    """
    负责将 Git 对象历史记录同步（补水）到 SQLite 数据库。
    """

    def __init__(self, git_db: GitDB, db_manager: DatabaseManager):
        self.git_db = git_db
        self.db_manager = db_manager
        # 复用 Reader 中的二进制解析逻辑，避免代码重复
        self._parser = GitObjectHistoryReader(git_db)

    def _get_missing_commit_hashes(self) -> Set[str]:
        """
        计算存在于 Git 中但缺失于 SQLite 的 commit 哈希集合。
        """
        logger.debug("正在计算需要补水的 Commit...")
        all_git_heads = self.git_db.get_all_ref_heads("refs/quipu/")
        if not all_git_heads:
            return set()

        git_log_entries = self.git_db.log_ref(all_git_heads)
        git_hashes = {entry["hash"] for entry in git_log_entries}
        
        db_hashes = self.db_manager.get_all_node_hashes()
        
        missing_hashes = git_hashes - db_hashes
        logger.info(f"发现 {len(missing_hashes)} 个需要补水的节点。")
        return missing_hashes

    def sync(self):
        """
        执行增量补水操作。
        """
        missing_hashes = self._get_missing_commit_hashes()
        if not missing_hashes:
            logger.debug("✅ 数据库与 Git 历史一致，无需补水。")
            return

        all_git_logs = self.git_db.log_ref(self.git_db.get_all_ref_heads("refs/quipu/"))
        log_map = {entry["hash"]: entry for entry in all_git_logs}

        # --- 批量准备数据 ---
        nodes_to_insert: List[Tuple] = []
        edges_to_insert: List[Tuple] = []

        # 1. 批量获取 Trees
        tree_hashes = [log_map[h]["tree"] for h in missing_hashes]
        trees_content = self.git_db.batch_cat_file(tree_hashes)

        # 2. 解析 Trees, 批量获取 Metas
        tree_to_meta_blob: Dict[str, str] = {}
        meta_blob_hashes: List[str] = []
        for tree_hash, content_bytes in trees_content.items():
            entries = self._parser._parse_tree_binary(content_bytes)
            if "metadata.json" in entries:
                blob_hash = entries["metadata.json"]
                tree_to_meta_blob[tree_hash] = blob_hash
                meta_blob_hashes.append(blob_hash)

        metas_content = self.git_db.batch_cat_file(meta_blob_hashes)

        # 3. 构建插入数据
        for commit_hash in missing_hashes:
            log_entry = log_map[commit_hash]
            tree_hash = log_entry["tree"]
            
            meta_blob_hash = tree_to_meta_blob.get(tree_hash)
            if not meta_blob_hash:
                logger.warning(f"跳过 {commit_hash[:7]}: 找不到 metadata.json")
                continue

            meta_bytes = metas_content.get(meta_blob_hash)
            if not meta_bytes:
                logger.warning(f"跳过 {commit_hash[:7]}: 找不到 metadata blob")
                continue
            
            output_tree = self._parser._parse_output_tree_from_body(log_entry["body"])
            if not output_tree:
                logger.warning(f"跳过 {commit_hash[:7]}: 找不到 Output-Tree trailer")
                continue

            try:
                meta_data = json.loads(meta_bytes)
                nodes_to_insert.append((
                    commit_hash,
                    output_tree,
                    meta_data.get("type", "unknown"),
                    float(meta_data.get("exec", {}).get("start") or log_entry["timestamp"]),
                    meta_data.get("summary", "No summary"),
                    meta_data.get("generator", {}).get("id"),
                    meta_bytes.decode('utf-8'),
                    None  # plan_md_cache is NULL for cold data
                ))

                # 处理边关系
                parent_hashes = log_entry["parent"].split()
                for p_hash in parent_hashes:
                    edges_to_insert.append((commit_hash, p_hash))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析 {commit_hash[:7]} 的元数据失败: {e}")

        # --- 批量写入数据库 ---
        if nodes_to_insert:
            self.db_manager.batch_insert_nodes(nodes_to_insert)
            logger.info(f"💧 {len(nodes_to_insert)} 个节点元数据已补水。")
        if edges_to_insert:
            self.db_manager.batch_insert_edges(edges_to_insert)
            logger.info(f"💧 {len(edges_to_insert)} 条边关系已补水。")
