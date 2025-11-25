# fix-test: 修复测试以适配懒加载机制

## 用户需求
由于引入了 Git 对象存储的懒加载优化，`HistoryReader.load_all_nodes()` 返回的节点不再预加载 `content`。这导致了多个依赖 `node.content` 直接访问的测试用例失败。

## 评论
这是预期的破坏性变更。测试代码作为 API 的消费者，必须更新以反映新的使用模式：想要获取内容，必须显式调用 `reader.get_node_content(node)`。

## 目标
1.  修复 `tests/test_storage_reader.py` 中的单元测试，显式测试懒加载行为。
2.  修复 `tests/test_root_invariance.py` 中的集成测试。

## 基本原理
在测试中，当我们需要验证节点内容时，不再直接断言 `node.content`，而是先调用 `reader.get_node_content(node)` 触发加载，或者直接断言该方法的返回值。

## 标签
#comp/tests #scope/dx #fix

---

## Script

### Acts 1: 修复 Storage Reader 测试

更新 `test_storage_reader.py`，在访问内容前显式加载。

~~~~~act
replace tests/test_storage_reader.py
~~~~~

~~~~~python
        roots = [n for n in nodes if n.input_tree == h0]
        assert len(roots) == 1
        node_a = roots[0]
        assert node_a.content.strip() == "Plan A"
        assert node_a.timestamp.timestamp() == 1000.0
        
        assert len(node_a.children) == 1
        node_b = node_a.children[0]
        assert node_b.content.strip() == "Plan B"
        assert node_b.input_tree == h1
        assert node_b.parent == node_a
        
        assert len(node_b.children) == 1
        node_c = node_b.children[0]
        assert node_c.content.strip() == "Capture C"
        assert node_c.node_type == "capture"
~~~~~

~~~~~python
        roots = [n for n in nodes if n.input_tree == h0]
        assert len(roots) == 1
        node_a = roots[0]
        # Lazy load verification
        assert node_a.content == "" 
        assert reader.get_node_content(node_a).strip() == "Plan A"
        assert node_a.timestamp.timestamp() == 1000.0
        
        assert len(node_a.children) == 1
        node_b = node_a.children[0]
        assert reader.get_node_content(node_b).strip() == "Plan B"
        assert node_b.input_tree == h1
        assert node_b.parent == node_a
        
        assert len(node_b.children) == 1
        node_c = node_b.children[0]
        assert reader.get_node_content(node_c).strip() == "Capture C"
        assert node_c.node_type == "capture"
~~~~~

~~~~~act
replace tests/test_storage_reader.py
~~~~~

~~~~~python
        nodes = reader.load_all_nodes()
        
        assert len(nodes) == 3
        
        nodes_by_content = {n.content.strip(): n for n in nodes}
        node_a = nodes_by_content["Plan A"]
        node_b = nodes_by_content["Plan B"]
        node_c = nodes_by_content["Plan C"]
        
        assert node_a.parent is None
~~~~~

~~~~~python
        nodes = reader.load_all_nodes()
        
        assert len(nodes) == 3
        
        # Explicitly load content for mapping
        nodes_by_content = {reader.get_node_content(n).strip(): n for n in nodes}
        
        node_a = nodes_by_content["Plan A"]
        node_b = nodes_by_content["Plan B"]
        node_c = nodes_by_content["Plan C"]
        
        assert node_a.parent is None
~~~~~

~~~~~act
replace tests/test_storage_reader.py
~~~~~

~~~~~python
        nodes = reader.load_all_nodes()
        
        assert len(nodes) == 2
        valid_nodes = {n.content.strip(): n for n in nodes}
        assert "A" in valid_nodes
        assert "C" in valid_nodes
        
        node_c = valid_nodes["C"]
~~~~~

~~~~~python
        nodes = reader.load_all_nodes()
        
        assert len(nodes) == 2
        # Explicitly load content
        valid_nodes = {reader.get_node_content(n).strip(): n for n in nodes}
        assert "A" in valid_nodes
        assert "C" in valid_nodes
        
        node_c = valid_nodes["C"]
~~~~~

### Acts 2: 修复 Root Invariance 集成测试

更新 `test_root_invariance.py`，使用 `engine.reader` 获取内容。

~~~~~act
replace tests/test_root_invariance.py
~~~~~

~~~~~python
        plan_nodes = [n for n in nodes if n.node_type == 'plan']
        assert len(plan_nodes) >= 1, "应至少有一个 plan 节点"
        assert "Success from subdir" in plan_nodes[-1].content
~~~~~

~~~~~python
        plan_nodes = [n for n in nodes if n.node_type == 'plan']
        assert len(plan_nodes) >= 1, "应至少有一个 plan 节点"
        # 使用 reader 显式获取内容 (Lazy Loading 适配)
        content = engine.reader.get_node_content(plan_nodes[-1])
        assert "Success from subdir" in content
~~~~~