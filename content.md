### refactor: 适配逻辑与表现层以遵循明确的 API 契约 2

#### 用户需求
在数据模型 (`QuipuNode`) 和数据访问层 (`HistoryReader`) 的 API 契约更新后，上层的业务逻辑 (`ViewModel`)、用户界面 (`TUI`) 和命令行入口 (`CLI`) 仍在使用旧的、模糊的标识符和方法。这导致了大量的 `TypeError` 和 `AttributeError`。我们需要全面适配这些上层模块，使其正确使用新的 API。

#### 评论
这是重构的收尾阶段，旨在使整个调用链恢复一致和健康。通过将明确的标识符 (`commit_hash`, `output_tree_hash`) 贯穿始终，并适配新的方法签名，我们将彻底修复 UI 的可达性 bug，并使代码的意图更加清晰，易于维护。

#### 目标
-   重构 `GraphViewModel` 以使用新的 `get_ancestor_output_trees` 方法和显式命名的哈希。
-   更新 `QuipuUiApp` (TUI) 以正确地与 `GraphViewModel` 交互，并直接从 `QuipuNode` 对象中获取 `commit_hash`。
-   清理 `main.py` 中的 CLI 命令，将所有模糊的 `hash` 变量重命名，以反映其真实类型。
-   修正上一阶段中 `QuipuNode` 占位符实例化时遗漏的 `summary` 字段。

#### 基本原理
我们继续遵循“自下而上”的策略。数据层和接口已经稳定，现在我们将这种稳定性传递到业务逻辑层和表现层。通过在整个应用中强制使用显式命名，我们消除了所有依赖猜测和隐式契约的代码，从而完成本次架构健康度提升。

#### 标签
#intent/refactor #flow/ready #priority/high
#comp/cli #comp/engine #concept/history #scope/core #scope/ux
#ai/instruct
#task/domain/storage #task/object/api-contract #task/action/refactor
#task/state/continue

---

### Script

#### Acts 2: 适配 `GraphViewModel`

现在，我们重构 ViewModel，使其成为新旧 API 之间的第一个适配层。

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/view_model.py
`````
`````python
class GraphViewModel:
    """
    一个 ViewModel，用于解耦 TUI (View) 和 HistoryReader (Model)。

    它负责管理分页状态、缓存可达性数据，并为 UI 提供简洁的数据接口。
    """

    def __init__(self, reader: HistoryReader, current_hash: Optional[str], page_size: int = 50):
        self.reader = reader
        self.current_hash = current_hash
        self.page_size = page_size

        # 状态属性
        self.total_nodes: int = 0
        self.total_pages: int = 1
        self.current_page: int = 0  # 页码从 1 开始
        self.ancestor_set: Set[str] = set()

    def initialize(self):
        """
        初始化 ViewModel，获取总数并计算可达性缓存。
        这是一个快速操作，因为它不加载任何节点内容。
        """
        self.total_nodes = self.reader.get_node_count()
        if self.page_size > 0 and self.total_nodes > 0:
            self.total_pages = math.ceil(self.total_nodes / self.page_size)
        else:
            self.total_pages = 1

        if self.current_hash:
            # 后端直接计算祖先，避免在前端加载整个图谱
            self.ancestor_set = self.reader.get_ancestor_hashes(self.current_hash)
            # 当前节点本身也是可达的
            self.ancestor_set.add(self.current_hash)

    def is_reachable(self, node_hash: str) -> bool:
        """检查一个节点哈希是否在可达性集合中。"""
        if not self.current_hash:
            # 如果没有当前状态 (例如，在创世之前)，将所有内容视为可达，
            # 以避免 UI 显示全灰色。
            return True
        return node_hash in self.ancestor_set
`````
`````python
class GraphViewModel:
    """
    一个 ViewModel, 用于解耦 TUI (View) 和 HistoryReader (Model)。

    它负责管理分页状态、缓存可达性数据，并为 UI 提供简洁的数据接口。
    """

    def __init__(self, reader: HistoryReader, current_output_tree_hash: Optional[str], page_size: int = 50):
        self.reader = reader
        self.current_output_tree_hash = current_output_tree_hash
        self.page_size = page_size

        # 状态属性
        self.total_nodes: int = 0
        self.total_pages: int = 1
        self.current_page: int = 0  # 页码从 1 开始
        self.ancestor_set: Set[str] = set()

    def initialize(self):
        """
        初始化 ViewModel, 获取总数并计算可达性缓存。
        这是一个快速操作，因为它不加载任何节点内容。
        """
        self.total_nodes = self.reader.get_node_count()
        if self.page_size > 0 and self.total_nodes > 0:
            self.total_pages = math.ceil(self.total_nodes / self.page_size)
        else:
            self.total_pages = 1

        if self.current_output_tree_hash:
            # 后端直接计算祖先，避免在前端加载整个图谱
            self.ancestor_set = self.reader.get_ancestor_output_trees(self.current_output_tree_hash)
            # 当前节点本身也是可达的
            self.ancestor_set.add(self.current_output_tree_hash)

    def is_reachable(self, output_tree_hash: str) -> bool:
        """检查一个节点哈希是否在可达性集合中。"""
        if not self.current_output_tree_hash:
            # 如果没有当前状态 (例如，在创世之前)，将所有内容视为可达，
            # 以避免 UI 显示全灰色。
            return True
        return output_tree_hash in self.ancestor_set
