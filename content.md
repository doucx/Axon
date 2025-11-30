好的，我们将执行这个重构计划。

目标：
1.  **解耦 UI 文案**：将所有 Runtime Acts 中的硬编码错误字符串提取到新的 `acts.json` 资源文件中。
2.  **规范化测试**：通过 Mock `bus.get`，使测试用例断言语义化的 `msg_id`，而不是脆弱的中文文案。
3.  **提升覆盖率**：为 `refactor`, `shell`, `memory` 模块补充完整的测试用例。

### 计划步骤

1.  **资源文件**：创建 `packages/quipu-common/src/pyquipu/common/locales/zh/acts.json`。
2.  **测试基础设施**：修改 `tests/runtime/conftest.py`，配置 Mock Bus 的行为，使其在测试中直接返回 `msg_id`。
3.  **代码重构**：更新所有 `packages/quipu-runtime/src/pyquipu/acts/*.py` 文件，使用 `bus.get()`。
4.  **测试更新与新增**：更新现有测试，并创建新的测试文件。

---

### [WIP] test: 提高 Act 测试覆盖率并重构错误消息

#### 用户需求
1.  消除 Runtime 代码中的硬编码错误字符串，使用 MessageBus 机制。
2.  增加 `refactor`, `shell`, `memory` 等模块的单元测试覆盖率。
3.  确保测试断言针对 `msg_id` 而非具体文本。

#### 目标
1.  创建 `acts.json` 语言包。
2.  重构 7 个 Act 模块 (`basic`, `check`, `git`, `memory`, `read`, `refactor`, `shell`)。
3.  更新/创建对应的测试文件。

#### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/runtime #comp/tests #scope/dx #task/domain/testing #task/object/acts #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 Acts 语言资源包

首先定义所有 Act 可能抛出的错误和提示消息。

~~~~~act
write_file
packages/quipu-common/src/pyquipu/common/locales/zh/acts.json
~~~~~
~~~~~json
{
  "acts.error.missingArgs": "{act_name} 需要至少 {count} 个参数: {signature}",
  
  "acts.basic.error.writePermission": "写入文件失败: 对 '{path}' 的访问权限不足。",
  "acts.basic.error.writeUnknown": "写入文件时发生未知错误: {error}",
  "acts.basic.error.fileNotFound": "文件未找到: {path}",
  "acts.basic.error.readFailed": "读取文件 {path} 失败: {error}",
  "acts.basic.error.patchContentMismatch": "在文件 {path} 中未找到指定的旧文本。\n请确保 Markdown 块中的空格和换行完全匹配。",
  "acts.basic.error.patchPermission": "替换文件内容失败: 对 '{path}' 的访问权限不足。",
  "acts.basic.error.patchUnknown": "更新文件时发生未知错误: {error}",
  "acts.basic.error.appendPermission": "追加文件内容失败: 对 '{path}' 的访问权限不足。",
  "acts.basic.error.appendUnknown": "追加文件时发生未知错误: {error}",
  "acts.basic.success.fileWritten": "✅ [写入] 文件已写入: {path}",
  "acts.basic.success.filePatched": "✅ [更新] 文件内容已更新: {path}",
  "acts.basic.success.fileAppended": "✅ [追加] 内容已追加到: {path}",

  "acts.check.error.filesMissing": "❌ [Check] 以下文件在工作区中未找到:\n{file_list}",
  "acts.check.error.cwdMismatch": "❌ [Check] 工作区目录不匹配!\n  预期: {expected}\n  实际: {actual}",
  "acts.check.success.filesExist": "✅ [Check] 所有指定文件均存在。",
  "acts.check.success.cwdMatched": "✅ [Check] 工作区目录匹配: {path}",

  "acts.git.error.cmdFailed": "Git 命令执行失败: git {args}\n错误信息: {error}",
  "acts.git.error.gitNotFound": "未找到 git 命令，请确保系统已安装 Git。",
  "acts.git.success.initialized": "✅ [Git] 已初始化仓库: {path}",
  "acts.git.success.added": "✅ [Git] 已添加文件: {targets}",
  "acts.git.success.committed": "✅ [Git] 提交成功: {message}",
  "acts.git.warning.repoExists": "⚠️  Git 仓库已存在，跳过初始化。",
  "acts.git.warning.commitSkipped": "⚠️  [Git] 没有暂存的更改，跳过提交。",

  "acts.memory.error.missingContent": "log_thought 需要内容参数",
  "acts.memory.error.writeFailed": "无法写入记忆文件: {error}",
  "acts.memory.success.thoughtLogged": "🧠 [记忆] 思维已记录到 .quipu/memory.md",

  "acts.read.error.pathNotFound": "搜索路径不存在: {path}",
  "acts.read.error.invalidRegex": "无效的正则表达式: {pattern} ({error})",
  "acts.read.error.targetNotFound": "文件不存在: {path}",
  "acts.read.error.targetIsDir": "这是一个目录，请使用 list_files: {path}",
  "acts.read.error.readFailed": "读取文件失败: {error}",
  "acts.read.error.dirNotFound": "目录不存在或不是目录: {path}",
  "acts.read.info.searching": "🔍 [搜索] 模式: '{pattern}' 于 {path}",
  "acts.read.info.useRipgrep": "⚡ 使用 'rg' (ripgrep) 进行高性能搜索。",
  "acts.read.info.noMatchRipgrep": "🤷 (rg) 未找到匹配项。",
  "acts.read.info.usePythonSearch": "🐢 使用原生 Python 搜索 (回退模式)。",
  "acts.read.info.noMatchPython": "🤷 (Python) 未找到匹配项。",
  "acts.read.info.readingFile": "📖 [读取] 正在读取 {filename}...",
  "acts.read.info.listingTree": "📂 [列表] 目录树: {path}",
  "acts.read.info.listingDir": "📂 [列表] 目录内容: {path}",
  "acts.read.warning.ripgrepFailed": "⚠️  ripgrep 执行出错，回退到 Python 搜索: {error}",
  "acts.read.error.binaryOrEncoding": "❌ [读取] 无法读取二进制或非 UTF-8 文件: {filename}",

  "acts.refactor.error.srcNotFound": "源文件不存在: {path}",
  "acts.refactor.error.movePermission": "移动/重命名失败: 权限不足。源: '{src}', 目标: '{dest}'",
  "acts.refactor.error.moveUnknown": "移动/重命名时发生未知错误: {error}",
  "acts.refactor.error.deletePermission": "删除失败: 对 '{path}' 的访问权限不足。",
  "acts.refactor.error.deleteUnknown": "删除时发生未知错误: {error}",
  "acts.refactor.warning.deleteSkipped": "⚠️  文件不存在，跳过删除: {path}",
  "acts.refactor.success.moved": "✅ [移动] 已移动/重命名: {source} -> {destination}",
  "acts.refactor.success.deleted": "🗑️  [删除] 已删除: {path}",

  "acts.shell.error.failed": "命令执行失败 (Code {code})",
  "acts.shell.error.exception": "Shell 执行异常: {error}",
  "acts.shell.info.executing": "🚀 [Shell] 正在执行: {command}",
  "acts.shell.warning.stderrOutput": "⚠️  [Stderr]:\n{output}"
}
~~~~~

