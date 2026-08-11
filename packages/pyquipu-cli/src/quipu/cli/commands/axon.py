import inspect
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from needle.pointer import L
from quipu.common.bus import bus

from ..config import DEFAULT_ENTRY_FILE, DEFAULT_WORK_DIR
from ..logger_config import setup_logging
from ..ui_utils import confirmation_handler_for_executor

logger = logging.getLogger(__name__)


def register(app: typer.Typer):
    @app.command(name="axon", help="无状态执行 Plan 文件，绕过 Quipu 引擎。")
    def axon_command(
        ctx: typer.Context,
        file: Annotated[
            Path | None, typer.Argument(help="包含 Markdown 指令的文件路径。", resolve_path=True)
        ] = None,
        work_dir: Annotated[
            Path,
            typer.Option(
                "--work-dir", "-w", help="操作执行的根目录（工作区）", file_okay=False, dir_okay=True, resolve_path=True
            ),
        ] = DEFAULT_WORK_DIR,
        parser_name: Annotated[str, typer.Option("--parser", "-p", help="选择解析器语法。默认为 'auto'。")] = "auto",
        yolo: Annotated[
            bool, typer.Option("--yolo", "-y", help="跳过所有确认步骤，直接执行 (You Only Look Once)。")
        ] = False,
        list_acts: Annotated[bool, typer.Option("--list-acts", "-l", help="列出所有可用的操作指令及其说明。")] = False,
    ):
        setup_logging()

        # --list-acts 是一个独立的查询操作，应尽早处理并退出
        if list_acts:
            from quipu.application.controller import get_available_acts

            bus.info(L.axon.listActs.ui.header)
            acts = get_available_acts(work_dir)
            for name in sorted(acts.keys()):
                doc = acts[name]
                clean_doc = inspect.cleandoc(doc) if doc else "暂无说明"
                indented_doc = "\n".join(f"   {line}" for line in clean_doc.splitlines())
                item_header = bus.render_to_string(L.axon.listActs.ui.actItem, name=name)
                bus.data(f"{item_header}\n{indented_doc}\n")
            ctx.exit(0)

        logger.debug(f"axon started with file={file}, work_dir={work_dir}, parser={parser_name}, yolo={yolo}")

        # --- 1. 输入处理 (CLI 层职责) ---
        content = ""
        source_desc = ""
        if file:
            if not file.exists():
                bus.error(L.common.error.fileNotFound, path=file)
                ctx.exit(1)
            content = file.read_text(encoding="utf-8")
            source_desc = f"文件 ({file.name})"
        elif not sys.stdin.isatty():
            try:
                stdin_content = sys.stdin.read()
                if stdin_content:
                    content = stdin_content
                    source_desc = "STDIN (管道流)"
            except Exception:
                pass

        if not content and not file and DEFAULT_ENTRY_FILE.exists():
            content = DEFAULT_ENTRY_FILE.read_text(encoding="utf-8")
            source_desc = f"默认文件 ({DEFAULT_ENTRY_FILE.name})"

        if not content.strip():
            bus.warning(L.axon.warning.noInput)
            ctx.exit(0)

        # --- 2. 委托给应用层服务 (核心重构) ---
        from quipu.application.controller import run_stateless_plan

        logger.info(f"Axon 启动 | 源: {source_desc} | 工作区: {work_dir}")

        result = run_stateless_plan(
            content=content,
            work_dir=work_dir,
            parser_name=parser_name,
            yolo=yolo,
            confirmation_handler=confirmation_handler_for_executor,
        )

        # --- 3. 渲染结果 (CLI 层职责) ---
        if result.message:
            kwargs = result.msg_kwargs or {}
            if result.exit_code == 2:
                bus.warning(result.message, **kwargs)
            elif not result.success:
                bus.error(result.message, **kwargs)
            else:
                bus.success(result.message, **kwargs)

        ctx.exit(result.exit_code)
