# fix 修复测试中的导入错误

## 目标
修复 `tests/test_plugins.py` 中对 `core.controller` 的错误引用。
将 `_find_project_root` 更正为 `find_project_root`。

## 基本原理
在 `core/controller.py` 中，项目根目录查找函数的定义是 `find_project_root`（无下划线前缀）。而测试文件 `tests/test_plugins.py` 错误地引用了带有下划线的私有名称 `_find_project_root`，导致 pytest 收集测试时失败。这可能是一个遗留的命名不一致问题。

## 标签
 #fix #test

---

## Script

### Act 1: 修正 tests/test_plugins.py 的导入和调用

将 `tests/test_plugins.py` 中的 `_find_project_root` 替换为 `find_project_root`。

~~~~~act
replace tests/test_plugins.py
~~~~~

~~~~~python
from core.controller import _find_project_root  # 从 Controller 导入辅助函数
~~~~~

~~~~~python
from core.controller import find_project_root  # 从 Controller 导入辅助函数
~~~~~

~~~~~act
replace tests/test_plugins.py
~~~~~

~~~~~python
        # 从子目录查找
        found = _find_project_root(subdir)
        assert found == root.resolve()
        
        # 从根目录查找
        found_root = _find_project_root(root)
        assert found_root == root.resolve()
        
        # 在非 git 目录查找
        orphan = tmp_path / "orphan"
        orphan.mkdir()
        assert _find_project_root(orphan) is None
~~~~~

~~~~~python
        # 从子目录查找
        found = find_project_root(subdir)
        assert found == root.resolve()
        
        # 从根目录查找
        found_root = find_project_root(root)
        assert found_root == root.resolve()
        
        # 在非 git 目录查找
        orphan = tmp_path / "orphan"
        orphan.mkdir()
        assert find_project_root(orphan) is None
~~~~~