#### Acts 2: 更新测试配置

为了让测试能够断言 `msg_id`，我们需要配置 `mock_runtime_bus.get` 的副作用，使其直接返回 `msg_id`。这样 `ctx.fail(bus.get("my.error"))` 在测试中就等同于 `ctx.fail("my.error")`。

~~~~~act
write_file
tests/runtime/conftest.py
~~~~~
~~~~~python
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pyquipu.acts.basic import register as register_basic_acts
from pyquipu.runtime.executor import Executor


@pytest.fixture(autouse=True)
def mock_runtime_bus(monkeypatch):
    """
    自动 patch 所有 runtime 模块中导入的 'bus' 实例。
    """
    m_bus = MagicMock()
    
    # 关键修改：让 bus.get 返回传入的 msg_id，方便测试断言语义
    m_bus.get.side_effect = lambda msg_id, **kwargs: msg_id
    
    patch_targets = [
        "pyquipu.runtime.executor.bus",
        "pyquipu.runtime.plugin_loader.bus",
        "pyquipu.acts.basic.bus",
        "pyquipu.acts.check.bus",
        "pyquipu.acts.git.bus",
        "pyquipu.acts.memory.bus",
        "pyquipu.acts.read.bus",
        "pyquipu.acts.refactor.bus",
        "pyquipu.acts.shell.bus",
    ]
    for target in patch_targets:
        monkeypatch.setattr(target, m_bus, raising=False)
    return m_bus


@pytest.fixture
def executor(tmp_path: Path) -> Executor:
    """
    为运行时测试提供一个隔离的 Executor 实例。
    - 在独立的临时目录 (tmp_path) 中运行。
    - 自动注册基础 acts。
    - 默认以非交互模式 (yolo=True) 运行。
    """
    instance = Executor(root_dir=tmp_path, yolo=True)
    register_basic_acts(instance)
    return instance


@pytest.fixture
def isolated_vault(executor: Executor) -> Path:
    """
    提供 Executor 实例的根工作目录。
    """
    return executor.root_dir
~~~~~

