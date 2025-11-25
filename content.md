# refactor: 提交已完成的 monorepo 物理拆分

## 目标
将阶段 1 和阶段 2 的所有重构工作（包括文件迁移、配置创建和导入路径修复）作为一个原子性的变更，提交到 Git 版本历史中。

## 基本原理
在完成了一次大规模的、成功的重构之后，创建一个清晰、独立的提交是至关重要的。这不仅为项目历史创建了一个重要的里程碑，也为未来可能的回滚或代码审查提供了明确的边界。本次提交将标志着 Axon 从单体应用结构到 Quipu 多包 monorepo 结构的正式转变。

## 标签
完成核心模块的重构。 #refactor #git #chore

---

## Script

### Act 1: 暂存所有变更

将所有被移动、创建和修改的文件添加到 Git 的暂存区。

~~~~~act
git_add .
~~~~~

### Act 2: 创建提交

使用符合规范的提交信息，将暂存区的变更固化到历史记录中。

~~~~~act
git_commit
~~~~~
~~~~~message
refactor(arch): Implement monorepo structure for core modules

This commit completes the physical separation phase (Stage 2) of the Quipu refactoring plan.

- The monolithic `core/` directory has been dismantled.
- Functionality is now split into four independent packages under `packages/`:
  - `quipu-interfaces`
  - `quipu-engine`
  - `quipu-runtime`
  - `quipu-cli`
- Each package has its own `pyproject.toml` defining its dependencies and entry points.
- All import paths and test configurations have been updated to reflect the new structure.
~~~~~