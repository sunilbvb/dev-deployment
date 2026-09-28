#!/usr/bin/env bash
set -euo pipefail

# Smart Git wrapper - stash-aware pull/push, conflict detection
ACTION="${1:-status}"
[ "$#" -gt 0 ] && shift

case "$ACTION" in
    status)
        git status "$@"
        ;;
    pull)
        echo "📥 Pulling latest changes (with auto-stash)..."
        STASHED=0
        if git stash --include-untracked >/dev/null 2>&1; then
            STASHED=1
        fi
        if git pull --rebase "$@"; then
            echo "✅ Pull succeeded"
        else
            echo "❌ Pull failed with conflicts"
            if [ "$STASHED" -eq 1 ]; then
                git stash pop >/dev/null 2>&1 || true
            fi
            exit 1
        fi
        if [ "$STASHED" -eq 1 ]; then
            git stash pop >/dev/null 2>&1 || true
        fi
        ;;
    push)
        echo "🚀 Pushing branch to remote..."
        git push "$@"
        ;;
    *)
        echo "Usage: smart_git.sh {status|pull|push} [git options]"
        exit 1
        ;;
esac
