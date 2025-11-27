好的，这是最后一项功能的适配：**任务 7: 适配可达性渲染与内容视图**。

此任务确保在新的分页模式下，UI 依然能正确地高亮可达分支，并在内容预览区显示包含开发者意图在内的完整信息。

### feat: 在 TUI 中集成私有数据视图

#### 用户需求
根据 UI 性能优化方案，更新 `QuipuUiApp` 的内容预览逻辑，使其能够通过 `GraphViewModel` 获取并展示节点的公共计划 (`plan.md`) 和私有开发者意图 (`intent.md`)。

#### 评论
这是 Quipu 知识管理能力的一次重要增强。通过在 UI 中直接展示与某个变更相关联的“开发者意图”，我们极大地缩短了从“代码做了什么”到“代码为什么这么做”的认知路径。这使得审查历史、理解设计决策和回顾思考过程变得前所未有的高效。

#### 目标
1.  修改 `_update_content_view` 方法。
2.  调用 `self.view_model.get_content_bundle()` 来获取合并后的内容字符串。
3.  将获取到的内容渲染到 Markdown 预览组件中。

#### 基本原理
该修改完成了 MVVM 模式中 `View` -> `ViewModel` 数据流的最后一环。当用户在视图中高亮一个节点时，`_update_content_view` 方法向 `ViewModel` 请求该节点的完整内容。`ViewModel` 负责与 `Model` (HistoryReader) 交互，获取公共和私有数据，并将它们格式化成一个统一的、适合渲染的字符串返回给视图。视图层只负责显示，不关心数据来源。

#### 标签
#intent/build #flow/ready #priority/high
#comp/cli #concept/ui #scope/ux
#ai/instruct
#task/domain/ui #task/object/tui-performance #task.action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 更新内容视图以显示公有与私有数据

我将修改 `_update_content_view` 方法，将 `content_loader` 的调用替换为对 `view_model.get_content_bundle` 的调用。

可达性渲染部分 (`_populate_table`) 在之前的步骤中已经适配了 `view_model`，无需再次修改。

~~~~~act
patch_file
~~~~~
~~~~~path
packages/quipu-cli/src/quipu/cli/tui.py
~~~~~
~~~~~python
        # 懒加载并渲染 Markdown 内容
        content = self.content_loader(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content)
~~~~~
~~~~~python
        # 从 ViewModel 获取合并后的公共和私有内容并渲染
        content = self.view_model.get_content_bundle(node)
        markdown = self.query_one("#content-body", Markdown)
        markdown.update(content)
~~~~~

### 下一步建议
至此，**Quipu UI 性能优化与功能增强** 的所有前端改造任务（任务 4、5、6、7）已全部完成。`tui.py` 现在完全通过 `GraphViewModel` 来管理状态和数据，实现了分页加载、按键导航和私有数据显示。

最后一步是 **任务 8: CLI 入口更新**，即修改 `main.py` 中的 `ui` 命令，将新的 `GraphViewModel` 和改造后的 `QuipuUiApp` 正确地实例化并连接起来。
