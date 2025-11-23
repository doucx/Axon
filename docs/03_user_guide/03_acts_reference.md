# 🛠️ Act 指令参考手册

## 基础文件操作 (Basic)

### `write_file`
写入文件。如果文件不存在则创建，存在则覆盖。
*   参数: `[path, content]`
*   模式: Hybrid

### `replace`
精确文本替换。`old_string` 必须与文件中的内容（包括缩进）完全一致。
*   参数: `[path, old_string, new_string]`
*   模式: Hybrid

### `append_file`
追加内容到文件末尾。
*   参数: `[path, content]`
*   模式: Hybrid

---

## 版本控制 (Git)

### `git_init`
初始化仓库。
*   参数: 无

### `git_add`
添加文件到暂存区。
*   参数: `[files]` (支持多文件，空格分隔)
*   模式: Exclusive

### `git_commit`
提交更改。
*   参数: `[message]`
*   模式: Block Only (必须在代码块中写消息)

### `git_status`
显示当前状态。
*   参数: 无

---

## 环境检查 (Check)

### `check_files_exist`
断言文件存在。如果文件缺失，脚本立即终止。
*   参数: `[file_list_string]` (按行分隔的文件名)
*   模式: Exclusive

### `check_cwd_match`
断言当前绝对路径。用于防止在错误的机器上运行。
*   参数: `[expected_absolute_path]`
*   模式: Exclusive

---

## 辅助工具 (Shell & Read)

### `run_command`
执行系统 Shell 命令。
*   参数: `[command_string]`
*   模式: Exclusive

### `read_file`
读取并打印文件内容到标准输出。
*   参数: `[path]`
*   模式: Hybrid

### `list_files`
列出目录结构。
*   参数: `[path] [--tree]`
*   模式: Exclusive

### `search_files`
搜索文件内容（优先使用 `rg`）。
*   参数: `[pattern] [--path PATH]`
*   模式: Exclusive

---

## 重构 (Refactor)

### `move_file`
移动或重命名文件。
*   参数: `[src, dest]`
*   模式: Hybrid

### `delete_file`
删除文件或目录（递归）。
*   参数: `[path]`
*   模式: Exclusive

---

## 记忆 (Memory)

### `log_thought`
记录思维链或决策过程到 `.axon/memory.md`。
*   参数: `[content]`
*   模式: Block Only