#### Acts 3: 重构 Basic Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/basic.py
~~~~~
~~~~~python
import logging
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册基础文件系统操作"""
    executor.register("write_file", _write_file, arg_mode="hybrid", summarizer=_summarize_write)
    executor.register("patch_file", _patch_file, arg_mode="hybrid", summarizer=_summarize_patch_file)
    executor.register("append_file", _append_file, arg_mode="hybrid", summarizer=_summarize_append)
    executor.register("end", _end, arg_mode="hybrid")
    executor.register("echo", _echo, arg_mode="hybrid")


def _summarize_write(args: List[str], contexts: List[str]) -> str:
    path = args[0] if args else (contexts[0] if contexts else "???")
    return f"Write: {path}"


def _summarize_patch_file(args: List[str], contexts: List[str]) -> str:
    path = args[0] if args else (contexts[0] if contexts else "???")
    return f"patch_file in: {path}"


def _summarize_append(args: List[str], contexts: List[str]) -> str:
    path = args[0] if args else (contexts[0] if contexts else "???")
    return f"Append to: {path}"


def _end(ctx: ActContext, args: List[str]):
    pass


def _echo(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="echo", count=1, signature="[content]"))

    bus.data(args[0])


def _write_file(ctx: ActContext, args: List[str]):
    if len(args) < 2:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="write_file", count=2, signature="[path, content]"))

    raw_path = args[0]
    content = args[1]

    target_path = ctx.resolve_path(raw_path)

    old_content = ""
    if target_path.exists():
        try:
            old_content = target_path.read_text(encoding="utf-8")
        except Exception:
            old_content = "[Binary or Unreadable]"

    ctx.request_confirmation(target_path, old_content, content)

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    except PermissionError:
        ctx.fail(bus.get("acts.basic.error.writePermission", path=raw_path))
    except Exception as e:
        ctx.fail(bus.get("acts.basic.error.writeUnknown", error=e))

    bus.success("acts.basic.success.fileWritten", path=target_path.relative_to(ctx.root_dir))


def _patch_file(ctx: ActContext, args: List[str]):
    if len(args) < 3:
        ctx.fail(
            bus.get("acts.error.missingArgs", act_name="patch_file", count=3, signature="[path, old_string, new_string]")
        )

    raw_path, old_str, new_str = args[0], args[1], args[2]
    target_path = ctx.resolve_path(raw_path)

    if not target_path.exists():
        ctx.fail(bus.get("acts.basic.error.fileNotFound", path=raw_path))

    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception as e:
        ctx.fail(bus.get("acts.basic.error.readFailed", path=raw_path, error=e))

    if old_str not in content:
        ctx.fail(bus.get("acts.basic.error.patchContentMismatch", path=raw_path))

    new_content = content.replace(old_str, new_str, 1)

    ctx.request_confirmation(target_path, content, new_content)

    try:
        target_path.write_text(new_content, encoding="utf-8")
    except PermissionError:
        ctx.fail(bus.get("acts.basic.error.patchPermission", path=raw_path))
    except Exception as e:
        ctx.fail(bus.get("acts.basic.error.patchUnknown", error=e))

    bus.success("acts.basic.success.filePatched", path=target_path.relative_to(ctx.root_dir))


def _append_file(ctx: ActContext, args: List[str]):
    if len(args) < 2:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="append_file", count=2, signature="[path, content]"))

    raw_path, content_to_append = args[0], args[1]
    target_path = ctx.resolve_path(raw_path)

    if not target_path.exists():
        ctx.fail(bus.get("acts.basic.error.fileNotFound", path=raw_path))

    old_content = ""
    try:
        old_content = target_path.read_text(encoding="utf-8")
    except Exception:
        old_content = "[Binary or Unreadable]"

    new_content = old_content + content_to_append

    ctx.request_confirmation(target_path, old_content, new_content)

    try:
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(content_to_append)
    except PermissionError:
        ctx.fail(bus.get("acts.basic.error.appendPermission", path=raw_path))
    except Exception as e:
        ctx.fail(bus.get("acts.basic.error.appendUnknown", error=e))

    bus.success("acts.basic.success.fileAppended", path=target_path.relative_to(ctx.root_dir))
~~~~~

#### Acts 4: 重构 Check Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/check.py
~~~~~
~~~~~python
import logging
import os
from pathlib import Path
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册检查类操作"""
    executor.register("check_files_exist", _check_files_exist, arg_mode="exclusive")
    executor.register("check_cwd_match", _check_cwd_match, arg_mode="exclusive")


def _check_files_exist(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="check_files_exist", count=1, signature="[file_list_string]"))

    raw_files = args[0].strip().split("\n")
    missing_files = []

    for raw_path in raw_files:
        clean_path = raw_path.strip()
        if not clean_path:
            continue

        target_path = ctx.resolve_path(clean_path)
        if not target_path.exists():
            missing_files.append(clean_path)

    if missing_files:
        file_list_str = "\n".join(f"  - {f}" for f in missing_files)
        ctx.fail(bus.get("acts.check.error.filesMissing", file_list=file_list_str))

    bus.success("acts.check.success.filesExist")


