# Quipu

> **The Effector for AI Agents.**
>
> 将 Markdown 转化为可执行、可回溯、安全的系统操作脚本。

> 警告：文档严重过时
---

## 📚 文档导航

Quipu 的文档已重新组织，请查阅以下指南：

### 🏁 入门
*   **[简介](docs/01_introduction.md)**: 了解 Quipu 的设计哲学。
*   **[快速上手](docs/02_getting_started.md)**: 安装与 Hello World。

### 📖 用户指南
*   **[核心概念](docs/03_user_guide/01_core_concepts.md)**: 理解 Act, Context 与 ArgMode。
*   **[CLI 参考](docs/03_user_guide/02_cli_reference.md)**: `run`, `log`, `checkout`, `sync` 命令手册。
*   **[指令参考](docs/03_user_guide/03_acts_reference.md)**: 所有可用 Act (`write_file`, `git_commit` 等) 的详细说明。

### 🤖 提示工程
*   **[Prompt 指南](docs/04_prompting_guide.md)**: **(重要)** 如何编写 System Prompt 让 AI 生成 Quipu 兼容的脚本。

### 💻 开发者
*   **[架构解析](docs/05_developer_guide/01_architecture.md)**: 幽灵引擎与核壳分离架构。
*   **[插件开发](docs/05_developer_guide/02_adding_new_acts.md)**: 如何扩展 Quipu 的能力。

---

## ⚡️ 快速安装

```bash
pip install -r requirements.txt
```

## 🧪 运行测试

```bash
pytest
```
