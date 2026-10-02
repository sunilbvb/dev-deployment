#!/usr/bin/env bash
set -euo pipefail

# Mono-repo workspace status summary across multiple apps
WS_ROOT="${WORKSPACE_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$WS_ROOT"

echo "📂 Workspace Root: $WS_ROOT"
echo "🌿 Current Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'none')"
echo "📊 Git Status Summary:"
git status --short