def _check_cwd_match(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(
            bus.get("acts.error.missingArgs", act_name="check_cwd_match", count=1, signature="[expected_absolute_path]")
        )

    expected_path_str = args[0].strip()
    current_root = ctx.root_dir.resolve()
    expected_path = Path(os.path.expanduser(expected_path_str)).resolve()

    if current_root != expected_path:
        ctx.fail(bus.get("acts.check.error.cwdMismatch", expected=expected_path, actual=current_root))

    bus.success("acts.check.success.cwdMatched", path=current_root)
~~~~~

#### Acts 5: 重构 Git Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/git.py
~~~~~
~~~~~python
import logging
import os
import subprocess
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册 Git 相关操作"""
    executor.register("git_init", _git_init, arg_mode="exclusive")
    executor.register("git_add", _git_add, arg_mode="exclusive")
    executor.register("git_commit", _git_commit, arg_mode="block_only", summarizer=_summarize_commit)
    executor.register("git_status", _git_status, arg_mode="exclusive")


def _summarize_commit(args: List[str], contexts: List[str]) -> str:
    msg = contexts[0] if contexts else "No message"
    summary = (msg[:50] + "...") if len(msg) > 50 else msg
    return f"Git Commit: {summary}"


def _run_git_cmd(ctx: ActContext, cmd_args: List[str]) -> str:
    """在工作区根目录执行 git 命令的辅助函数。"""
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    try:
        result = subprocess.run(
            ["git"] + cmd_args, cwd=ctx.root_dir, capture_output=True, text=True, check=True, env=env
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        ctx.fail(bus.get("acts.git.error.cmdFailed", args=" ".join(cmd_args), error=error_msg))
    except FileNotFoundError:
        ctx.fail(bus.get("acts.git.error.gitNotFound"))
    return ""


def _git_init(ctx: ActContext, args: List[str]):
    if (ctx.root_dir / ".git").exists():
        bus.warning("acts.git.warning.repoExists")
        return
    _run_git_cmd(ctx, ["init"])
    bus.success("acts.git.success.initialized", path=ctx.root_dir)


def _git_add(ctx: ActContext, args: List[str]):
    targets = []
    if not args:
        targets = ["."]
    else:
        for arg in args:
            targets.extend(arg.split())
    if not targets:
        targets = ["."]
    _run_git_cmd(ctx, ["add"] + targets)
    bus.success("acts.git.success.added", targets=targets)


def _git_commit(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="git_commit", count=1, signature="[message]"))

    message = args[0]

    status = _run_git_cmd(ctx, ["status", "--porcelain"])
    if not status:
        bus.warning("acts.git.warning.commitSkipped")
        return

    ctx.request_confirmation(ctx.root_dir / ".git", "Staged Changes", f"Commit Message: {message}")

    _run_git_cmd(ctx, ["commit", "-m", message])
    bus.success("acts.git.success.committed", message=message)


def _git_status(ctx: ActContext, args: List[str]):
    status = _run_git_cmd(ctx, ["status"])
    bus.data(status)
~~~~~

#### Acts 6: 重构 Memory Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/memory.py
~~~~~
~~~~~python
import logging
from datetime import datetime
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册记忆与日志操作"""
    executor.register("log_thought", _log_thought, arg_mode="block_only")


def _log_thought(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.memory.error.missingContent"))

    content = args[0]

    memory_dir = ctx.root_dir / ".quipu"
    memory_dir.mkdir(exist_ok=True)

    memory_file = memory_dir / "memory.md"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## [{timestamp}]\n{content}\n"

    try:
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        ctx.fail(bus.get("acts.memory.error.writeFailed", error=e))

    bus.success("acts.memory.success.thoughtLogged")
~~~~~

#### Acts 7: 重构 Read Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/read.py
~~~~~
~~~~~python
import argparse
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.exceptions import ExecutionError
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册读取与检索操作"""
    executor.register("read_file", _read_file, arg_mode="hybrid")
    executor.register("list_files", _list_files, arg_mode="exclusive")
    executor.register("search_files", _search_files, arg_mode="exclusive")


class SafeArgumentParser(argparse.ArgumentParser):
    """覆盖 ArgumentParser 以抛出 ExecutionError。"""

    def error(self, message):
        raise ExecutionError(f"参数解析错误: {message}")

    def exit(self, status=0, message=None):
        if message:
            raise ExecutionError(message)


def _search_files(ctx: ActContext, args: List[str]):
    parser = SafeArgumentParser(prog="search_files", add_help=False)
    parser.add_argument("pattern", help="搜索内容的正则表达式")
    parser.add_argument("--path", "-p", default=".", help="搜索的根目录")

    try:
        parsed_args = parser.parse_args(args)
    except ExecutionError as e:
        ctx.fail(str(e))
    except Exception as e:
        ctx.fail(f"参数解析异常: {e}")

    search_path = ctx.resolve_path(parsed_args.path)
    if not search_path.exists():
        ctx.fail(bus.get("acts.read.error.pathNotFound", path=search_path))

    bus.info("acts.read.info.searching", pattern=parsed_args.pattern, path=search_path)

    if shutil.which("rg"):
        bus.info("acts.read.info.useRipgrep")
        try:
            cmd = ["rg", "-n", "--no-heading", "--color=never", parsed_args.pattern, str(search_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=ctx.root_dir)
            if result.stdout:
                bus.data(result.stdout.strip())
            else:
                bus.info("acts.read.info.noMatchRipgrep")
            return
        except Exception as e:
            bus.warning("acts.read.warning.ripgrepFailed", error=str(e))

    bus.info("acts.read.info.usePythonSearch")
    _python_search(ctx, search_path, parsed_args.pattern)


def _python_search(ctx: ActContext, start_path: Path, pattern_str: str):
    try:
        regex = re.compile(pattern_str)
    except re.error as e:
        ctx.fail(bus.get("acts.read.error.invalidRegex", pattern=pattern_str, error=e))

    matches = []
    for root, dirs, files in os.walk(start_path):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".idea", ".vscode", "node_modules", ".quipu"}]
        for file in files:
            file_path = Path(root) / file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            clean_line = line.strip()
                            relative_path = file_path.relative_to(ctx.root_dir)
                            matches.append(f"{relative_path}:{i}:{clean_line[:200]}")
            except (UnicodeDecodeError, PermissionError):
                continue

    if matches:
        bus.data("\n".join(matches))
    else:
        bus.info("acts.read.info.noMatchPython")


def _read_file(ctx: ActContext, args: List[str]):
    if not args:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="read_file", count=1, signature="[path]"))

    target_path = ctx.resolve_path(args[0])
    if not target_path.exists():
        ctx.fail(bus.get("acts.read.error.targetNotFound", path=args[0]))
    if target_path.is_dir():
        ctx.fail(bus.get("acts.read.error.targetIsDir", path=args[0]))

    try:
        content = target_path.read_text(encoding="utf-8")
        bus.info("acts.read.info.readingFile", filename=target_path.name)
        bus.data(content)
    except UnicodeDecodeError:
        bus.error("acts.read.error.binaryOrEncoding", filename=args[0])
    except Exception as e:
        ctx.fail(bus.get("acts.read.error.readFailed", error=e))


def _list_files(ctx: ActContext, args: List[str]):
    parser = SafeArgumentParser(prog="list_files", add_help=False)
    parser.add_argument("path", nargs="?", default=".", help="目标目录")
    parser.add_argument("--tree", "-t", action="store_true", help="以树状结构递归显示")

    try:
        parsed_args = parser.parse_args(args)
    except Exception as e:
        ctx.fail(f"参数解析异常: {e}")

    target_dir = ctx.resolve_path(parsed_args.path)
    if not target_dir.is_dir():
        ctx.fail(bus.get("acts.read.error.dirNotFound", path=target_dir))

    output = []
    if parsed_args.tree:
        bus.info("acts.read.info.listingTree", path=target_dir)
        for path_object in sorted(target_dir.rglob("*")):
            if ".git" in path_object.parts or ".quipu" in path_object.parts:
                continue
            depth = len(path_object.relative_to(target_dir).parts) - 1
            indent = "    " * depth
            output.append(f"{indent}└── {path_object.name}{'/' if path_object.is_dir() else ''}")
    else:
        bus.info("acts.read.info.listingDir", path=target_dir)
        items = sorted(list(target_dir.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
        for item in items:
            if item.name.startswith("."):
                continue
            output.append(f"📁 {item.name}/" if item.is_dir() else f"📄 {item.name}")

    if not output:
        output.append("(Empty directory)")
    bus.data("\n".join(output))
~~~~~

#### Acts 8: 重构 Refactor Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/refactor.py
~~~~~
~~~~~python
import logging
import shutil
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册重构类操作"""
    executor.register("move_file", _move_file, arg_mode="hybrid")
    executor.register("delete_file", _delete_file, arg_mode="exclusive")


def _move_file(ctx: ActContext, args: List[str]):
    if len(args) < 2:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="move_file", count=2, signature="[src, dest]"))

    src_raw, dest_raw = args[0], args[1]
    src_path = ctx.resolve_path(src_raw)
    dest_path = ctx.resolve_path(dest_raw)

    if not src_path.exists():
        ctx.fail(bus.get("acts.refactor.error.srcNotFound", path=src_raw))

    msg = f"Move: {src_raw} -> {dest_raw}"
    ctx.request_confirmation(src_path, "Source Exists", msg)

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
    except PermissionError:
        ctx.fail(bus.get("acts.refactor.error.movePermission", src=src_raw, dest=dest_raw))
    except Exception as e:
        ctx.fail(bus.get("acts.refactor.error.moveUnknown", error=e))
    bus.success("acts.refactor.success.moved", source=src_raw, destination=dest_raw)


