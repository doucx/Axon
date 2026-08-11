from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path


@dataclasses.dataclass
class QuipuNode:
    commit_hash: str
    output_tree: str
    input_tree: str
    timestamp: datetime
    filename: Path
    node_type: str  # "plan" | "capture"
    content: str = ""
    summary: str = ""
    owner_id: str | None = None

    # 图遍历字段（由加载器填充）
    parent: QuipuNode | None = None
    children: list[QuipuNode] = dataclasses.field(default_factory=list)

    @property
    def short_hash(self) -> str:
        return self.output_tree[:7]

    @property
    def siblings(self) -> list[QuipuNode]:
        if not self.parent:
            return [self]
        return self.parent.children
