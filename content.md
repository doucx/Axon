# fix-test: Repair failing storage integration tests

## 用户需求
在实现了存储后端的动态选择逻辑后，为其编写的集成测试 (`tests/test_storage_integration.py`) 全部失败了。我需要分析失败的原因并修复相关的代码，确保所有测试用例都能通过。

## 评论
测试失败暴露了一个隐藏的设计缺陷：`Engine` 的构造函数会无条件地创建旧版的文件系统历史目录，这干扰了新存储格式的检测逻辑。此外，测试辅助函数的健壮性不足，未能正确处理 Git 命令在找不到引用时的行为。修复这些问题将使存储层切换的逻辑更加稳健，并提高测试的可靠性。

## 目标
1.  修正 `Engine` 的初始化逻辑，将创建 `.quipu/history/` 目录的职责从 `Engine` 转移到 `FileSystemHistoryWriter`，避免对新项目的存储格式检测造成干扰。
2.  修复 `tests/test_storage_integration.py` 中的 `git_rev_parse` 辅助函数，使其在 Git 引用不存在时能正确返回空字符串，而不是返回引用名称本身。
3.  确保在应用修复后，`test_storage_integration.py` 中的所有测试都能成功通过。

## 基本原理
问题的根源有两个：

1.  **逻辑缺陷**: `Engine.__init__` 中存在 `self.history_dir.mkdir(...)` 的调用。这意味着，即使我们打算为一个新项目使用 `GitObject` 存储，这个方法也会首先创建一个空的 `.quipu/history/` 目录。当后续操作触发第二次 `_setup_engine` 调用时 (例如，`save` 命令)，检测逻辑 `elif (real_root / ".quipu" / "history").exists()` 会被错误地触发，导致系统降级回 `FileSystem` 存储。正确的做法是将目录创建的职责移至 `FileSystemHistoryWriter` 的构造函数中，因为它才是唯一需要这个目录的组件。
2.  **测试脆弱性**: 测试辅助函数 `git_rev_parse` 没有检查 `subprocess.run` 的返回码。当 `git rev-parse <ref>` 命令找不到 `<ref>` 时，它会直接将 `<ref>` 字符串打印到 `stdout` 并以非零状态码退出。由于测试代码没有检查返回码，它错误地将字符串 `"refs/quipu/history"` 当作一个有效的哈希值进行断言，导致了测试失败。我们将通过增加返回码检查来修复这个辅助函数。

通过解决这两个问题，我们可以确保核心逻辑的正确性，并使测试能够准确地验证该逻辑。

## 标签
#comp/engine #comp/cli #concept/history #scope/tests

---

## Script

### Acts 1: 修正 `Engine` 初始化逻辑

我们将目录创建的职责从 `Engine` 转移到 `FileSystemHistoryWriter`。

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/state_machine.py
~~~~~
~~~~~python
        self.history_dir = self.quipu_dir / "history"
        self.head_file = self.quipu_dir / "HEAD"

        self.nav_log_file = self.quipu_dir / "nav_log"
        self.nav_ptr_file = self.quipu_dir / "nav_ptr"

        self.history_dir.mkdir(parents=True, exist_ok=True)

        quipu_gitignore = self.quipu_dir / ".gitignore"
~~~~~
~~~~~python
        self.history_dir = self.quipu_dir / "history"
        self.head_file = self.quipu_dir / "HEAD"

        self.nav_log_file = self.quipu_dir / "nav_log"
        self.nav_ptr_file = self.quipu_dir / "nav_ptr"

        quipu_gitignore = self.quipu_dir / ".gitignore"
~~~~~

~~~~~act
replace
~~~~~
~~~~~path
packages/quipu-engine/src/quipu/core/file_system_storage.py
~~~~~
~~~~~python
    """
    def __init__(self, history_dir: Path):
        self.history_dir = history_dir
~~~~~
~~~~~python
    """
    def __init__(self, history_dir: Path):
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)
~~~~~

### Acts 2: 修复集成测试中的辅助函数

现在，我们修复 `test_storage_integration.py` 中的 `git_rev_parse` 函数，使其能正确处理引用不存在的情况。

~~~~~act
replace
~~~~~
~~~~~path
tests/test_storage_integration.py
~~~~~
~~~~~python
def git_rev_parse(ref: str, cwd: Path) -> str:
    """Helper to get the hash of a git ref."""
    result = subprocess.run(["git", "rev-parse", ref], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip()
~~~~~
~~~~~python
def git_rev_parse(ref: str, cwd: Path) -> str:
    """Helper to get the hash of a git ref."""
    result = subprocess.run(["git", "rev-parse", ref], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
~~~~~