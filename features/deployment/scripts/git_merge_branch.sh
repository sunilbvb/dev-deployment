#!/usr/bin/env bash
set -euo pipefail

# Merge branch automation with conflict guard
TARGET_BRANCH="${1:-}"
SOURCE_BRANCH="${2:-}"

if [ -z "$TARGET_BRANCH" ] || [ -z "$SOURCE_BRANCH" ]; then
    echo "Usage: git_merge_branch.sh <target_branch> <source_branch>"
    exit 1
fi

echo "🔀 Checking out $TARGET_BRANCH..."
git checkout "$TARGET_BRANCH"

echo "📥 Pulling latest $TARGET_BRANCH..."
git pull origin "$TARGET_BRANCH" --ff-only || true

echo "Merging $SOURCE_BRANCH into $TARGET_BRANCH..."
if git merge --no-ff "$SOURCE_BRANCH" -m "Merge branch '$SOURCE_BRANCH' into '$TARGET_BRANCH'"; then
    echo "✅ Successfully merged $SOURCE_BRANCH into $TARGET_BRANCH"
else
    echo "❌ Merge conflict detected between $SOURCE_BRANCH and $TARGET_BRANCH"
    git merge --abort || true
    exit 1
fi
