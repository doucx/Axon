import os
import shutil
import subprocess
import re
import argparse
from pathlib import Path
from typing import List, Optional
import logging
from core.executor import Executor, ExecutionError

logger = logging.getLogger(__name__)

def register(executor: Executor):
    """注册读取与检索操作"""
    executor.register("read_file", _read_file, arg_mode="hybrid")
    # list_files 改为 exclusive 模式以支持 CLI 风格参数并防止误吸入
    executor.register("list_files", _list_files, arg_mode="exclusive")
    # search_files 使用 exclusive 模式，以支持在行内指定参数时忽略后续无关块（流式处理优化）
    executor.register("search_files", _search_files, arg_mode="exclusive")

class SafeArgumentParser(argparse.ArgumentParser):
    """
    覆盖默认的 ArgumentParser 行为：
    1. 错误时抛出 ExecutionError 而不是退出进程。
    2. 禁用自动 help 打印导致的退出。
    """
    def error(self, message):
        raise ExecutionError(f"参数解析错误: {message}")

    def exit(self, status=0, message=None):
        if message:
            raise ExecutionError(message)

def _search_files(executor: Executor, args: List[str]):
    """
    Act: search_files
    Args: pattern [--path PATH]
    说明: 在指定目录下搜索包含 pattern 的文件内容。
    使用 CLI 风格参数解析。
    """
    # 1. 配置参数解析器
    parser = SafeArgumentParser(prog="search_files", add_help=False)
    parser.add_argument("pattern", help="搜索内容的正则表达式")
    parser.add_argument("--path", "-p", default=".", help="搜索的根目录 (默认: 当前目录)")
    
    # 2. 解析参数
    try:
        parsed_args = parser.parse_args(args)
    except ExecutionError:
        # 重新抛出以保持异常类型一致，或者在此处捕获并丰富错误信息
        raise
    except Exception as e:
        raise ExecutionError(f"参数解析异常: {e}")

    pattern = parsed_args.pattern
    search_path_str = parsed_args.path
    
    search_path = executor.resolve_path(search_path_str)

    if not search_path.exists():
        raise ExecutionError(f"搜索路径不存在: {search_path}")

    logger.info(f"🔍 [Search] Pattern: '{pattern}' in {search_path}")

    # --- Strategy 1: Ripgrep (Fastest) ---
    if shutil.which("rg"):
        logger.info("⚡ Using 'rg' (ripgrep) for high-performance search.")
        try:
            # -n: line number
            # --no-heading: format as file:line:content
            # --color=never: plain text
            # -S: smart case (optional, but keep simple for now)
            cmd = ["rg", "-n", "--no-heading", "--color=never", pattern, str(search_path)]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                cwd=executor.root_dir # rg handles absolute paths fine, but good habit
            )
            
            if result.stdout:
                # 结果输出到 STDOUT 以支持管道
                print(result.stdout.strip())
                return
            else:
                logger.info("No matches found (via rg).")
                return

        except Exception as e:
            logger.warning(f"⚠️  ripgrep 执行出错，回退到 Python 搜索: {e}")
            # Fall through to Python strategy
    
    # --- Strategy 2: Python Native (Fallback) ---
    logger.info("🐢 Using Python native search (Fallback).")
    _python_search(search_path, pattern)

def _python_search(start_path: Path, pattern_str: str):
    """Python 原生搜索实现，用于没有安装 rg 的环境"""
    try:
        regex = re.compile(pattern_str)
    except re.error as e:
        raise ExecutionError(f"无效的正则表达式: {pattern_str} ({e})")

    matches = []
    
    # 遍历文件
    for root, dirs, files in os.walk(start_path):
        # 排除常见干扰目录
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.idea', '.vscode', 'node_modules', '.axon'}]
        
        for file in files:
            file_path = Path(root) / file
            try:
                # 逐行读取，避免大文件爆内存
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_idx, line in enumerate(f, 1):
                        if regex.search(line):
                            # 格式化为类似 grep 的输出: file:line:content
                            clean_line = line.strip()
                            # 截断过长的行
                            if len(clean_line) > 200:
                                clean_line = clean_line[:200] + "..."
                            matches.append(f"{file_path}: {line_idx}: {clean_line}")
            except (UnicodeDecodeError, PermissionError):
                continue # 跳过二进制文件或无权限文件

    if matches:
        output = "\n".join(matches)
        # 结果输出到 STDOUT
        print(output)
    else:
        logger.info("No matches found (via Python).")