def _delete_file(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="delete_file", count=1, signature="[path]"))

    raw_path = args[0]
    target_path = ctx.resolve_path(raw_path)

    if not target_path.exists():
        bus.warning("acts.refactor.warning.deleteSkipped", path=raw_path)
        return

    file_type = "目录 (递归删除!)" if target_path.is_dir() else "文件"
    warning = f"🚨 正在删除{file_type}: {target_path}"

    ctx.request_confirmation(target_path, "EXISTING CONTENT", warning)

    try:
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
    except PermissionError:
        ctx.fail(bus.get("acts.refactor.error.deletePermission", path=raw_path))
    except Exception as e:
        ctx.fail(bus.get("acts.refactor.error.deleteUnknown", error=e))

    bus.success("acts.refactor.success.deleted", path=raw_path)
~~~~~

#### Acts 9: 重构 Shell Acts

~~~~~act
write_file
packages/quipu-runtime/src/pyquipu/acts/shell.py
~~~~~
~~~~~python
import logging
import subprocess
from typing import List

from pyquipu.common.messaging import bus
from pyquipu.interfaces.types import ActContext, Executor

logger = logging.getLogger(__name__)


def register(executor: Executor):
    """注册 Shell 相关操作"""
    executor.register("run_command", _run_command, arg_mode="exclusive")


def _run_command(ctx: ActContext, args: List[str]):
    if len(args) < 1:
        ctx.fail(bus.get("acts.error.missingArgs", act_name="run_command", count=1, signature="[command_string]"))

    command = " ".join(args)

    warning_msg = f"⚠️  即将执行系统命令:\n  $ {command}\n  (CWD: {ctx.root_dir})"
    ctx.request_confirmation(ctx.root_dir, "System State", warning_msg)

    bus.info("acts.shell.info.executing", command=command)

    try:
        result = subprocess.run(command, cwd=ctx.root_dir, shell=True, capture_output=True, text=True)

        if result.stdout:
            bus.data(result.stdout.strip())
        if result.stderr:
            bus.warning("acts.shell.warning.stderrOutput", output=result.stderr.strip())

        if result.returncode != 0:
            ctx.fail(bus.get("acts.shell.error.failed", code=result.returncode))

    except Exception as e:
        ctx.fail(bus.get("acts.shell.error.exception", error=e))
~~~~~

#### Acts 10: 更新 test_check.py

~~~~~act
write_file
tests/runtime/acts/test_check.py
~~~~~
~~~~~python
from pathlib import Path

import pytest
from pyquipu.acts.check import register as register_check_acts
from pyquipu.interfaces.exceptions import ExecutionError
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import Executor


class TestCheckActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        """自动为每个测试注册 check acts"""
        register_check_acts(executor)

    def test_check_files_exist_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        (isolated_vault / "config.json").touch()
        (isolated_vault / "src").mkdir()
        (isolated_vault / "src/main.py").touch()

        file_list = "config.json\nsrc/main.py"
        func, _, _ = executor._acts["check_files_exist"]
        ctx = ActContext(executor)
        func(ctx, [file_list])

        mock_runtime_bus.success.assert_called_with("acts.check.success.filesExist")

    def test_check_files_exist_fail(self, executor: Executor, isolated_vault: Path):
        (isolated_vault / "exists.txt").touch()
        file_list = "exists.txt\nmissing.txt"

        # 断言 msg_id
        with pytest.raises(ExecutionError, match="acts.check.error.filesMissing"):
            func, _, _ = executor._acts["check_files_exist"]
            ctx = ActContext(executor)
            func(ctx, [file_list])

    def test_check_cwd_match_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        real_path = str(isolated_vault.resolve())
        func, _, _ = executor._acts["check_cwd_match"]
        ctx = ActContext(executor)
        func(ctx, [real_path])

        mock_runtime_bus.success.assert_called_with("acts.check.success.cwdMatched", path=isolated_vault.resolve())

    def test_check_cwd_match_fail(self, executor: Executor):
        wrong_path = "/this/path/does/not/exist"

        with pytest.raises(ExecutionError, match="acts.check.error.cwdMismatch"):
            func, _, _ = executor._acts["check_cwd_match"]
            ctx = ActContext(executor)
            func(ctx, [wrong_path])
~~~~~

#### Acts 11: 更新 test_read.py

~~~~~act
write_file
tests/runtime/acts/test_read.py
~~~~~
~~~~~python
import shutil
from pathlib import Path

import pytest
from pyquipu.acts.read import register as register_read_acts
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import ExecutionError, Executor


class TestReadActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        register_read_acts(executor)

    def test_search_python_fallback(self, executor: Executor, isolated_vault: Path, monkeypatch, mock_runtime_bus):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        target_file = isolated_vault / "config.py"
        target_file.write_text('SECRET_KEY = "123456"', encoding="utf-8")
        (isolated_vault / "readme.md").write_text("Nothing here", encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["SECRET_KEY"])

        mock_runtime_bus.info.assert_any_call("acts.read.info.usePythonSearch")

        # 验证数据输出
        assert mock_runtime_bus.data.called
        data_out = mock_runtime_bus.data.call_args[0][0]
        assert "config.py" in data_out
        assert 'SECRET_KEY = "123456"' in data_out

    @pytest.mark.skipif(not shutil.which("rg"), reason="Ripgrep (rg) 未安装，跳过集成测试")
    def test_search_with_ripgrep(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        (isolated_vault / "main.rs").write_text('fn main() { println!("Hello Quipu"); }', encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["println!"])

        mock_runtime_bus.info.assert_any_call("acts.read.info.useRipgrep")

        assert mock_runtime_bus.data.called
        data_out = mock_runtime_bus.data.call_args[0][0]
        assert "main.rs" in data_out
        assert 'println!("Hello Quipu")' in data_out

    def test_search_scoped_path(self, executor: Executor, isolated_vault: Path, monkeypatch, mock_runtime_bus):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        (isolated_vault / "target.txt").write_text("target_function", encoding="utf-8")
        src_dir = isolated_vault / "src"
        src_dir.mkdir()
        (src_dir / "inner.txt").write_text("target_function", encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["target_function", "--path", "src"])

        assert mock_runtime_bus.data.called
        stdout = mock_runtime_bus.data.call_args[0][0]

        # After the fix, the path should be relative to the root
        assert str(Path("src") / "inner.txt") in stdout
        assert "target.txt" not in stdout

    def test_search_no_match(self, executor: Executor, isolated_vault: Path, monkeypatch, mock_runtime_bus):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        (isolated_vault / "file.txt").write_text("some content", encoding="utf-8")

        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        search_func(ctx, ["non_existent_pattern"])

        mock_runtime_bus.info.assert_called_with("acts.read.info.noMatchPython")

    def test_search_binary_file_resilience(self, executor: Executor, isolated_vault: Path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda x: None)
        binary_file = isolated_vault / "data.bin"
        binary_file.write_bytes(b"\x80\x81\xff")
        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        try:
            search_func(ctx, ["pattern"])
        except Exception as e:
            pytest.fail(f"搜索过程因二进制文件崩溃: {e}")

    def test_search_args_error(self, executor: Executor):
        search_func, _, _ = executor._acts["search_files"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError) as exc:
            search_func(ctx, ["pattern", "--unknown-flag"])
        assert "参数解析错误" in str(exc.value)

    def test_read_file_not_found(self, executor: Executor):
        func, _, _ = executor._acts["read_file"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.read.error.targetNotFound"):
            func(ctx, ["ghost.txt"])

    def test_read_file_is_dir(self, executor: Executor, isolated_vault: Path):
        (isolated_vault / "subdir").mkdir()
        func, _, _ = executor._acts["read_file"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.read.error.targetIsDir"):
            func(ctx, ["subdir"])
~~~~~

#### Acts 12: 新增 test_refactor.py

~~~~~act
write_file
tests/runtime/acts/test_refactor.py
~~~~~
~~~~~python
from pathlib import Path

import pytest
from pyquipu.acts.refactor import register as register_refactor_acts
from pyquipu.interfaces.exceptions import ExecutionError
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import Executor


class TestRefactorActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        register_refactor_acts(executor)

    def test_move_file_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        src = isolated_vault / "old.txt"
        src.write_text("content")
        dest = isolated_vault / "new.txt"

        func, _, _ = executor._acts["move_file"]
        ctx = ActContext(executor)
        func(ctx, ["old.txt", "new.txt"])

        assert not src.exists()
        assert dest.exists()
        assert dest.read_text() == "content"
        mock_runtime_bus.success.assert_called_with("acts.refactor.success.moved", source="old.txt", destination="new.txt")

    def test_move_file_src_not_found(self, executor: Executor):
        func, _, _ = executor._acts["move_file"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.refactor.error.srcNotFound"):
            func(ctx, ["missing.txt", "dest.txt"])

    def test_move_file_permission_error(self, executor: Executor, isolated_vault: Path, monkeypatch):
        src = isolated_vault / "locked.txt"
        src.touch()
        import shutil

        def mock_move(*args):
            raise PermissionError("Access denied")

        monkeypatch.setattr(shutil, "move", mock_move)

        func, _, _ = executor._acts["move_file"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.refactor.error.movePermission"):
            func(ctx, ["locked.txt", "dest.txt"])

    def test_delete_file_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        target = isolated_vault / "trash.txt"
        target.touch()

        func, _, _ = executor._acts["delete_file"]
        ctx = ActContext(executor)
        func(ctx, ["trash.txt"])

        assert not target.exists()
        mock_runtime_bus.success.assert_called_with("acts.refactor.success.deleted", path="trash.txt")

    def test_delete_dir_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        target_dir = isolated_vault / "trash_dir"
        target_dir.mkdir()
        (target_dir / "file.txt").touch()

        func, _, _ = executor._acts["delete_file"]
        ctx = ActContext(executor)
        func(ctx, ["trash_dir"])

        assert not target_dir.exists()
        mock_runtime_bus.success.assert_called_with("acts.refactor.success.deleted", path="trash_dir")

    def test_delete_skipped(self, executor: Executor, mock_runtime_bus):
        func, _, _ = executor._acts["delete_file"]
        ctx = ActContext(executor)
        func(ctx, ["non_existent.txt"])

        mock_runtime_bus.warning.assert_called_with("acts.refactor.warning.deleteSkipped", path="non_existent.txt")
~~~~~

#### Acts 13: 新增 test_shell.py

~~~~~act
write_file
tests/runtime/acts/test_shell.py
~~~~~
~~~~~python
from pathlib import Path
import subprocess
import pytest
from pyquipu.acts.shell import register as register_shell_acts
from pyquipu.interfaces.exceptions import ExecutionError
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import Executor


class TestShellActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        register_shell_acts(executor)

    def test_run_command_success(self, executor: Executor, mock_runtime_bus):
        func, _, _ = executor._acts["run_command"]
        ctx = ActContext(executor)
        func(ctx, ["echo 'Hello Shell'"])

        mock_runtime_bus.info.assert_called_with("acts.shell.info.executing", command="echo 'Hello Shell'")
        mock_runtime_bus.data.assert_called_with("Hello Shell")

    def test_run_command_failure(self, executor: Executor, mock_runtime_bus):
        func, _, _ = executor._acts["run_command"]
        ctx = ActContext(executor)
        
        # 验证失败返回码
        with pytest.raises(ExecutionError, match="acts.shell.error.failed"):
            func(ctx, ["exit 1"])

    def test_run_command_stderr(self, executor: Executor, mock_runtime_bus):
        # 构造一个向 stderr 输出的命令
        cmd = "python3 -c \"import sys; print('error msg', file=sys.stderr)\""
        
        func, _, _ = executor._acts["run_command"]
        ctx = ActContext(executor)
        func(ctx, [cmd])

        # 检查是否捕获了 warning
        assert mock_runtime_bus.warning.called
        args, kwargs = mock_runtime_bus.warning.call_args
        assert args[0] == "acts.shell.warning.stderrOutput"
        assert "error msg" in kwargs["output"]

    def test_run_command_missing_args(self, executor: Executor):
        func, _, _ = executor._acts["run_command"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.error.missingArgs"):
            func(ctx, [])
~~~~~

#### Acts 14: 新增 test_memory.py

~~~~~act
write_file
tests/runtime/acts/test_memory.py
~~~~~
~~~~~python
from pathlib import Path

import pytest
from pyquipu.acts.memory import register as register_memory_acts
from pyquipu.interfaces.exceptions import ExecutionError
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import Executor


class TestMemoryActs:
    @pytest.fixture(autouse=True)
    def setup_executor(self, executor: Executor):
        register_memory_acts(executor)

    def test_log_thought_success(self, executor: Executor, isolated_vault: Path, mock_runtime_bus):
        func, _, _ = executor._acts["log_thought"]
        ctx = ActContext(executor)
        func(ctx, ["Thinking process..."])

        memory_file = isolated_vault / ".quipu" / "memory.md"
        assert memory_file.exists()
        content = memory_file.read_text(encoding="utf-8")
        assert "Thinking process..." in content
        assert "## [" in content

        mock_runtime_bus.success.assert_called_with("acts.memory.success.thoughtLogged")

    def test_log_thought_missing_args(self, executor: Executor):
        func, _, _ = executor._acts["log_thought"]
        ctx = ActContext(executor)
        with pytest.raises(ExecutionError, match="acts.memory.error.missingContent"):
            func(ctx, [])

    def test_log_thought_write_error(self, executor: Executor, isolated_vault: Path, monkeypatch):
        # 模拟 open 失败
        monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(IOError("Disk full")))

        func, _, _ = executor._acts["log_thought"]
        ctx = ActContext(executor)
        
        with pytest.raises(ExecutionError, match="acts.memory.error.writeFailed"):
            func(ctx, ["content"])
~~~~~

#### Acts 15: 更新 test_parser_and_basic_acts.py

~~~~~act
write_file
tests/runtime/test_parser_and_basic_acts.py
~~~~~
~~~~~python
from pathlib import Path

import pytest
from pyquipu.interfaces.types import ActContext
from pyquipu.runtime.executor import ExecutionError, Executor
from pyquipu.runtime.parser import BacktickParser, TildeParser, get_parser


class TestParser:
    def test_backtick_parser(self):
        md = """
```act
write_file
```
```path
test.txt
```
```content
hello
```
"""
        parser = BacktickParser()
        stmts = parser.parse(md)
        assert len(stmts) == 1
        assert stmts[0]["act"] == "write_file"
        assert stmts[0]["contexts"][0].strip() == "test.txt"

    def test_end_block(self):
        md = """
```act
op1
```
```arg1
val1
```
```act
end
```
```arg2
ignored_val
```
```act
op2
```
```arg3
val2
```
"""
        parser = BacktickParser()
        stmts = parser.parse(md)
        assert len(stmts) == 3
        assert stmts[0]["act"] == "op1"
        assert len(stmts[0]["contexts"]) == 1
        assert stmts[0]["contexts"][0].strip() == "val1"
        assert stmts[2]["act"] == "op2"
        assert stmts[2]["contexts"][0].strip() == "val2"

    def test_tilde_parser(self):
        md = """
~~~act
write_file
~~~
~~~path
markdown_guide.md
~~~
~~~markdown
Here is how you write code:
```python
print("hello")
```
~~~
"""
        parser = TildeParser()
        stmts = parser.parse(md)
        assert len(stmts) == 1
        assert stmts[0]["act"] == "write_file"
        content = stmts[0]["contexts"][1]
        assert "```python" in content

    def test_factory(self):
        assert isinstance(get_parser("backtick"), BacktickParser)
        assert isinstance(get_parser("tilde"), TildeParser)
        with pytest.raises(ValueError):
            get_parser("unknown")


class TestBasicActs:
    def test_write_file(self, executor: Executor, isolated_vault: Path):
        contexts = ["docs/readme.md", "# Hello"]
        write_func, _, _ = executor._acts["write_file"]
        ctx = ActContext(executor)
        write_func(ctx, contexts)

        expected_file = isolated_vault / "docs/readme.md"
        assert expected_file.exists()
        assert expected_file.read_text(encoding="utf-8") == "# Hello"

    def test_patch_file_text(self, executor: Executor, isolated_vault: Path):
        f = isolated_vault / "main.py"
        f.write_text('print("Hello World")', encoding="utf-8")

        patch_file_func, _, _ = executor._acts["patch_file"]
        ctx = ActContext(executor)
        patch_file_func(ctx, ["main.py", 'print("Hello World")', 'print("Hello AI")'])

        assert f.read_text(encoding="utf-8") == 'print("Hello AI")'

    def test_patch_file_fail_not_found(self, executor: Executor, isolated_vault: Path):
        f = isolated_vault / "wrong.txt"
        f.write_text("AAA", encoding="utf-8")

        patch_file_func, _, _ = executor._acts["patch_file"]
        ctx = ActContext(executor)

        with pytest.raises(ExecutionError, match="acts.basic.error.patchContentMismatch"):
            patch_file_func(ctx, ["wrong.txt", "BBB", "CCC"])

    def test_append_file(self, executor: Executor, isolated_vault: Path):
        f = isolated_vault / "log.txt"
        f.write_text("Line 1\n", encoding="utf-8")

        append_func, _, _ = executor._acts["append_file"]
        ctx = ActContext(executor)
        append_func(ctx, ["log.txt", "Line 2"])

        assert f.read_text(encoding="utf-8") == "Line 1\nLine 2"

    def test_append_fail_not_found(self, executor: Executor):
        append_func, _, _ = executor._acts["append_file"]
        ctx = ActContext(executor)

        with pytest.raises(ExecutionError, match="acts.basic.error.fileNotFound"):
            append_func(ctx, ["ghost.txt", "content"])


class TestHybridArgs:
    # These tests use executor.execute(), which correctly creates the context,
    # so they don't need changes.
    def test_inline_write_file(self, executor: Executor, isolated_vault: Path):
        stmts = [{"act": "write_file inline.txt", "contexts": ["Inline Content"]}]
        executor.execute(stmts)
        f = isolated_vault / "inline.txt"
        assert f.read_text(encoding="utf-8") == "Inline Content"

    def test_inline_quoted_args(self, executor: Executor, isolated_vault: Path):
        stmts = [{"act": 'write_file "name with spaces.txt"', "contexts": ["Hello"]}]
        executor.execute(stmts)
        f = isolated_vault / "name with spaces.txt"
        assert f.exists()

    def test_mixed_git_commit(self, executor: Executor):
        called_args = []

        def mock_commit(ctx, args):
            called_args.extend(args)

        executor.register("mock_commit", mock_commit)
        stmts = [{"act": 'mock_commit -m "fix bug"', "contexts": []}]
        executor.execute(stmts)
        assert called_args == ["-m", "fix bug"]

    def test_act_parsing_error(self, executor: Executor):
        stmts = [{"act": 'write_file "unclosed string', "contexts": []}]
        with pytest.raises(ExecutionError) as exc:
            executor.execute(stmts)
        assert "Error parsing Act command line" in str(exc.value)
~~~~~

### 下一步建议
1.  **运行测试**：执行 `pytest tests/runtime/` 验证所有 Act 的重构是否成功。
2.  **覆盖率检查**：检查 `tests/runtime/acts/` 目录下的覆盖率报告，确保 `refactor.py` 和 `shell.py` 的覆盖率显著提升。
3.  **CI 集成**：确认这些更改不会影响集成测试（虽然我们主要是内部重构，但 `ExecutionError` 的内容变化可能会影响到那些断言错误消息的集成测试，如果有的话）。
