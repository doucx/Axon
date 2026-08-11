import logging
import subprocess

from needle.pointer import L

from quipu.common.bus import bus
from quipu.spec.protocols.runtime import ActContext
from quipu.spec.protocols.runtime import ExecutorProtocol as Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    executor.register("run_command", _run_command, arg_mode="exclusive")


def _run_command(ctx: ActContext, args: list[str]):
    if len(args) < 1:
        ctx.fail(
            bus.render_to_string(
                L.acts.error.missingArgs, act_name="run_command", count=1, signature="[command_string]"
            )
        )

    command = "\n".join(args)

    warning_msg = f"⚠️  即将执行系统命令:\n  $ {command}\n  (CWD: {ctx.root_dir})"
    ctx.request_confirmation(ctx.root_dir, "System State", warning_msg)

    bus.info(L.acts.shell.info.executing, command=command)

    try:
        result = subprocess.run(command, cwd=ctx.root_dir, shell=True, capture_output=True, text=True)
    except Exception as e:
        ctx.fail(bus.render_to_string(L.acts.shell.error.exception, error=e))
        return

    if result.stdout:
        bus.data(result.stdout.strip())
    if result.stderr:
        bus.warning(L.acts.shell.warning.stderrOutput, output=result.stderr.strip())

    if result.returncode != 0:
        ctx.fail(bus.render_to_string(L.acts.shell.error.failed, code=result.returncode))
