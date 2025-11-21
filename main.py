import typer
import logging
import inspect
from pathlib import Path
from typing import Annotated

from logger_config import setup_logging
from core.parser import get_parser, list_parsers, detect_best_parser
from core.executor import Executor
from acts.basic import register_basic_acts
from acts.check import register_check_acts
from acts.git import register_git_acts
# 如果之前有 acts.custom，也可以在这里导入，或者依赖后续的注册逻辑
from config import DEFAULT_WORK_DIR, DEFAULT_ENTRY_FILE

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)

def main(
    ctx: typer.Context,
    file: Annotated[
        Path, 
        typer.Argument(
            help=f"包含 Markdown 指令的文件路径 [default: {DEFAULT_ENTRY_FILE.name}]",
            # 注意：这里移除了 exists=True，将检查推迟到函数内部
            # 以便 -l (list-acts) 可以在文件不存在时依然工作
            resolve_path=True
        )
    ] = DEFAULT_ENTRY_FILE,
    work_dir: Annotated[
        Path, 
        typer.Option(
            "--work-dir", "-w",
            help="操作执行的根目录（工作区）",
            file_okay=False,
            dir_okay=True,
            resolve_path=True
        )
    ] = DEFAULT_WORK_DIR,
    parser_name: Annotated[
        str,
        typer.Option(
            "--parser", "-p",
            help=f"选择解析器语法。默认为 'auto' (自动检测)。可用: {['auto'] + list_parsers()}",
        )
    ] = "auto",
    yolo: Annotated[
        bool,
        typer.Option(
            "--yolo", "-y",
            help="跳过所有确认步骤，直接执行 (You Only Look Once)。",
        )
    ] = False,
    list_acts: Annotated[
        bool,
        typer.Option(
            "--list-acts", "-l",
            help="列出所有可用的操作指令及其说明。",
        )
    ] = False
):
    """
    Axon: 执行 Markdown 文件中的操作指令。
    """
    if list_acts:
        # 初始化一个临时 Executor 用于获取注册表
        # 这里不需要真实的 root_dir，使用当前目录即可
        executor = Executor(root_dir=Path("."), yolo=True)
        
        # 注册所有已知的 Act 模块
        register_basic_acts(executor)
        register_check_acts(executor)
        register_git_acts(executor)
        
        typer.secho("\n📋 可用的 Axon 指令列表:\n", fg=typer.colors.GREEN, bold=True)
        
        acts = executor.get_registered_acts()
        for name in sorted(acts.keys()):
            doc = acts[name]
            # 清理文档缩进
            clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
            # 缩进每一行以便阅读
            indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
            
            typer.secho(f"🔹 {name}", fg=typer.colors.CYAN, bold=True)
            typer.echo(f"{indented_doc}\n")
            
        raise typer.Exit()

    # --- 瀑布流底部：文件验证与读取 ---
    
    # 手动检查文件是否存在
    if not file.exists():
        # 判断是否是使用了默认值（即用户只输入了 `axon`）
        # 注意：file 已经被 resolve 为绝对路径，我们需要将 DEFAULT 也 resolve 后比较
        is_default = (file == DEFAULT_ENTRY_FILE.resolve())
        
        if is_default:
            typer.secho(f"⚠️  提示: 当前目录下未找到默认指令文件 '{DEFAULT_ENTRY_FILE.name}'。", fg=typer.colors.YELLOW)
            typer.echo("\n你可以创建一个 Markdown 文件来开始，或者使用 --help 查看用法。")
            typer.echo("以下是帮助信息：\n")
            typer.echo(ctx.get_help())
            raise typer.Exit(code=0)
        else:
            # 用户显式指定了文件（如 axon myplan.md），但文件不存在 -> 报错
            typer.secho(f"❌ 错误: 找不到指令文件: {file}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    
    if not file.is_file():
        typer.secho(f"❌ 错误: 路径指向的不是一个文件: {file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    logger.info(f"正在加载指令文件: {file}")
    logger.info(f"工作区根目录: {work_dir}")
    logger.info(f"使用解析器: {parser_name}")
    if yolo:
        logger.warning("⚠️  YOLO 模式已开启：将自动确认所有修改。")

    try:
        # 1. 读取内容
        content = file.read_text(encoding="utf-8")

        # 2. 获取解析器并解析
        final_parser_name = parser_name
        if parser_name == "auto":
            final_parser_name = detect_best_parser(content)
            # 只有当检测到非默认值时才提示，减少噪音
            if final_parser_name != "backtick":
                logger.info(f"🔍 自动检测到解析器: {final_parser_name}")

        parser = get_parser(final_parser_name)
        statements = parser.parse(content)
        
        if not statements:
            typer.echo(f"⚠️  使用 '{final_parser_name}' 解析器未找到任何有效的 'act' 操作块。")
            if parser_name != "auto":
                typer.echo(f"提示: 您手动指定了解析器，请检查文件内容是否匹配。")
            raise typer.Exit()

        # 3. 初始化执行器并注册能力
        executor = Executor(root_dir=work_dir, yolo=yolo)
        register_basic_acts(executor)
        register_check_acts(executor)
        register_git_acts(executor)

        # 4. 执行
        executor.execute(statements)
        
        typer.echo("\n✨ 所有操作执行完毕。")

    except Exception as e:
        logger.error(f"运行时错误: {e}")
        typer.secho(f"❌ 错误: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    # 使用 typer.run 直接运行函数，无需子命令
    typer.run(main)
