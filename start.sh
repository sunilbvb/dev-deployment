#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load environment variables from .env if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Resolve WORKSPACE_ROOT
if [ -z "${WORKSPACE_ROOT:-}" ]; then
    ACTIVE_WS_FILE="config/active_workspace.txt"
    if [ -f "$ACTIVE_WS_FILE" ]; then
        CANDIDATE="$(cat "$ACTIVE_WS_FILE" | tr -d '\r\n' | xargs)"
        if [ -n "$CANDIDATE" ] && [ -d "$CANDIDATE" ]; then
            WORKSPACE_ROOT="$CANDIDATE"
        fi
    fi
fi

# Fallback to current directory if no external workspace specified
export WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(pwd)}"

PORT="${DEPLOYMENT_PORT:-18112}"

echo "🚀 Starting Deployment Console..."
echo "📂 Workspace Root: $WORKSPACE_ROOT"
echo "🌐 URL: http://localhost:$PORT"
echo ""

exec python3 "features/deployment/backend/server.py" --port "$PORT" "$@"
