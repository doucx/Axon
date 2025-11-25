本项目文件较多，为避免超长输出，我将分批次输出修改文件，请按顺序应用。

这些修改主要集中在 `core/models.py` 和 `core/history.py` 中添加摘要提取逻辑，以及彻底重写 `ui/tui.py` 来实现垂直时间轴视图和当前节点自动定位。

## 1. 核心数据模型更新 (core/models.py)

在 `AxonNode` 中添加 `summary` 字段。

~~~act
replace
~~~
~~~path
core/models.py
~~~
~~~old_string
    # 文件主体内容
    content: str = ""
    
    # --- 图遍历字段 (由加载器填充) ---
    parent: Optional[AxonNode] = None
~~~
~~~new_string
    # 文件主体内容
    content: str = ""
    summary: str = "" # 新增：用于 UI 显示的摘要
    
    # --- 图遍历字段 (由加载器填充) ---
    parent: Optional[AxonNode] = None
~~~

## 2. 历史加载与摘要提取 (core/history.py)

添加摘要提取逻辑。这里采用简单的规则：Plan 取第一个 Act 指令，Capture 取备注或默认描述。

~~~act
write_file
~~~
~~~path
core/history.py
~~~
~~~content
import logging
import re
from pathlib import Path
from typing import Dict, Optional
import yaml
from .models import AxonNode
from datetime import datetime

logger = logging.getLogger(__name__)

# 文件名格式: {input_hash}_{output_hash}_{timestamp}.md
# 示例: 000..._a1b2c3..._20231028120000.md
FILENAME_PATTERN = re.compile(
    r"([0-9a-f]{40}|_{40})_([0-9a-f]{40})_(\d{14})\.md"
)
# 注意: input_hash 可能是 40 个下划线，代表创世节点
# Python 3.11+ re.Scanner is much faster, but this is fine for now.

def _parse_frontmatter(text: str) -> tuple[Dict, str]:
    """从 Markdown 文本中分离 YAML frontmatter 和主体内容"""
    if not text.startswith("---"):
        return {}, text
    
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text # 格式不完整

    _, frontmatter_str, content = parts
    try:
        meta = yaml.safe_load(frontmatter_str) or {}
        return meta, content.strip()
    except yaml.YAMLError:
        return {}, text # YAML 解析失败

def _extract_summary(node_type: str, content: str) -> str:
    """提取一个简单的摘要。"""
    content_lines = content.strip().split('\n')
    if not content_lines:
        return "(Empty Node)"
    
    summary = "(No Summary Available)"

    if node_type == 'plan':
        # 寻找第一个 act 指令行
        for line in content_lines:
            line = line.strip()
            if line.startswith(('write_file', 'replace', 'git_commit', 'run_command', 'check_files_exist', 'log_thought', 'delete_file', 'move_file', 'git_add', 'git_init')):
                # 限制长度
                summary = (line[:60] + '...') if len(line) > 60 else line
                break
        
    elif node_type == 'capture':
        # 尝试查找备注
        for line in content_lines:
            if line.startswith("### 💬 备注:"):
                # 备注通常在下一行
                try:
                    idx = content_lines.index(line)
                    remark = content_lines[idx + 1].strip()
                    if remark:
                        summary = (remark[:60] + '...') if len(remark) > 60 else remark
                        break
                except IndexError:
                    pass
        # 如果没有备注，则使用默认描述
        if summary == "(No Summary Available)":
             summary = "Workspace changes captured"
    
    # Fallback to the first non-empty line if nothing specific was found
    if summary == "(No Summary Available)":
        for line in content_lines:
             if line.strip():
                 summary = (line.strip()[:60] + '...') if len(line.strip()) > 60 else line.strip()
                 break
    
    return summary


def load_history_graph(history_dir: Path) -> Dict[str, AxonNode]:
    """
    扫描历史目录，加载所有节点，并构建一个包含父子关系的图。
    返回以 output_tree_hash 为键的节点字典。
    """
    graph: Dict[str, AxonNode] = {}
    if not history_dir.exists():
        return graph

    # --- 第一遍: 加载所有独立的节点 ---
    for file_path in history_dir.glob("*.md"):
        match = FILENAME_PATTERN.match(file_path.name)
        if not match:
            logger.warning(f"跳过格式不匹配的历史文件: {file_path.name}")
            continue
        
        input_hash, output_hash, ts_str = match.groups()
        
        try:
            full_content = file_path.read_text("utf-8")
            meta, body_content = _parse_frontmatter(full_content)
            
            node_type = meta.get("type", "unknown")
            
            node = AxonNode(
                input_tree=input_hash,
                output_tree=output_hash,
                timestamp=datetime.strptime(ts_str, "%Y%m%d%H%M%S"),
                filename=file_path,
                node_type=node_type,
                parent_hint=meta.get("parent_hint"),
                content=body_content,
                summary=_extract_summary(node_type, body_content)
            )
            graph[output_hash] = node
        except Exception as e:
            logger.error(f"加载历史节点失败 {file_path.name}: {e}")

    # --- 第二遍: 连接父子关系 ---
    for node in graph.values():
        # 节点的 input_tree 就是其父节点的 output_tree
        if node.input_tree in graph:
            parent_node = graph[node.input_tree]
            node.parent = parent_node
            parent_node.children.append(node)

    # 为所有节点的子列表按时间排序，确保导航行为一致
    for node in graph.values():
        node.children.sort(key=lambda n: n.timestamp)

    logger.info(f"从 '{history_dir}' 加载并连接了 {len(graph)} 个历史节点。")
    return graph
~~~

## 3. TUI 界面重写 (ui/tui.py)