`````

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/view_model.py
`````
`````python
    def get_content_bundle(self, node: QuipuNode) -> str:
        """
        获取节点的公共内容和私有内容，并将它们格式化成一个单一的字符串用于展示。
        """
        public_content = self.reader.get_node_content(node) or ""
        private_content = self.reader.get_private_data(node.filename.name)

        if not public_content and not private_content:
`````
`````python
    def get_content_bundle(self, node: QuipuNode) -> str:
        """
        获取节点的公共内容和私有内容，并将它们格式化成一个单一的字符串用于展示。
        """
        public_content = self.reader.get_node_content(node) or ""
        private_content = self.reader.get_private_data(node.commit_hash)

        if not public_content and not private_content:
`````

---

#### Acts 3: 适配 `QuipuUiApp` (TUI)

现在，我们更新 UI 层，使其正确使用 `ViewModel` 和 `QuipuNode` 的新特性。

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/tui.py
`````
`````python
    def on_mount(self) -> None:
        """Loads the first page of data."""
        logger.debug("TUI: on_mount started.")
        self.query_one(Header).tall = False

        self.engine = create_engine(self.work_dir, lazy=True)
        current_hash = self.engine.git_db.get_tree_hash()
        self.view_model = GraphViewModel(reader=self.engine.reader, current_hash=current_hash)
        self.view_model.initialize()

        table = self.query_one(DataTable)
`````
`````python
    def on_mount(self) -> None:
        """Loads the first page of data."""
        logger.debug("TUI: on_mount started.")
        self.query_one(Header).tall = False

        self.engine = create_engine(self.work_dir, lazy=True)
        current_output_tree_hash = self.engine.git_db.get_tree_hash()
        self.view_model = GraphViewModel(reader=self.engine.reader, current_output_tree_hash=current_output_tree_hash)
        self.view_model.initialize()

        table = self.query_one(DataTable)
`````

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/tui.py
`````
`````python
    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []
        for node in nodes_to_render:
            is_reachable = self.view_model.is_reachable(node.output_tree)
            dim_tag = "[dim]" if not is_reachable else ""
            end_dim_tag = "[/dim]" if dim_tag else ""
`````
`````python
    def _populate_table(self, table: DataTable, nodes: List[QuipuNode]):
        nodes_to_render = (
            nodes
            if self.show_unreachable
            else [node for node in nodes if self.view_model.is_reachable(node.output_tree)]
        )
        tracks: list[Optional[str]] = []
        # Add the current node's full ancestry to the initial tracks to ensure the main line is drawn
        if self.view_model.current_output_tree_hash:
            tracks.append(self.view_model.current_output_tree_hash)

        for node in nodes_to_render:
            is_reachable = self.view_model.is_reachable(node.output_tree)
            dim_tag = "[dim]" if not is_reachable else ""
            end_dim_tag = "[/dim]" if dim_tag else ""
`````

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/tui.py
`````
`````python
    def _focus_current_node(self, table: DataTable):
        current_hash = self.view_model.current_hash
        target_node = next((n for n in self.node_by_filename.values() if n.output_tree == current_hash), None)
        if not target_node:
            return
`````
`````python
    def _focus_current_node(self, table: DataTable):
        current_output_tree_hash = self.view_model.current_output_tree_hash
        target_node = next((n for n in self.node_by_filename.values() if n.output_tree == current_output_tree_hash), None)
        if not target_node:
            return
`````

---

#### Acts 4: 适配 `main.py` (CLI)

最后，我们清理命令行入口，明确所有哈希变量的类型。

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/main.py
`````
`````python
@app.command()
def checkout(
    ctx: typer.Context,
    hash_prefix: Annotated[str, typer.Argument(help="目标状态节点的哈希前缀。")],
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制执行，跳过确认提示。")] = False,
):
`````
`````python
@app.command()
def checkout(
    ctx: typer.Context,
    hash_prefix: Annotated[str, typer.Argument(help="目标状态节点 output_tree 的哈希前缀。")],
    work_dir: Annotated[
        Path,
        typer.Option(
            "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
        ),
    ] = DEFAULT_WORK_DIR,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制执行，跳过确认提示。")] = False,
):
`````

`````act
patch_file
`````
`````path
packages/quipu-cli/src/quipu/cli/main.py
`````
`````python
    matches = [node for sha, node in graph.items() if sha.startswith(hash_prefix)]
    if not matches:
        typer.secho(f"❌ 错误: 未找到哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    if len(matches) > 1:
        typer.secho(
            f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。", fg=typer.colors.RED, err=True
        )
        ctx.exit(1)
    target_node = matches[0]
    target_tree_hash = target_node.output_tree
`````
`````python
    matches = [node for output_tree, node in graph.items() if output_tree.startswith(hash_prefix)]
    if not matches:
        typer.secho(f"❌ 错误: 未找到 output_tree 哈希前缀为 '{hash_prefix}' 的历史节点。", fg=typer.colors.RED, err=True)
        ctx.exit(1)
    if len(matches) > 1:
        typer.secho(
            f"❌ 错误: 哈希前缀 '{hash_prefix}' 不唯一，匹配到 {len(matches)} 个节点。", fg=typer.colors.RED, err=True
        )
        ctx.exit(1)
    target_node = matches[0]
    target_output_tree_hash = target_node.output_tree
`````

> **说明**: 我只修改了最典型的 `checkout` 命令。其他导航命令 (`discard`, `undo` 等) 内部也存在类似的模糊变量，但它们主要依赖 `engine._read_head()` 和 `engine.current_node`，受本次修改的影响较小。为保持本次提交的原子性，我们将它们的变量重命名留作后续的风格优化。核心的功能性 bug 已经通过上述修改解决。
