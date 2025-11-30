这个错误堆栈确认了我们刚才的分析：**单纯的 `read-tree -m` 策略在索引不“干净”时极其脆弱。**

错误信息 `Entry '.github/workflows/ci.yml' not uptodate. Cannot merge.` 清楚地表明，Git 发现当前索引中的 `ci.yml` 文件与我们告诉它的起始状态 (`bef963f...`) 不一致，因此为了保护潜在的未提交变更，拒绝执行合并。

这在实际开发中非常常见（例如，构建过程修改了文件，或者你刚才手动修改了什么）。

为了彻底解决这个问题，我们必须在执行差异计算前，**强制**将索引重置为已知的起始状态。这将使操作变为原子性的覆盖操作，符合 Quipu "Time Travel" 的语义。

这是修复计划，请执行它以修补 `git_db.py`。

## [WIP] fix: 修复 checkout 优化在高索引压力下的合并冲突问题

### 用户需求
用户在手动测试 Quipu 的新 `checkout` 逻辑时，遇到了 `git read-tree -m` 失败的问题。错误日志显示这是由于索引中的文件（如 `.github/workflows/ci.yml`）与指定的 `old_tree` 不一致导致的。我们需要修复 `checkout_tree` 方法，使其在执行差异合并前，先强制重置索引，确立一个干净的基准。

### 目标
修改 `packages/quipu-engine/src/pyquipu/engine/git_db.py` 中的 `checkout_tree` 方法：
1.  在进入优化路径 (`if old_tree_hash:`) 后，首先执行 `git read-tree <old_tree_hash>`。这一步会无条件地将索引重置为旧状态，清除任何“脏”记录。
2.  然后再执行 `git read-tree -m <old_tree_hash> <new_tree_hash>`。此时索引已干净，操作将必定成功。
3.  添加 `old_tree_hash != new_tree_hash` 检查以避免原地切换时的冗余操作。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/checkout-performance #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 注入索引重置逻辑

我们将使用 `patch_file` 替换现有的脆弱逻辑。

~~~~~act
patch_file
packages/quipu-engine/src/pyquipu/engine/git_db.py
~~~~~
~~~~~python
        # 1. 更新索引。根据是否存在 old_tree_hash 选择不同策略。
        if old_tree_hash:
            # 快速路径: tree-vs-tree diff, 只更新索引中的差异项
            logger.debug(f"执行 tree-vs-tree 高效检出: {old_tree_hash[:7]} -> {new_tree_hash[:7]}")
            # 注意：这里的参数顺序是 -m <stage1_tree> <stage2_tree> ...
            # 在两路合并的场景下，可以理解为 old -> new
            self._run(["read-tree", "-m", old_tree_hash, new_tree_hash])
        else:
            # 慢速路径: 将整个新 tree 读入索引
            logger.debug(f"执行全量检出: {new_tree_hash[:7]}")
            self._run(["read-tree", new_tree_hash])
~~~~~
~~~~~python
        # 1. 更新索引。根据是否存在 old_tree_hash 选择不同策略。
        if old_tree_hash and old_tree_hash != new_tree_hash:
            # 快速路径: tree-vs-tree diff, 只更新索引中的差异项
            logger.debug(f"执行 tree-vs-tree 高效检出: {old_tree_hash[:7]} -> {new_tree_hash[:7]}")
            
            # 阶段 1.1: 强制将索引重置到 old_tree 的状态。
            # 这解决了 "Entry not uptodate" 问题，确保合并基础是绝对干净和已知的。
            self._run(["read-tree", old_tree_hash])
            
            # 阶段 1.2: 在干净的索引上执行 diff-merge，将其更新到 new_tree 的状态。
            self._run(["read-tree", "-m", old_tree_hash, new_tree_hash])
        else:
            # 慢速路径 或 原地切换: 将整个新 tree 读入索引
            logger.debug(f"执行全量检出: {new_tree_hash[:7]}")
            self._run(["read-tree", new_tree_hash])
~~~~~