彻底重写 `ui/tui.py` 以实现时间轴视图、简化标签和自动焦点。

~~~act
write_file
~~~
~~~path
ui/tui.py
~~~
~~~content
import sys
from typing import List, Optional, Dict
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree
from textual.widgets.tree import TreeNode

# 确保能从上级目录导入 core 模块
# Textual App 会在当前目录下启动，所以这行是必要的
# 但是我们不直接在这里依赖 sys.path，而是假设 main.py 已处理
# sys.path.append('..') 
from core.models import AxonNode

class AxonUiApp(App):
    """一个用于浏览 Axon 历史图谱的 Textual 应用，以时间轴模式显示。"""

    BINDINGS = [
        ("q", "quit", "退出"),
        ("c", "checkout_node", "检出选中节点"),
        ("enter", "checkout_node", "检出选中节点"),
    ]
    
    CSS = """
    Tree {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 1;
        border: tall $background-lighten-2;
    }
    """

    def __init__(self, graph_root_nodes: List[AxonNode], current_hash: str):
        super().__init__()
        # graph_root_nodes: 所有的根节点 (没有父节点的节点)
        self.root_nodes = graph_root_nodes
        # current_hash: 当前工作区匹配的哈希，用于自动定位
        self.current_hash = current_hash 

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Tree("📋 Axon 历史时间轴 (↑ 新 ↓ 旧)")
        yield Footer()

    def on_mount(self) -> None:
        """挂载时填充树状组件，并设置焦点。"""
        tree = self.query_one(Tree)
        tree.show_root = False
        
        # 1. 填充 Tree：按时间倒序遍历根节点 (最新在顶部)
        focused_treenode: Optional[TreeNode] = None
        
        # 确保根节点按时间倒序
        sorted_root_nodes = sorted(self.root_nodes, key=lambda n: n.timestamp, reverse=True) 
        
        tree.root.set_label("") # 清空根节点的标签
        
        for root_node in sorted_root_nodes:
            # 递归填充，并更新当前焦点节点
            focus_result = self._populate_tree(tree.root, root_node)
            if focus_result:
                focused_treenode = focus_result

        tree.root.expand_all()
        
        # 2. 设置焦点
        if focused_treenode:
            tree.set_cursor_node(focused_treenode)
            tree.scroll_to_node(focused_treenode)
        
        tree.focus()

    def _populate_tree(self, parent_treenode: TreeNode, axon_node: AxonNode) -> Optional[TreeNode]:
        """递归地从 AxonNode 数据构建 TUI 树，并查找当前节点。"""
        
        # 1. 简化标签
        type_abbr = "P" if axon_node.node_type == "plan" else "C"
        icon = "⚡" if type_abbr == "P" else "📸"
        
        # 标签格式: [P] hash - summary
        label_text = f"{icon} [{type_abbr}] {axon_node.short_hash} - {axon_node.summary}"
        
        # 时间轴：放在 label 的最左边，以节省空间
        time_str = axon_node.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # 结合时间轴和标签。使用 "|" 分隔，模仿多列。
        label = f"{time_str} | {label_text}"

        # 2. 创建节点
        new_treenode = parent_treenode.add(label, data=axon_node)
        
        # 3. 检查是否为当前焦点
        focused_node: Optional[TreeNode] = None
        if axon_node.output_tree == self.current_hash:
            focused_node = new_treenode
            
        # 4. 递归处理子节点
        # 按时间倒序排序 (最新子节点在顶部，与整个时间轴方向一致)
        sorted_children = sorted(axon_node.children, key=lambda n: n.timestamp, reverse=True)
        
        for child in sorted_children:
            result = self._populate_tree(new_treenode, child)
            if result:
                # 如果子分支中找到了焦点，则更新焦点
                focused_node = result

        return focused_node
    
    def action_checkout_node(self) -> None:
        """当用户按下 'c' 或 Enter 键时触发。"""
        tree = self.query_one(Tree)
        
        # 确保当前节点有数据
        if not tree.cursor_node or not tree.cursor_node.data:
            return

        selected_axon_node: AxonNode = tree.cursor_node.data
        
        if selected_axon_node:
            # 退出应用，并返回选中的哈希值给主进程
            self.exit(result=selected_axon_node.output_tree)
~~~

## 4. 主程序更新 (main.py)

更新 `ui` 命令，以获取当前工作区状态并将其传递给 TUI 应用。

~~~act
replace
~~~
~~~path
main.py
~~~
~~~old_string
    root_nodes = [node for node in graph.values() if not node.parent]
    
    app_instance = AxonUiApp(root_nodes)
    selected_hash = app_instance.run()

    if selected_hash:
        typer.secho(f"\n> TUI 请求检出到: {selected_hash[:7]}", err=True)
        _execute_checkout(ctx, graph[selected_hash], work_dir)
~~~
~~~new_string
    # 查找当前状态哈希，用于 TUI 自动定位
    current_hash = engine.git_db.get_tree_hash()
    current_node = graph.get(current_hash)

    if not graph:
        typer.secho("📜 历史记录为空，无需启动 UI。", fg=typer.colors.YELLOW, err=True)
        ctx.exit(0)
        
    root_nodes = [node for node in graph.values() if not node.parent]
    
    # 关键：传递 current_hash，如果找不到匹配节点，则传递空字符串
    app_instance = AxonUiApp(root_nodes, current_hash if current_node else "")
    selected_hash = app_instance.run()

    if selected_hash:
        typer.secho(f"\n> TUI 请求检出到: {selected_hash[:7]}", err=True)
        _execute_checkout(ctx, graph[selected_hash], work_dir)
~~~