#!/usr/bin/env bash
set -euo pipefail

# Rename local + remote branch with safety checks
OLD_BRANCH="${1:-}"
NEW_BRANCH="${2:-}"

if [ -z "$OLD_BRANCH" ] || [ -z "$NEW_BRANCH" ]; then
    echo "Usage: git_rename_branch.sh <old_branch_name> <new_branch_name>"
    exit 1
fi

echo "Renaming local branch '$OLD_BRANCH' to '$NEW_BRANCH'..."
git branch -m "$OLD_BRANCH" "$NEW_BRANCH"

echo "Deleting old remote branch 'origin/$OLD_BRANCH'..."
git push origin --delete "$OLD_BRANCH" 2>/dev/null || true

echo "Pushing new branch '$NEW_BRANCH' and setting upstream..."
git push origin -u "$NEW_BRANCH"
echo "✅ Branch rename complete: $OLD_BRANCH -> $NEW_BRANCH"
