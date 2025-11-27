好的，我们继续执行任务 2.4。

我们将在 `GitDB` 模块中添加两个核心方法，`push_quipu_refs` 和 `fetch_quipu_refs`。这两个方法会封装 v1.1 规范中定义的、略显复杂的 Git refspec，为上层 CLI 提供一个简洁、清晰的接口。

## feat: 在 GitDB 中实现 push 和 fetch 核心方法

### 用户需求
根据 `Quipu Sync 功能开发任务列表` (任务 2.4)，需要在 `GitDB` 类中实现两个新的高层方法，用于处理 Quipu 历史记录的推送和拉取。
-   `push_quipu_refs`: 将本地探索分支 (`refs/quipu/local/heads/*`) 推送到远程个人空间 (`refs/quipu/users/<user_id>/heads/*`)。
-   `fetch_quipu_refs`: 将远程个人空间的数据拉取到本地的只读镜像 (`refs/quipu/remotes/<remote>/<user_id>/heads/*`)。

### 评论
这是连接本地 Quipu 引擎与远程仓库的关键一步。通过将复杂的 `refspec` 逻辑封装在 `GitDB` 中，我们不仅避免了在 CLI 层硬编码 Git 命令，还为这些核心操作提供了一个可被集中测试和维护的稳定接口。`--prune` 参数的加入确保了本地与远程状态的整洁同步。

### 目标
1.  在 `packages/quipu-engine/src/quipu/core/git_db.py` 文件中为 `GitDB` 类添加 `push_quipu_refs` 方法。
2.  在同一文件中为 `GitDB` 类添加 `fetch_quipu_refs` 方法。
3.  确保这两个方法正确地构建了 v1.1 规范所需的 refspec，并调用底层的 `_run` 方法执行 `git push` 和 `git fetch`。

### 基本原理
这两个方法是 Quipu Sync v1.1 架构蓝图的直接代码实现。它们利用 Git `refspec` 的强大能力，在本地和远程仓库之间精确地映射引用路径。
-   **Push**: 将所有本地分支头一对一地映射到远程用户专属的目录下，实现了无冲突写入。
-   **Fetch**: 将远程指定用户的所有分支头一对一地映射到本地一个隔离的、只读的镜像目录下，实现了安全的、非侵入性的数据拉取。

### 标签
#intent/build #flow/ready #priority/high 
#comp/engine 
#concept/sync #concept/state 
#scope/core #scope/api 
#ai/instruct
#task/domain/sync #task/object/git-interface #task/action/implementation #task-state/continue

---

### Script

#### Acts 1: 向 `GitDB` 添加同步方法

我们将这两个新方法追加到 `GitDB` 类的末尾。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/git_db.py
~~~~~
~~~~~python
                        "body": parts[4] if len(parts) > 4 else "",
                    }
                )
        return parsed_logs
~~~~~
~~~~~python
                        "body": parts[4] if len(parts) > 4 else "",
                    }
                )
        return parsed_logs

    def push_quipu_refs(self, remote: str, user_id: str):
        """
        将本地 Quipu heads 推送到远程用户专属的命名空间。
        遵循 QDPS v1.1 规范。
        """
        refspec = f"refs/quipu/local/heads/*:refs/quipu/users/{user_id}/heads/*"
        logger.info(f"🚀 Pushing Quipu history to {remote} for user {user_id}...")
        self._run(["push", remote, "--prune", refspec])

    def fetch_quipu_refs(self, remote: str, user_id: str):
        """
        从远程用户专属命名空间拉取 Quipu heads 到本地镜像。
        遵循 QDPS v1.1 规范。
        """
        refspec = f"refs/quipu/users/{user_id}/heads/*:refs/quipu/remotes/{remote}/{user_id}/heads/*"
        logger.info(f"🔍 Fetching Quipu history from {remote} for user {user_id}...")
        self._run(["fetch", remote, "--prune", refspec])
~~~~~

### 下一步建议
底层的 Git 接口已经准备就绪。现在，我们可以开始构建面向用户的 `quipu sync` 命令了。

下一步将是执行任务 **3.1 和 3.2**：在 `quipu-cli` 中创建 `sync` 命令的入口，并开始在 `main.py` 中编排完整的同步流程，调用我们刚刚创建的 `push` 和 `fetch` 方法。
