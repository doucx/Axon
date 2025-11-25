好的，提交和展望如下。

# feat: 提交性能优化与 UI 修复的最终代码

## 用户需求
将近期完成的针对 Git 对象存储的懒加载性能优化，以及相关的 UI 摘要显示问题的修复，提交到版本控制中。

## 评论
本次提交包含了从接口层、实现层、测试层到 UI 层的完整修改，标志着懒加载功能的成功集成。

## 目标
创建一个清晰、完整的 Git 提交，记录本次性能优化的全部工作。

## 基本原理
使用 `git_add` 和 `git_commit` 命令，将所有暂存的变更作为一个原子性提交进行归档。

## 标签
#comp/engine #comp/cli #comp/tests #perf

---

## Script

### Acts 1: 提交代码

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~

~~~~~text
feat(engine): Implement lazy loading for history reader

This commit introduces a lazy loading mechanism for the Git Object
history storage to significantly improve read performance, especially for
commands like `ui` and `log`.

Problem:
The previous implementation eagerly loaded the full `content.md` for every
history node, resulting in N * 3 `git cat-file` subprocess calls for
N nodes. This caused noticeable delays (~2.7s for ~150 nodes).

Solution:
1.  **Interface Change**: Added a `get_node_content(node)` method to the
    `HistoryReader` abstract base class.
2.  **Lazy Loading**: The `GitObjectHistoryReader` now only loads the
    `metadata.json` blob in `load_all_nodes()`. The full `content.md` is
    fetched on-demand via the new `get_node_content` method. This reduces
    initial IO calls by at least 1/3.
3.  **UI Fix**: The TUI was parsing `node.content` to generate summaries. It
    has been updated to prioritize the `node.summary` field, which is
    already available from the metadata, thus avoiding the need to trigger
    a lazy load and fixing a bug where summaries appeared empty.
4.  **Test Adaptation**: Unit and integration tests have been updated to
    reflect the new lazy loading API usage.
~~~~~

---

### 下一步展望

本次性能优化非常成功，它解决了 `git cat-file` 进程开销的核心瓶颈，使得 Git 对象存储在中小规模仓库（几百个节点）下的体验变得流畅。

现在，我们的物理存储层 (L1) 已经健壮且高效，是时候构建逻辑索引层 (L2) 了。

**核心建议：实施 SQLite 缓存层**

这是 `QDPS` 规范蓝图中规划的最终形态，也是解决大规模历史（数千乃至上万节点）性能问题的根本方案。

**工作原理：**
1.  **索引 (Indexing)**: 在 `quipu run`, `quipu save` 等写操作成功后，`Engine` 将新节点的元数据（从 `metadata.json` 解析）写入到一个本地的 `.quipu/cache.sqlite` 文件中。
2.  **查询 (Querying)**: `quipu log`, `quipu ui` 等读操作将**首先**查询 SQLite 数据库。由于数据库索引的存在，获取上千条记录的摘要、类型、时间戳等信息几乎是瞬时的 (毫秒级)。
3.  **补水 (Rehydration)**: 如果 `cache.sqlite` 文件不存在，或者文件中的最新记录与 `refs/quipu/history` 的 HEAD 不一致，系统会自动触发“补水”流程。此时，它会使用我们刚刚优化过的 `GitObjectHistoryReader` 从 Git 历史中读取所有元数据，一次性重建整个 SQLite 缓存。

**带来的优势：**
*   **极致性能**: `ui` 和 `log` 的启动将与历史记录数量无关，实现真正的秒开。
*   **高级查询**: 我们可以轻松实现复杂的查询，例如 `quipu log --type capture --summary-contains "refactor"`，这是单纯 `git log` 难以高效实现的。
*   **数据健壮性**: 缓存文件是可随时丢弃和重建的，Git 依然是唯一的“真理之源”，完全符合我们的核心设计哲学。

我们可以开始设计具体的实现方案，包括数据库 Schema 的最终确定，以及 `Engine` 中“读缓存-写缓存-补水”的逻辑流程。