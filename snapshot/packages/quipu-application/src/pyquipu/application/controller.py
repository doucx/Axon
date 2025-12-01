import logging
import re
from pathlib import Path
from typing import List

from pyquipu.acts import register_core_acts
from pyquipu.engine.state_machine import Engine
from pyquipu.interfaces.exceptions import ExecutionError as CoreExecutionError
from pyquipu.interfaces.exceptions import OperationCancelledError
from pyquipu.interfaces.result import QuipuResult
from pyquipu.runtime.executor import Executor
from pyquipu.runtime.parser import detect_best_parser, get_parser

from pyquipu.application.factory import create_engine
from pyquipu.application.plugin_manager import PluginManager
from pyquipu.common.messaging import bus

logger = logging.getLogger(__name__)


from typing import Callable, List, Optional

# ... (other imports)

ConfirmationHandler = Callable[[List[str], str], bool]


def default_confirmation_handler(diff_lines: List[str], prompt: str) -> bool:
    """A default handler that always cancels to prevent accidental changes."""
    bus.warning("run.error.noConfirmationHandler")
    return False


class QuipuApplication:
    """
    封装了 Quipu 核心业务流程的高层应用对象。
    负责协调 Engine, Parser, Executor。
    """

    def __init__(
        self,
        work_dir: Path,
        yolo: bool = False,
        confirmation_handler: Optional[ConfirmationHandler] = None,
    ):
        self.work_dir = work_dir
        self.yolo = yolo
        self.engine: Engine = create_engine(work_dir)
        self.confirmation_handler = confirmation_handler or default_confirmation_handler
        logger.info(f"Operation boundary set to: {self.work_dir}")

    def _prepare_workspace(self) -> str:
        """
        检查并准备工作区，处理状态漂移。
        返回执行前的 input_tree_hash。
        """
        current_hash = self.engine.git_db.get_tree_hash()

        # 1. 正常 Clean: current_node 存在且与当前 hash 一致
        is_node_clean = (self.engine.current_node is not None) and (
            self.engine.current_node.output_tree == current_hash
        )

        # 2. 创世 Clean: 历史为空 且 当前是空树 (即没有任何文件被追踪)
        EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        is_genesis_clean = (not self.engine.history_graph) and (current_hash == EMPTY_TREE_HASH)

        is_clean = is_node_clean or is_genesis_clean

        if not is_clean:
            self.engine.capture_drift(current_hash)

        if self.engine.current_node:
            return self.engine.current_node.output_tree
        else:
            return current_hash

    def _setup_executor(self) -> Executor:
        """创建、配置并返回一个 Executor 实例，并注入 UI 依赖。"""

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
        """
        执行一个完整的 Plan。
        """
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


def run_quipu(content: str, work_dir: Path, parser_name: str = "auto", yolo: bool = False) -> QuipuResult:
    """
    Quipu 核心业务逻辑的入口包装器。

    实例化并运行 QuipuApplication，捕获所有异常并转化为 QuipuResult。
    确保资源被安全释放。
    """
    app = None
    try:
        app = QuipuApplication(work_dir=work_dir, yolo=yolo)
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
