好的，我明白了。你希望将创建 `migrate_v1_to_v1.1.sh` 外部脚本的过程，本身记录为一个 Quipu 计划。这是一个很好的实践，体现了用 Quipu 记录开发过程的核心思想。

这个计划将只包含创建外部迁移脚本的行为，而不涉及对 `Hydrator` 核心逻辑的修复，完全符合你的要求。

---

我将为你生成这个计划。

## feat: 创建外部迁移脚本以升级至 v1.1 架构

### 用户需求
在项目从 v1.0 升级到 v1.1 架构的过程中，需要一个可靠、透明且独立于核心应用的工具，来完成一次性的数据迁移。核心应用内的迁移逻辑被证明复杂且容易出错，因此需要一个外部脚本来保证操作的原子性和可控性。

### 评论
这是一个明智的工程决策。当内部工具的复杂度超出其价值时，回归到一个简单的、功能单一的外部脚本是最高效的解决方案。这个脚本将作为项目历史的一部分，为未来的维护者提供清晰的迁移路径记录。

### 目标
1.  创建一个名为 `migrate_v1_to_v1.1.sh` 的 Bash 脚本。
2.  该脚本能够自动删除旧的 SQLite 缓存，为重建做准备。
3.  该脚本能够识别所有旧版 v1.0 的 Git 引用（`refs/quipu/history` 和 `refs/quipu/heads/*`）。
4.  脚本将所有找到的旧引用对应的 commit，重定位到新的 v1.1 命名空间（`refs/quipu/local/heads/*`）。
5.  在创建新引用后，安全地删除所有旧的 v1.0 引用。
6.  脚本应包含清晰的注释和安全检查，确保其易于理解和安全执行。

### 基本原理
此脚本利用标准的 Git 命令行工具 (`git for-each-ref`, `git rev-parse`, `git update-ref`) 来直接操作 Git 引用数据库。
-   `git for-each-ref` 用于批量发现指定前缀下的所有引用。
-   `git rev-parse` 用于验证和获取单个引用的 commit 哈希。
-   `git update-ref` 是一个底层的、安全的工具，用于创建和删除引用，是整个迁移操作的核心。
-   通过将所有操作封装在一个 `set -e` 的 Bash 脚本中，我们确保了操作的原子性：一旦任何步骤失败，脚本将立即中止，防止留下一个不一致的状态。

### 标签
#intent/tooling #flow/ready #priority/critical 
#comp/build #concept/history #scope/dx 
#ai/instruct
#task/domain/storage #task/object/data-migration #task/action/build
#task/state/end

---

### Script

#### Acts 1: 创建外部迁移脚本

我们将创建 `migrate_v1_to_v1.1.sh` 文件，并赋予其可执行权限。

~~~~~act
write_file
migrate_v1_to_v1.1.sh
~~~~~
~~~~~bash
#!/bin/bash

# ==============================================================================
# Quipu v1.0 to v1.1 Data Migration Script
#
# This script performs a one-way migration of Quipu's internal Git references
# to the new v1.1 format. It is designed for a single-user repository.
#
# WHAT IT DOES:
# 1. Deletes the SQLite cache (`.quipu/history.sqlite`) for a clean rebuild.
# 2. Finds all legacy commit heads from `refs/quipu/heads/*` and `refs/quipu/history`.
# 3. Creates new v1.1-compliant references at `refs/quipu/local/heads/<hash>`.
# 4. Deletes all legacy references.
#
# USAGE:
# 1. Place this script in the root of your Quipu project (where the .git dir is).
# 2. Run `chmod +x migrate_v1_to_v1.1.sh`.
# 3. Execute it: `./migrate_v1_to_v1.1.sh`.
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# --- Sanity Check ---
if [ ! -d ".git" ]; then
    echo "❌ Error: This script must be run from the root of a Git repository."
    exit 1
fi

echo "🚀 Starting Quipu v1.0 to v1.1 data migration..."
echo "----------------------------------------------------"

# --- Step 1: Delete the SQLite cache ---
DB_PATH=".quipu/history.sqlite"
if [ -f "$DB_PATH" ]; then
    echo "🗑️  Deleting old SQLite cache: $DB_PATH"
    rm -f "$DB_PATH"
else
    echo "✅ No existing SQLite cache found. Skipping deletion."
fi

# --- Step 2: Collect all unique legacy commit hashes ---
echo "🔍 Finding all legacy v1.0 references..."

# Using a temporary file to store unique hashes
TMP_HASHES_FILE=$(mktemp)

# Get hashes from refs/quipu/heads/*
git for-each-ref --format='%(objectname)' refs/quipu/heads/ > "$TMP_HASHES_FILE"

# Get hash from refs/quipu/history, if it exists
if git rev-parse --verify refs/quipu/history >/dev/null 2>&1; then
    git rev-parse refs/quipu/history >> "$TMP_HASHES_FILE"
fi

# Sort and get unique hashes
ALL_HASHES=$(sort -u "$TMP_HASHES_FILE")
rm "$TMP_HASHES_FILE"

if [ -z "$ALL_HASHES" ]; then
    echo "✅ No legacy Quipu references found. Nothing to migrate."
    exit 0
fi

# Use wc -l to count lines (hashes)
COMMIT_COUNT=$(echo "$ALL_HASHES" | wc -l | xargs)
echo "✅ Found ${COMMIT_COUNT} unique legacy commit heads to migrate."

# --- Step 3: Create new v1.1 references ---
echo "✍️  Creating new v1.1 references under 'refs/quipu/local/heads/'..."
for commit_hash in $ALL_HASHES; do
    NEW_REF="refs/quipu/local/heads/${commit_hash}"
    git update-ref "$NEW_REF" "$commit_hash"
    echo "   -> Created ${NEW_REF}"
done

# --- Step 4: Delete old v1.0 references ---
echo "🔥 Deleting old v1.0 references..."

# Delete all refs under refs/quipu/heads/
OLD_HEADS=$(git for-each-ref --format='%(refname)' refs/quipu/heads/)
if [ -n "$OLD_HEADS" ]; then
    for old_ref in $OLD_HEADS; do
        git update-ref -d "$old_ref"
        echo "   -> Deleted ${old_ref}"
    done
fi

# Delete refs/quipu/history if it exists
if git rev-parse --verify refs/quipu/history >/dev/null 2>&1; then
    git update-ref -d refs/quipu/history
    echo "   -> Deleted refs/quipu/history"
fi

echo "----------------------------------------------------"
echo "🎉 Migration complete!"
echo ""
echo "NEXT STEP:"
echo "Run 'quipu ui' or 'quipu cache rebuild' to regenerate the database from the migrated references."
echo ""
~~~~~

~~~~~act
run_command
~~~~~
~~~~~bash
chmod +x migrate_v1_to_v1.1.sh
~~~~~

### 下一步建议
-   将此计划 (`plan.md`) 和新创建的 `migrate_v1_to_v1.1.sh` 脚本提交到版本控制中。
-   更新项目文档，说明在从 v1.0 版本升级时需要运行此脚本。
