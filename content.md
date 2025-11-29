## [WIP] test: 修正 `test_pull_only_mode` 中关于本地引用污染的错误断言

### 错误分析
测试 `tests/integration/test_sync_modes.py` 中的 `test_pull_only_mode` 断言 User A 的节点必须出现在 User B 的 `refs/quipu/local/heads/` 中。基于上述分析，这是一个错误的假设。User A 的节点应当只存在于 `refs/quipu/remotes/origin/UserA/heads/` 中，以保持 User B 本地命名空间的洁净，防止后续 Push 操作导致的所有权混淆。

### 用户需求
修正集成测试，使其符合 QDPS (Quipu Data Persistence Standard) 的隔离原则：订阅内容仅存在于 `remotes` 命名空间，不污染 `local` 命名空间。

### 评论
这是一个关键的测试修正，它确立了正确的同步边界。

### 目标
修改 `test_pull_only_mode`，断言 User A 的节点**不在** `local/heads` 中，但**在** `remotes/...` 中。

### 基本原理
Quipu 的 Hydrator (`hydrator.py`) 已经设计为扫描所有 `refs/quipu/`（包括 `remotes`），因此即使不在 `local/heads`，这些节点依然会进入 SQLite 数据库并在 UI 中可见。这是正确的行为。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/sync #scope/core #ai/instruct #task/domain/testing #task/object/sync-test #task/action/correction #task/state/begin

---

### Script

#### Acts 1: 修正测试断言

我们将修改 `test_sync_modes.py`，反转对 `local_refs_b` 的断言逻辑。

~~~~~act
patch_file
tests/integration/test_sync_modes.py
~~~~~
~~~~~python
        # Verify User B's local repo HAS User A's node (in remotes and local)
        local_refs_b = run_git_command(user_b_path, ["for-each-ref"])
        assert f"refs/quipu/remotes/origin/{user_a_id}/heads/{node_a}" in local_refs_b
        assert f"refs/quipu/local/heads/{node_a}" in local_refs_b

        # Verify remote DOES NOT have User B's node
~~~~~
~~~~~python
        # Verify User B's local repo HAS User A's node (in remotes ONLY)
        local_refs_b = run_git_command(user_b_path, ["for-each-ref"])
        assert f"refs/quipu/remotes/origin/{user_a_id}/heads/{node_a}" in local_refs_b
        # Crucial: Foreign nodes should NOT pollute local/heads to prevent re-pushing them as own
        assert f"refs/quipu/local/heads/{node_a}" not in local_refs_b

        # Verify remote DOES NOT have User B's node
~~~~~

### 下一步建议
再次运行 `pytest tests/integration/test_sync_modes.py`。这次应该通过。

---

这是一个极其深刻且关键的指正。你是对的，我之前的提议（将所有订阅用户的引用调和到 `local/heads`）不仅是错误的，而且在架构上是**灾难性**的。

这里是详细的解释：

### 为什么它是灾难性的？

**1. 身份窃取与回环污染 (Identity Hijacking & Loop Pollution)**

`Quipu` 的同步协议（QDPS）基于一个核心假设：**`push` 操作会将 `refs/quipu/local/heads/*` 下的所有内容推送到远程的 `refs/quipu/users/ME/heads/*`。**

如果 `sync` 操作自动将 **协作者 A** 的引用复制到了 **我** 的 `local/heads`：
1.  我执行 `pull`（包含了 A 的数据）。
2.  A 的分支出现在了我的 `local/heads` 中。
3.  我执行 `push`。
4.  **灾难发生**：系统会将 A 的分支作为**我**的数据，推送到**我的**远程用户目录下 (`users/ME/heads`)。

这导致了：
*   **数据重复**：A 的历史现在存在于两个地方（A 的目录和我的目录）。
*   **所有权混淆**：在未来的图谱分析中，很难区分这是我 fork 的分支，还是仅仅是同步造成的垃圾副本。
*   **无限增殖**：如果 B 也同步了我，B 会得到 A 的副本（来自我）和 A 的原件。

**2. 本地工作区污染 (Workspace Pollution)**

`refs/quipu/local/heads` 的语义是“**我的工作台**”。它应该只包含我正在进行的、或我显式保存的状态。
如果订阅了 5 个活跃的协作者，每个协作者有 10 个分支，我的 `local/heads` 会突然多出 50 个我不关心的引用。这会破坏 `git log --branches` 的可用性，也会让 `checkout` 时的自动补全变得不可用。

**3. 破坏修剪逻辑 (Pruning Logic Breakage)**

`pull-prune` 模式旨在删除本地存在但远程已删除的分支。
如果我们将别人的分支放入 `local/heads`，当我对照**我的**远程镜像进行修剪时，这些“别人的分支”会被视为“未在我的远程存在”，从而被立即误删。或者，我们需要编写极其复杂的逻辑来区分哪些 `local` 引用是“原生”的，哪些是“外来”的。

### 正确的架构视图

*   **`refs/quipu/remotes/origin/UserA/...`**: 这是**图书馆**。它是只读的，参考用的。UI 和数据库应该从这里读取数据来展示“别人的工作”。
*   **`refs/quipu/local/heads/...`**: 这是**我的书桌**。只有我创造的，或者我显式决定“借阅”（Checkout/Branch off）的内容才应该在这里。

### 结论

**代码 (`remote.py`) 目前的逻辑（只调和当前用户）其实是正确的。**
**出错的是测试用例 (`test_sync_modes.py`) 的断言。**

该测试错误地假设“Pull 成功”意味着“出现在 `local/heads` 中”。实际上，Pull 成功意味着“出现在 `remotes/...` 中且能被 Hydrator 读取”。

我们需要修改测试，而不是修改代码。

