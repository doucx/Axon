非常抱歉，这是一个经典的异步编程错误。

错误分析

错误 `WorkerError: Unsupported attempt to run a thread worker` 发生的原因是：

在我的代码中：
```python
self.run_worker(
    self._load_content_in_background(node, req_id), # <--- 错误在这里
    thread=True,
    ...
)
```
我**直接调用了** `_load_content_in_background` 方法。这意味着：
1.  该方法在**主 UI 线程**上立即执行了（导致阻塞）。
2.  该方法执行完毕后返回了 `None`。
3.  `run_worker` 实际上接收到的参数是 `None`。
4.  Textual 发现传入的 `work` 既不是协程也不是可调用对象（而是 None），于是抛出了错误。

解决方案

`run_worker` 需要接收一个**可调用对象 (Callable)**，而不是函数调用的结果。

我们需要使用 `functools.partial` 将函数和参数封装成一个可调用对象，然后传给 `run_worker`，让 Textual 在后台线程中去调用它。

## [WIP] fix(cli): 修复 TUI 异步 Worker 启动方式错误

### 用户需求
修复 TUI 中按 `v` 切换视图或加载内容时触发的 `WorkerError`。

### 目标
1.  在 `pyquipu/cli/tui.py` 中引入 `functools.partial`。
2.  修改 `_launch_worker` 方法，使用 `partial` 封装后台任务，而不是直接调用。

### 标签
#intent/fix #flow/ready #priority/critical #comp/cli #concept/ui #task/domain/ui #task/object/tui-async-loader #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 引入 partial 并修正 run_worker 调用

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/tui.py
~~~~~
~~~~~python
import logging
from pathlib import Path
from typing import List, Optional
~~~~~
~~~~~python
import logging
from functools import partial
from pathlib import Path
from typing import List, Optional
~~~~~

~~~~~act
patch_file
packages/quipu-cli/src/pyquipu/cli/tui.py
~~~~~
~~~~~python
    def _launch_worker(self):
        """计时器结束，启动后台 Worker"""
        node = self.view_model.get_selected_node()
        if not node:
            return

        # 1. 生成新的请求 ID
        self._current_request_id += 1
        req_id = self._current_request_id

        # 2. 启动独占 Worker
        # thread=True: 允许执行 I/O 操作
        # exclusive=True: 自动取消同一组中旧的 Worker
        self.run_worker(
            self._load_content_in_background(node, req_id),
            thread=True,
            group="content_loader",
            exclusive=True
        )

    def _load_content_in_background(self, node: QuipuNode, req_id: int):
~~~~~
~~~~~python
    def _launch_worker(self):
        """计时器结束，启动后台 Worker"""
        node = self.view_model.get_selected_node()
        if not node:
            return

        # 1. 生成新的请求 ID
        self._current_request_id += 1
        req_id = self._current_request_id

        # 2. 启动独占 Worker
        # 使用 partial 封装函数和参数，而不是直接调用
        worker_func = partial(self._load_content_in_background, node, req_id)
        
        self.run_worker(
            worker_func,
            thread=True,
            group="content_loader",
            exclusive=True
        )

    def _load_content_in_background(self, node: QuipuNode, req_id: int):
~~~~~
