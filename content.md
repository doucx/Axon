# fix-test: 修正 ViewModel 测试中 `filename` 构造不一致的问题

## 错误分析
测试 `tests/test_view_model.py::TestGraphViewModel::test_get_content_bundle` 失败。失败的断言是 `assert 'Private Intent' in bundle1`。

分析代码可知，`GraphViewModel.get_content_bundle` 方法通过 `self.reader.get_private_data(node.filename.name)` 来获取私有数据。在真实的 `QuipuNode` 对象中，`filename` 通常是 `Path(".quipu/git_objects/<commit_hash>")`，因此 `node.filename.name` 会返回 `commit_hash`。

然而，在失败的测试用例中，`QuipuNode` 对象被构造为 `QuipuNode(..., filename=Path("f_both"), ...)`。这导致 `node.filename.name` 返回的是 `"f_both"`。

同时，`MockHistoryReader` 的 `private_data` 字典是以哈希 (`"h_both"`) 作为键来存储私有数据的。

因此，当 `get_private_data` 尝试用键 `"f_both"` 去查找时，自然找不到对应的数据，返回了 `None`，导致测试失败。

## 用户需求
修复 `test_get_content_bundle` 测试用例，使其能够通过。

## 评论
这是一个典型的测试数据与被测代码逻辑不匹配导致的问题。修复方法是调整测试中 `QuipuNode` 对象的构造方式，使其 `filename` 属性的行为与真实场景保持一致，即 `node.filename.name` 应该返回节点的唯一哈希标识。

## 目标
1.  修改 `tests/test_view_model.py` 中 `test_get_content_bundle` 函数。
2.  调整 `QuipuNode` 实例的创建，使其 `filename` 属性包含节点的哈希。
3.  确保测试通过，验证 `GraphViewModel` 的内容整合逻辑是正确的。

## 基本原理
通过将 `QuipuNode` 的 `filename` 构造为 `Path(f"mock/{node_hash}")`，我们模拟了真实场景下的 `Path` 结构，使得 `node.filename.name` 能够正确地返回 `node_hash`。这样，`get_private_data` 就能使用正确的键从 `MockHistoryReader` 的 `private_data` 字典中查找到预设的私有内容，从而修复测试。

## 标签
#intent/fix #flow/ready #priority/high
#comp/tests #scope/dx
#ai/instruct
#task/domain/ui #task/object/performance #task/action/bug-fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修正测试数据

此操作将使用 `replace` 精确地修正 `test_view_model.py` 文件中 `QuipuNode` 的构造方式。

~~~~~act
replace tests/test_view_model.py
~~~~~
~~~~~python
        node_both = QuipuNode("a", "h_both", datetime.now(), Path("f_both"), "plan", summary="Public Content")
        node_public = QuipuNode("b", "h_public", datetime.now(), Path("f_public"), "plan", summary="Public Only")
        node_private = QuipuNode("c", "h_private", datetime.now(), Path("f_private"), "plan", summary="") # No public
        node_none = QuipuNode("d", "h_none", datetime.now(), Path("f_none"), "plan", summary="")
~~~~~
~~~~~python
        # The key change is constructing a realistic filename where .name is the hash.
        node_both = QuipuNode("a", "h_both", datetime.now(), Path("mock/h_both"), "plan", summary="Public Content")
        node_public = QuipuNode("b", "h_public", datetime.now(), Path("mock/h_public"), "plan", summary="Public Only")
        node_private = QuipuNode("c", "h_private", datetime.now(), Path("mock/h_private"), "plan", summary="") # No public
        node_none = QuipuNode("d", "h_none", datetime.now(), Path("mock/h_none"), "plan", summary="")
~~~~~
