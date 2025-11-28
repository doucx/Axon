import json
import logging
import re
from typing import List, Dict, Set, Tuple, Optional

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

    def _get_owner_from_ref(self, ref_name: str, local_user_id: str) -> Optional[str]:
        """从 Git ref 路径中解析 owner_id。"""
        # 匹配 remote 镜像: refs/quipu/remotes/<remote_name>/<user_id>/heads/...
        remote_match = re.match(r"refs/quipu/remotes/[^/]+/([^/]+)/heads/.*", ref_name)
        if remote_match:
            return remote_match.group(1)

        # 匹配 local heads
        if ref_name.startswith("refs/quipu/local/heads/"):
            return local_user_id

        return None

    def _get_missing_commits_with_owner(self, local_user_id: str) -> Dict[str, str]:
        """
        计算 Git 中存在但 SQLite 缺失的 commit，并确定其所有者。
        返回 {commit_hash: owner_id} 字典。
        """
        logger.debug("正在计算需要补水的 Commit 及其所有者...")
        ref_tuples = self.git_db.get_all_ref_heads("refs/quipu/")
        if not ref_tuples:
            return {}

        commit_to_owner: Dict[str, str] = {}
        for commit_hash, ref_name in ref_tuples:
            # 一个 commit 可能被多个 ref 指向 (e.g., local 和 remote mirror)
            # 只要能确定一个所有者即可。
            if commit_hash in commit_to_owner:
                continue
            
            owner_id = self._get_owner_from_ref(ref_name, local_user_id)
            if owner_id:
                commit_to_owner[commit_hash] = owner_id

        if not commit_to_owner:
            return {}

        db_hashes = self.db_manager.get_all_node_hashes()
        
        missing_commits = {
            commit: owner for commit, owner in commit_to_owner.items() if commit not in db_hashes
        }
        
        logger.info(f"发现 {len(missing_commits)} 个需要补水的节点。")
        return missing_commits

    def sync(self, local_user_id: str):
        """
        执行增量补水操作。
        """
        missing_commits = self._get_missing_commits_with_owner(local_user_id)
        if not missing_commits:
            logger.debug("✅ 数据库与 Git 历史一致，无需补水。")
            return

        missing_hashes = list(missing_commits.keys())
        all_git_logs = self.git_db.log_ref(missing_hashes) # Log only missing commits for efficiency
        log_map = {entry["hash"]: entry for entry in all_git_logs}

        # --- 批量准备数据 ---
        nodes_to_insert: List[Tuple] = []
        edges_to_insert: List[Tuple] = []

        # 1. 批量获取 Trees
        tree_hashes = [log_map[h]["tree"] for h in missing_hashes if h in log_map]
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
            if commit_hash not in log_map: continue
            
            log_entry = log_map[commit_hash]
            tree_hash = log_entry["tree"]
            owner_id = missing_commits[commit_hash]

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
                nodes_to_insert.append(
                    (
                        commit_hash,
                        owner_id,
                        output_tree,
                        meta_data.get("type", "unknown"),
                        float(meta_data.get("exec", {}).get("start") or log_entry["timestamp"]),
                        meta_data.get("summary", "No summary"),
                        meta_data.get("generator", {}).get("id"),
                        meta_bytes.decode("utf-8"),
                        None,  # plan_md_cache is NULL for cold data
                    )
                )

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