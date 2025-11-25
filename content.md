# fix(cli): correct genesis state detection [修复创世状态检测逻辑]

## 用户需求
在重构 `controller.py` 时引入了一个逻辑错误：当项目处于“创世状态”（即没有历史记录且 Git 仓库为空）时，系统错误地将其判定为“脏”状态（Dirty），从而触发了一次不必要的 `capture_drift` 操作。这导致在测试 `test_uses_filesystem_storage_on_legacy_project` 中生成了多余的历史文件，致使测试失败。

## 评论
这是一个典型的边界条件处理错误。在旧逻辑中，`align()` 方法返回的枚举值 `"CLEAN"` 涵盖了创世状态。而在重构后的布尔逻辑中，单纯检查 `current_node` 是否存在是不够的，因为创世状态下 `current_node` 确实为 `None`，但这并不代表状态漂移。

## 目标
*   修正 `packages/quipu-cli/src/quipu/cli/controller.py` 中的 `is_clean` 判定逻辑。
*   确保在创世状态（无历史且为空树）下不触发 `capture_drift`。

## 基本原理
引入 `EMPTY_TREE_HASH` 常量，显式检查“图谱为空”且“当前状态为空树”的情况，将其标记为 Clean。

## 标签
#comp/cli #scope/core #fix #test

---

## Script

### Acts 1: Fix Controller Logic

修正 `controller.py` 中对工作区状态的判断逻辑，正确处理创世状态。

~~~~~act
replace packages/quipu-cli/src/quipu/cli/controller.py
~~~~~

~~~~~python
        # --- Phase 2: Decision (Lazy Capture) ---
        current_hash = engine.git_db.get_tree_hash()
        
        # 判断是否 Dirty/Orphan
        # 如果 current_node 存在且其 output_tree 与当前 hash 一致，则为 Clean
        is_clean = engine.current_node is not None and engine.current_node.output_tree == current_hash
        
        if not is_clean:
            # 如果环境有漂移（或全新项目），先生成一个 Capture 节点
~~~~~

~~~~~python
        # --- Phase 2: Decision (Lazy Capture) ---
        current_hash = engine.git_db.get_tree_hash()
        
        # 判断是否 Dirty/Orphan
        # 1. 正常 Clean: current_node 存在且与当前 hash 一致
        is_node_clean = (engine.current_node is not None) and (engine.current_node.output_tree == current_hash)
        
        # 2. 创世 Clean: 历史为空 且 当前是空树 (即没有任何文件被追踪)
        EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        is_genesis_clean = (not engine.history_graph) and (current_hash == EMPTY_TREE_HASH)
        
        is_clean = is_node_clean or is_genesis_clean
        
        if not is_clean:
            # 如果环境有漂移（或全新项目且非空），先生成一个 Capture 节点
~~~~~