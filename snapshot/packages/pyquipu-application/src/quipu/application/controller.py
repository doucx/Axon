import logging
import re
from collections.abc import Callable
from pathlib import Path

from quipu.acts import register_core_acts
from quipu.runtime.executor import Executor
from quipu.runtime.parser import detect_best_parser, get_parser
from quipu.spec.constants import EMPTY_TREE_HASH
from quipu.spec.exceptions import ExecutionError as CoreExecutionError
from quipu.spec.exceptions import OperationCancelledError
from quipu.spec.models.execution import QuipuResult
from quipu.spec.protocols.engine import QuipuEngine

from .factory import create_engine
from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)


def get_available_acts(work_dir: Path) -> dict[str, str]:
    # A dummy confirmation handler is used as it's not required for listing.
    # Yolo=True ensures no interactive prompts can be triggered.
    executor = Executor(
        root_dir=work_dir,
        yolo=True,
        confirmation_handler=lambda diff, prompt: True,
    )
    register_core_acts(executor)
    PluginManager().load_from_sources(executor, work_dir)
    return executor.get_registered_acts()


# 定义 ConfirmationHandler 类型别名: (diff_lines, prompt) -> bool
# 注意: Executor 期望如果不确认则抛出异常，或者返回 False (取决于 Executor 实现)。
# 为了保持与 CLI 行为一致，调用方传入的 handler 应该在用户拒绝时抛出 OperationCancelledError。
ConfirmationHandler = Callable[[list[str], str], bool]


class QuipuApplication:
    def __init__(self, work_dir: Path, confirmation_handler: ConfirmationHandler, yolo: bool = False):
        self.work_dir = work_dir
        self.confirmation_handler = confirmation_handler
        self.yolo = yolo
        self.engine: QuipuEngine = create_engine(work_dir)
        logger.info(f"Operation boundary set to: {self.work_dir}")

    def _prepare_workspace(self) -> str:
        current_hash = self.engine.git_db.get_tree_hash()

        # 1. 正常 Clean: current_node 存在且与当前 hash 一致
        is_node_clean = (self.engine.current_node is not None) and (
            self.engine.current_node.output_tree == current_hash
        )

        # 2. 创世 Clean: 历史为空 且 当前是空树 (即没有任何文件被追踪)
        is_genesis_clean = (not self.engine.history_graph) and (current_hash == EMPTY_TREE_HASH)

        is_clean = is_node_clean or is_genesis_clean

        if not is_clean:
            self.engine.capture_drift(current_hash)

        if self.engine.current_node:
            return self.engine.current_node.output_tree
        else:
            return current_hash

    def _setup_executor(self) -> Executor:
        executor = Executor(
            root_dir=self.work_dir,
            yolo=self.yolo,
            confirmation_handler=self.confirmation_handler,
        )

        # 加载核心 acts
        register_core_acts(executor)

        # 加载外部插件
        plugin_manager = PluginManager()
        plugin_manager.load_from_sources(executor, self.work_dir)

        return executor

    def run(self, content: str, parser_name: str) -> QuipuResult:
        # --- Phase 1 & 2: Perception & Decision (Lazy Capture) ---
        input_tree_hash = self._prepare_workspace()

        # --- Phase 3: Action (Execution) ---
        # 3.1 Parser
        final_parser_name = parser_name
        if parser_name == "auto":
            final_parser_name = detect_best_parser(content)
            if final_parser_name != "backtick":
                logger.info(f"🔍 自动检测到解析器: {final_parser_name}")

        parser = get_parser(final_parser_name)
        statements = parser.parse(content)

        if not statements:
            return QuipuResult(
                success=True,  # No failure, just nothing to do
                exit_code=0,
                message="axon.warning.noStatements",
                msg_kwargs={"parser": final_parser_name},
            )

        # 3.2 Executor Setup
        executor = self._setup_executor()

        # 3.3 Execute
        executor.execute(statements)

        # --- Phase 4: Recording (Plan Crystallization) ---
        final_summary = None
        # 优先级 1: 从 Markdown 内容中提取 # 标题
        title_match = re.search(r"^\s*#{1,6}\s+(.*)", content, re.MULTILINE)
        if title_match:
            final_summary = title_match.group(1).strip()
        # 优先级 2: 从第一个 act 指令生成摘要
        elif statements:
            final_summary = executor.summarize_statement(statements[0])

        output_tree_hash = self.engine.git_db.get_tree_hash()

        self.engine.create_plan_node(
            input_tree=input_tree_hash,
            output_tree=output_tree_hash,
            plan_content=content,
            summary_override=final_summary,
        )

        return QuipuResult(success=True, exit_code=0, message="run.success")


def run_quipu(
    content: str,
    work_dir: Path,
    confirmation_handler: ConfirmationHandler,
    parser_name: str = "auto",
    yolo: bool = False,
) -> QuipuResult:
    app = None
    try:
        app = QuipuApplication(work_dir=work_dir, confirmation_handler=confirmation_handler, yolo=yolo)
        return app.run(content=content, parser_name=parser_name)

    except OperationCancelledError as e:
        logger.info(f"🚫 操作已取消: {e}")
        return QuipuResult(
            success=False, exit_code=2, message="run.error.cancelled", msg_kwargs={"error": str(e)}, error=e
        )

    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )

    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
    finally:
        # 确保无论成功或失败，引擎资源都被关闭
        if app and hasattr(app, "engine") and app.engine:
            app.engine.close()


def run_stateless_plan(
    content: str,
    work_dir: Path,
    confirmation_handler: ConfirmationHandler,
    parser_name: str = "auto",
    yolo: bool = False,
) -> QuipuResult:
    try:
        executor = Executor(
            root_dir=work_dir,
            yolo=yolo,
            confirmation_handler=confirmation_handler,
        )
        register_core_acts(executor)
        PluginManager().load_from_sources(executor, work_dir)

        final_parser_name = parser_name
        if parser_name == "auto":
            final_parser_name = detect_best_parser(content)

        parser = get_parser(final_parser_name)
        statements = parser.parse(content)

        if not statements:
            return QuipuResult(
                success=True,
                exit_code=0,
                message="axon.warning.noStatements",
                msg_kwargs={"parser": final_parser_name},
            )

        executor.execute(statements)
        return QuipuResult(success=True, exit_code=0, message="axon.success")

    except CoreExecutionError as e:
        logger.error(f"❌ 操作失败: {e}")
        return QuipuResult(
            success=False, exit_code=1, message="run.error.execution", msg_kwargs={"error": str(e)}, error=e
        )
    except Exception as e:
        logger.error(f"运行时错误: {e}", exc_info=True)
        return QuipuResult(
            success=False, exit_code=1, message="run.error.system", msg_kwargs={"error": str(e)}, error=e
        )
