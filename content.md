# fix-cli-checkout-subprocess 修复 TUI checkout 子进程调用错误

## 目标
修复 `quipu ui` 界面中执行检出操作时，因 `subprocess` 调用方式不当导致的 `ImportError`，确保子进程能正确识别包结构并执行相对导入。

## 基本原理
当前 `_execute_checkout` 函数使用 `[sys.executable, __file__, ...]` 启动子进程。这会导致 `main.py` 被作为顶级脚本直接执行，从而破坏了包的层级结构上下文，使得 `from .logger_config import ...` 等相对导入语句失败。

将调用方式修改为 `[sys.executable, "-m", "quipu.cli.main", ...]` 可以确保 `main.py` 作为模块被加载，从而保留包上下文，使相对导入正常工作。

## 标签
#fix #cli #subprocess

---

## Script

### Act 1: 修正 subprocess 模块调用方式

修改 `packages/quipu-cli/src/quipu/cli/main.py`，将直接文件执行改为模块执行。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/main.py
~~~~~

~~~~~python
    result = subprocess.run(
        [sys.executable, __file__, "checkout", target_node.output_tree, "--work-dir", str(work_dir), "--force"],
        capture_output=True, text=True
    )
~~~~~

~~~~~python
    result = subprocess.run(
        [sys.executable, "-m", "quipu.cli.main", "checkout", target_node.output_tree, "--work-dir", str(work_dir), "--force"],
        capture_output=True, text=True
    )
~~~~~