import logging
from pathlib import Path
from typing import Dict, Optional
import yaml
from datetime import datetime

from .git_db import GitDB
from .history import load_history_graph
from .models import AxonNode

logger = logging.getLogger(__name__)

class Engine:
    """
    Axon 状态引擎。
    负责协调 Git 物理状态和 Axon 逻辑图谱。
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.axon_dir = self.root_dir / ".axon"
        self.history_dir = self.axon_dir / "history"
        self.head_file = self.axon_dir / "HEAD"
        
        # 确保目录结构存在
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心：确保 .axon 目录被 Git 忽略
        axon_gitignore = self.axon_dir / ".gitignore"
        if not axon_gitignore.exists():
            try:
                axon_gitignore.write_text("*\n", encoding="utf-8")
            except Exception as e:
                logger.warning(f"无法创建隔离文件 {axon_gitignore}: {e}")
        
        self.git_db = GitDB(self.root_dir)
        self.history_graph: Dict[str, AxonNode] = {}
        self.current_node: Optional[AxonNode] = None

    def _read_head(self) -> Optional[str]:
        """读取 .axon/HEAD 文件中的 Hash"""
        if self.head_file.exists():
            return self.head_file.read_text(encoding="utf-8").strip()
        return None

    def _write_head(self, tree_hash: str):
        """更新 .axon/HEAD"""
        try:
            self.head_file.write_text(tree_hash, encoding="utf-8")
        except Exception as e:
            logger.warning(f"⚠️  无法更新 HEAD 指针: {e}")

    def align(self) -> str:
        """
        核心对齐方法：确定 "我现在在哪"。
        返回状态: "CLEAN", "DIRTY", "ORPHAN"
        """
        # 1. 加载或重新加载历史
        self.history_graph = load_history_graph(self.history_dir)
        
        # 2. 获取当前物理状态
        current_hash = self.git_db.get_tree_hash()

        # 3. 特殊情况：处理创世状态 (空仓库)
        EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        if current_hash == EMPTY_TREE_HASH and not self.history_graph:
            logger.info("✅ 状态对齐：检测到创世状态 (空仓库)。")
            self.current_node = None
            # 创世状态不写入 HEAD，或者写入空？暂不写入。
            return "CLEAN"
        
        # 4. 在逻辑图谱中定位
        if current_hash in self.history_graph:
            self.current_node = self.history_graph[current_hash]
            logger.info(f"✅ 状态对齐：当前工作区匹配节点 {self.current_node.short_hash}")
            # 对齐成功，更新 HEAD
            self._write_head(current_hash)
            return "CLEAN"
        
        # 未找到匹配节点，进入漂移检测
        logger.warning(f"⚠️  状态漂移：当前 Tree Hash {current_hash[:7]} 未在历史中找到。")
        
        if not self.history_graph:
            return "ORPHAN" # 历史为空，但工作区非空
        
        return "DIRTY"

    def capture_drift(self, current_hash: str, message: Optional[str] = None) -> AxonNode:
        """
        捕获当前工作区的漂移，生成一个新的 CaptureNode。
        """
        log_message = f"📸 正在捕获工作区漂移 (Message: {message})" if message else f"📸 正在捕获工作区漂移"
        logger.info(f"{log_message}，新状态 Hash: {current_hash[:7]}")

        # 1. 确定父节点 (input_tree)
        # 优先使用 HEAD 指针，其次尝试从历史中推断，最后回退到创世 Hash
        genesis_hash = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        input_hash = genesis_hash
        
        head_hash = self._read_head()
        if head_hash and head_hash in self.history_graph:
            input_hash = head_hash
        elif self.history_graph:
            # Fallback: 使用时间戳最新的节点（风险：可能导致跳线，但在无 HEAD 时是唯一选择）
            last_node = max(self.history_graph.values(), key=lambda node: node.timestamp)
            input_hash = last_node.output_tree
            logger.warning(f"⚠️  丢失 HEAD 指针，自动回退到最新历史节点: {input_hash[:7]}")
        
        # 获取父 Commit 用于 Git 锚定
        last_commit_hash = None
        # 这里逻辑简化：不再依赖 rev-parse refs/axon/history，而是尝试通过 input_hash 找关系
        # 但为了保持兼容，我们还是尝试获取
        res = self.git_db._run(["rev-parse", "refs/axon/history"], check=False)
        if res.returncode == 0:
            last_commit_hash = res.stdout.strip()

        # 2. 生成差异摘要
        diff_summary = self.git_db.get_diff_stat(input_hash, current_hash)
        
        # 3. 构建节点内容和元数据
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_hash}_{current_hash}_{ts_str}.md"
        
        meta = {"type": "capture", "input_tree": input_hash, "output_tree": current_hash}
        
        user_message_section = f"### 💬 备注:\n{message}\n\n" if message else ""
        body = (
            f"# 📸 Snapshot Capture\n\n"
            f"{user_message_section}"
            f"检测到工作区发生变更。\n\n"
            f"### 📝 变更文件摘要:\n```\n{diff_summary}\n```"
        )
        
        # 4. 写入文件
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        filename.write_text(frontmatter + body, "utf-8")
        
        # 5. 创建锚点 Commit
        commit_msg = f"Axon Save: {message}" if message else f"Axon Capture: {current_hash[:7]}"
        parents = [last_commit_hash] if last_commit_hash else []
        new_commit_hash = self.git_db.create_anchor_commit(current_hash, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/axon/history", new_commit_hash)

        # 6. 更新内存状态
        new_node = AxonNode(
            input_tree=input_hash,
            output_tree=current_hash,
            timestamp=timestamp,
            filename=filename,
            node_type="capture",
            content=body
        )
        
        self.history_graph[current_hash] = new_node
        self.current_node = new_node
        
        # 7. 关键：更新 HEAD 指向新的捕获节点
        self._write_head(current_hash)
        
        logger.info(f"✅ 捕获完成，新节点已创建: {filename.name}")
        return new_node

    def create_plan_node(self, input_tree: str, output_tree: str, plan_content: str) -> AxonNode:
        """
        将一次成功的 Plan 执行固化为历史节点。
        """
        if input_tree == output_tree:
            logger.info(f"📝 记录幂等操作节点 (Idempotent Node): {output_tree[:7]}")
        else:
            logger.info(f"📝 正在记录 Plan 节点: {input_tree[:7]} -> {output_tree[:7]}")
        
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d%H%M%S")
        filename = self.history_dir / f"{input_tree}_{output_tree}_{ts_str}.md"
        
        meta = {
            "type": "plan",
            "input_tree": input_tree,
            "output_tree": output_tree
        }
        
        body = f"{plan_content.strip()}\n"
        frontmatter = f"---\n{yaml.dump(meta, sort_keys=False)}---\n\n"
        
        filename.write_text(frontmatter + body, "utf-8")
        
        # Git 锚定逻辑保持不变...
        parent_commit = None
        try:
            res = self.git_db._run(["rev-parse", "refs/axon/history"], check=False)
            if res.returncode == 0:
                parent_commit = res.stdout.strip()
        except Exception: pass
            
        commit_msg = f"Axon Plan: {output_tree[:7]}"
        parents = [parent_commit] if parent_commit else []
        
        new_commit_hash = self.git_db.create_anchor_commit(output_tree, commit_msg, parent_commits=parents)
        self.git_db.update_ref("refs/axon/history", new_commit_hash)
        
        new_node = AxonNode(
            input_tree=input_tree,
            output_tree=output_tree,
            timestamp=timestamp,
            filename=filename,
            node_type="plan",
            content=body
        )
        
        self.history_graph[output_tree] = new_node
        self.current_node = new_node
        
        # 关键：更新 HEAD
        self._write_head(output_tree)
        
        logger.info(f"✅ Plan 已归档: {filename.name}")
        return new_node

    def checkout(self, target_hash: str):
        """
        将工作区重置到指定状态，并更新 HEAD 指针。
        """
        # 1. 执行物理检出
        self.git_db.checkout_tree(target_hash)
        
        # 2. 更新 HEAD 指针
        self._write_head(target_hash)
        
        # 3. 尝试更新内存中的当前节点状态
        # 注意：如果 history_graph 尚未加载，这里不会更新 current_node，
        # 但这通常没问题，因为下一次操作会重新 align
        if target_hash in self.history_graph:
            self.current_node = self.history_graph[target_hash]
        
        logger.info(f"🔄 状态已切换至: {target_hash[:7]}")