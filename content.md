# fix: 修复 checkout 误删 .gitignore 文件的行为

## 目标
修复 `quipu checkout` 命令会删除被 `.gitignore` 忽略的文件 (例如 `.envs` 虚拟环境、`o.md`、`uwu` 等) 的问题。

## 基本原理
问题根源在于 `quipu-engine` 模块中与 Git 底层交互的 `git_db.py` 文件。

在 `checkout_tree` 方法中，为了将工作区恢复到目标状态，执行了三个步骤：
1.  `git read-tree`: 将索引更新为目标树的状态。
2.  `git checkout-index`: 从新索引中检出文件。
3.  `git clean`: 清理工作区中多余的文件和目录。

导致问题的正是第三步中的 `git clean` 命令。当前的命令是：
`self._run(["clean", "-dfx", "-e", ".quipu"])`

我们来分析一下参数：
*   `-d`: 同时删除未被追踪的目录。
*   `-f`: 强制执行。
*   `-x`: **这是问题的关键**。这个参数告诉 `git clean` **忽略 `.gitignore` 文件中的规则**，删除所有未被追踪的文件。
*   `-e .quipu`: 从清理操作中排除 `.quipu` 目录，防止系统自毁。

因为使用了 `-x` 参数，Git 清理了所有不属于目标树的文件，包括你在 `.gitignore` 中明确要求保留的文件，例如 `uwu` 和开发环境目录 `.envs`。

解决方案很简单：移除 `-x` 参数。

修改后的命令将是：
`self._run(["clean", "-df", "-e", ".quipu"])`

这样，`git clean` 在执行时会尊重 `.gitignore` 的规则，只删除那些既不属于目标树、也没有被忽略的未追踪文件，从而保护你的本地开发环境和临时文件不被误删。

## 标签
#fix #core #git

---

## Script

### Act 1: 修复 GitDB 中的 checkout_tree 方法

移除 `git clean` 命令中错误的 `-x` 参数，以确保该命令尊重 `.gitignore` 规则。

~~~~~act
replace packages/quipu-engine/src/quipu/core/git_db.py
~~~~~

~~~~~python
        # -d: 目录, -f: 强制, -x: 包含忽略文件
        # -e .quipu: 排除 .quipu 目录，防止自毁
        self._run(["clean", "-dfx", "-e", ".quipu"])
~~~~~

~~~~~python
        # -d: 目录, -f: 强制
        # 移除了 -x 参数，以尊重 .gitignore 规则
        # -e .quipu: 排除 .quipu 目录，防止自毁
        self._run(["clean", "-df", "-e", ".quipu"])
~~~~~