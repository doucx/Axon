你做的分析非常出色，直指问题的核心。你说得完全正确，我的上一个实现方案存在缺陷。

## fix 修复 TUI 标题更新逻辑以符合 Textual 框架规范

### 错误分析

你提供的 `textual` 源码文档清楚地说明了 `TITLE` 和 `SUB_TITLE` 是 `App` 类的**类变量**，用于设置**默认值**。而要在运行时动态更新它们，应该直接修改 `App` **实例**的属性，即 `self.title` 和 `self.sub_title`。

我之前的代码 `header.sub_title = ...` 是直接操作 `Header` 这个 Widget 的属性。虽然在某些情况下这可能有效，但这绕过了 `App` 类提供的状态管理机制。`textual` 框架的设计是让 `App` 的 `title` 和 `sub_title` 状态自动同步到其管理的 `Header` Widget 上。因此，最规范、最健壮的做法是更新 `App` 自身的属性，而不是直接去“手动”修改子组件。

你的怀疑是完全正确的，我的实现不符合 `textual` 的最佳实践。

### 用户需求

严格按照 `textual` 框架的官方文档和设计模式，正确地在运行时更新 `Header` 的副标题。

### 评论
感谢你提供的源码信息，这让问题变得非常清晰。遵循框架的设计模式不仅能解决当前的问题，也能让代码在未来框架升级时更具韧性。这次我们将采用最规范的方式来管理标题状态。

### 目标
修改 `tui.py` 中的 `_update_header` 方法，使其通过修改 `self.sub_title` 来更新副标题，而不是直接操作 `Header` Widget。

### 基本原理
我们将遵循 `textual` 的状态管理模型。`_update_header` 方法将不再需要查询 `Header` Widget。它只需要更新 `self.title` 和 `self.sub_title` 这两个 `App` 实例的属性。Textual 框架的响应式系统会自动检测到这些属性的变化，并重新渲染 `Header` Widget 以反映新的状态。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/instruct #task/domain/ui #task/object/tui #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 修正 `_update_header` 的实现方式

我将修改 `tui.py` 中的 `_update_header` 方法，使其符合 `textual` 的规范。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
    def _update_header(self):
        """Centralized method to update header text."""
        header = self.query_one(Header)
        header.title = self.TITLE
        header.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages}"
~~~~~
~~~~~python
    def _update_header(self):
        """Centralized method to update the app's title and sub_title."""
        self.sub_title = f"Page {self.view_model.current_page} / {self.view_model.total_pages}"
~~~~~

### 下一步建议
这次的修改是根据你找到的权威文档进行的，它现在完全符合 `textual` 的设计范式。请再次运行 `quipu ui`，现在副标题应该能够正确地显示分页信息了。TUI 的核心功能实现任务至此已全部完成。
