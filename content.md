好的，这是一个简单但重要的调整，可以将用户首次使用的体验默认设置为性能更优的 `sqlite` 后端。

## chore: 将默认存储后端切换为 SQLite

### 用户需求
用户要求将 `quipu` 的默认存储后端从 `git_object` 更改为 `sqlite`，因为后者现在已经足够稳定和高效。

### 评论
这是一个合理的请求。将默认值更改为 `sqlite` 可以为新用户提供开箱即用的最佳性能，同时仍然允许高级用户通过 `config.yml` 文件手动覆盖此设置。

### 目标
修改 `quipu-engine` 包中的 `ConfigManager`，将其 `DEFAULTS` 字典中的 `storage.type` 值更新为 `"sqlite"`。

### 基本原理
直接修改 `config.py` 文件中定义的 `DEFAULTS` 常量。这是一个全局性的默认设置，当用户的 `.quipu/config.yml` 文件中未指定存储类型时，系统会回退到此值。

### 标签
#intent/tune #flow/ready #priority/medium #comp/engine #concept/config #scope/dx #ai/instruct #task/domain/storage #task/object/default-config #task/action/update #task/state/begin #task/state/end #task/status/completed

---

### Script

#### Acts 1: 更新默认配置

我们将修改 `packages/quipu-engine/src/quipu/core/config.py` 文件，将 `storage.type` 的默认值从 `git_object` 改为 `sqlite`。

~~~~~act
patch_file
packages/quipu-engine/src/quipu/core/config.py
~~~~~
~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "storage": {
        "type": "git_object",  # 可选: "git_object", "sqlite"
    },
    "sync": {
~~~~~
~~~~~python
# 默认配置，为所有可能的设置提供一个基础
DEFAULTS = {
    "storage": {
        "type": "sqlite",  # 可选: "git_object", "sqlite"
    },
    "sync": {
~~~~~

### 下一步建议
此项更改已完成。我们可以继续处理其他任务，或者运行测试以验证默认行为是否已按预期变更。
