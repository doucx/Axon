# Quipu 开发指南 (The Quipu Development Workflow)

本文档介绍了如何在一个“依靠 Quipu 构建 Quipu”的自举环境中安全、高效地工作。

## 核心概念：双环境隔离 (Dual-Environment Separation)

为了解决“修改工具本身会导致工具崩溃”的死锁问题，我们维护了两个隔离的环境：

1.  **🔵 Stable 环境 (`qs`)**:
    *   **角色**: 医生/基础设施。
    *   **本质**: 直接从 PyPI 安装的线上稳定发布版 (`pyquipu-cli`)。
    *   **用途**: **你的生产力工具**。用它来执行 Plan 文件、重构源码和代码修改。它完全独立于你正在编辑的本地代码，不会因调试中断。
2.  **🟢 Dev 环境 (`qd`)**:
    *   **角色**: 病人/被测对象。
    *   **本质**: 当前本地源码的可编辑安装 (`uv pip install -e .[dev]`)。
    *   **用途**: **你的测试对象**。用它来跑测试、手动调试、验证新功能。它实时反映本地源码的修改。

---

## 快速开始

### 1. 初始化环境

首次克隆项目或更新依赖后，在根目录执行：

```bash
# 1. 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 一键构建开发环境
python3 scripts/setup_dev.py

# 3. 激活别名 (建议加入 .bashrc 或 .zshrc)
source scripts/dev_setup.sh
```

对于 fish：

```fish
# 激活别名 (建议加入 .config/fish/config.fish)
source scripts/dev_setup.fish
```

### 2. 常用命令速查

| 别名 | 完整命令 | 用途 |
| :--- | :--- | :--- |
| **`qs`** | `.envs/stable/bin/quipu` | **稳定执行工具**。用这个来跑 `Plan.md` 修改代码。 |
| **`qd`** | `.envs/dev/bin/quipu` | **开发调试对象**。用这个来测试本地代码新特性。 |
| **`qtest`** | `.envs/dev/bin/pytest` | **运行测试**。运行项目的单元与集成测试。 |
| **`ruff`** | `.envs/dev/bin/ruff` | **代码检查与格式化**。静态检查和代码美化。 |

---

## 标准开发循环 (The Loop)

### 场景 A：常规功能开发

1.  **编写计划**: 创建 `feat_xxx.md`。
2.  **执行修改**: 使用 **Stable** 环境执行计划。
    ```bash
    qs run feat_xxx.md
    ```
3.  **验证**: 使用 **Dev** 环境运行测试。
    ```bash
    qtest tests/test_new_feat.py
    ```

### 场景 B：依赖更新或新包注册

如果你在 `packages/` 中新增了子包或修改了依赖，只需重新运行：
```bash
python3 scripts/setup_dev.py --only-dev
```

---

## 故障排除

### Q: 我把代码改坏了，`qd` 报错，但我需要用 Quipu 来修复它。
**A**: 这正是双环境存在的意义！`qs` 是通过 PyPI 安装的独立稳定版本，不会受本地源码破坏的影响。你可以继续使用 `qs run fix_bug.md` 来修改源代码。

### Q: `qtest` 找不到我新加的包？
**A**: 如果你添加了新的 `packages/` 子目录，请运行 `python3 scripts/setup_dev.py --only-dev` 来注册新的 Editable Install。