def _read_file(executor: Executor, args: List[str]):
    """
    Act: read_file
    Args: [path]
    说明: 读取并打印文件内容到日志（stdout）。
    """
    if len(args) < 1:
        raise ExecutionError("read_file 需要至少一个参数: [path]")
    
    raw_path = args[0]
    target_path = executor.resolve_path(raw_path)
    
    if not target_path.exists():
        raise ExecutionError(f"文件不存在: {raw_path}")
    
    if target_path.is_dir():
        raise ExecutionError(f"这是一个目录，请使用 list_files: {raw_path}")

    try:
        content = target_path.read_text(encoding='utf-8')
        logger.info(f"📖 [Read] Reading {target_path.name}...")
        # 纯内容输出到 STDOUT，移除装饰性边框以便于管道处理
        print(content)
    except UnicodeDecodeError:
        logger.error(f"❌ [Read] 无法读取二进制文件或非 UTF-8 文件: {raw_path}")
    except Exception as e:
        raise ExecutionError(f"读取文件失败: {e}")

def _list_files(executor: Executor, args: List[str]):
    """
    Act: list_files
    Args: [path] [--tree]
    说明: 列出目录内容。默认类似 'ls' (仅显示当前层级)，使用 --tree 参数则递归显示树状结构。
    """
    # 1. 配置参数解析器
    parser = SafeArgumentParser(prog="list_files", add_help=False)
    parser.add_argument("path", nargs="?", default=".", help="目标目录")
    parser.add_argument("--tree", "-t", action="store_true", help="以树状结构递归显示")
    
    # 2. 解析参数
    try:
        parsed_args = parser.parse_args(args)
    except Exception as e:
        raise ExecutionError(f"参数解析异常: {e}")

    target_dir = executor.resolve_path(parsed_args.path)
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise ExecutionError(f"目录不存在或不是目录: {target_dir}")

    output_lines = []
    
    # 模式 A: Tree (递归)
    if parsed_args.tree:
        logger.info(f"📂 [List] Directory Tree: {target_dir}")
        # 简单的递归遍历，限制深度防止刷屏
        limit_depth = 3
        base_level = len(target_dir.parts)

        for root, dirs, files in os.walk(target_dir):
            # 排除隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]
            
            root_path = Path(root)
            level = len(root_path.parts) - base_level
            
            if level >= limit_depth:
                del dirs[:] # 停止向下递归
                continue
                
            indent = "  " * level
            # 优化显示：如果不是第一层，增加缩进
            # 第一层(base_level)通常是 target_dir 本身
            output_lines.append(f"{indent}📁 {root_path.name}/")
            for f in files:
                output_lines.append(f"{indent}  📄 {f}")

    # 模式 B: LS (扁平)
    else:
        logger.info(f"📂 [List] Directory: {target_dir}")
        # 获取目录下所有条目
        items = list(target_dir.iterdir())
        # 排序：目录在前，文件在后，字母序
        dirs = sorted([x for x in items if x.is_dir() and not x.name.startswith('.')], key=lambda x: x.name.lower())
        files = sorted([x for x in items if x.is_file() and not x.name.startswith('.')], key=lambda x: x.name.lower())
        
        if not dirs and not files:
            output_lines.append("(Empty directory)")
        
        for d in dirs:
            output_lines.append(f"📁 {d.name}/")
        for f in files:
            output_lines.append(f"📄 {f.name}")

    # 输出结果
    print("\n".join(output_lines))