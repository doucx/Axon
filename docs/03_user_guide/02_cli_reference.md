# 💻 CLI 命令参考

Axon 的命令行界面设计得简洁直观。所有命令的入口均为 `python main.py`（安装后为 `axon`）。

## `run` - 执行脚本

执行 Markdown 文件中的指令。

```bash
axon run [FILE] [OPTIONS]
```

*   `FILE`: (可选) 要执行的 Markdown 文件路径。如果不提供且没有管道输入，默认寻找 `o.md`。
*   `--work-dir, -w`: 指定工作区根目录。默认为当前目录。
*   `--yolo, -y`: **You Only Look Once**。跳过所有交互式确认，直接执行。
*   `--parser, -p`: 指定解析器 (`auto`, `backtick`, `tilde`)。默认为 `auto`。
*   `--list-acts, -l`: 列出所有可用的 Act 指令。

**示例**:
```bash
# 管道模式：将 LLM 的输出直接喂给 Axon
llm "Refactor code" | axon run -y
```

## `log` - 查看历史

显示 Axon 的操作历史图谱。

```bash
axon log [OPTIONS]
```

*   `--work-dir, -w`: 指定工作区。

输出将显示时间戳、节点类型（Plan/Capture）、Hash 前缀以及摘要。

## `checkout` - 时间旅行

将工作区重置到指定的历史状态。

```bash
axon checkout <HASH_PREFIX> [OPTIONS]
```

*   `<HASH_PREFIX>`: 目标状态 Hash 的前几位（从 `log` 命令获取）。
*   `--force, -f`: 强制重置，不询问确认。

**安全机制**: 如果当前工作区有未记录的修改，`checkout` 会在切换前自动创建一个 Capture 节点保存现场。

## `discard` - 丢弃变更

丢弃工作区中所有未被 Axon 记录的变更，将文件恢复到上一个干净的历史状态。

```bash
axon discard [OPTIONS]
```

*   `--force, -f`: 强制执行，不询问确认。

**使用场景**: 当一个 Plan 执行失败或被中途取消后，工作区可能会处于一个包含部分修改的“脏”状态。`discard` 命令提供了一个类似于 `git checkout .` 的功能，可以一键清理这些残留的修改，让你从一个已知的良好起点重新开始。

## `sync` - 远程同步

同步 Axon 的隐形历史记录到远程 Git 仓库。

```bash
axon sync [OPTIONS]
```

*   `--remote, -r`: 指定远程仓库名称（默认 `origin`）。

此命令通过 `git push/pull refs/axon/history` 实现历史共享，让团队成员可以复现彼此的 AI 操作历史。