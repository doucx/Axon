from pathlib import Path

import pytest
from quipu.acts.memory import register as register_memory_acts
from quipu.runtime.executor import Executor
from quipu.spec.exceptions import ExecutionError
from quipu.spec.protocols.runtime import ActContext


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
        monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("Disk full")))

        func, _, _ = executor._acts["log_thought"]
        ctx = ActContext(executor)

        with pytest.raises(ExecutionError, match="acts.memory.error.writeFailed"):
            func(ctx, ["content"])
