#!/bin/bash

# Deployment Console — Standalone Launcher
# Starts features/deployment as its own independent server.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$FEATURE_DIR/../.." && pwd)"

PID_FILE="$FEATURE_DIR/deployment.pid"

if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

DEFAULT_PORT="${DEPLOYMENT_PORT:-18112}"
export DEPLOYMENT_PORT="$DEFAULT_PORT"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "❌ Deployment console is already running (PID: $PID)"
        echo "🌐 Access it at: http://localhost:$DEPLOYMENT_PORT"
        echo "💡 To stop it, run: ./stop-deployment.sh"
        exit 1
    else
        echo "🧹 Cleaning up stale PID file..."
        rm -f "$PID_FILE"
    fi
fi

# Point router.py at the active workspace
ACTIVE_WORKSPACE_FILE="$REPO_ROOT/config/active_workspace.txt"
if [ -f "$ACTIVE_WORKSPACE_FILE" ]; then
    CANDIDATE_WORKSPACE="$(cat "$ACTIVE_WORKSPACE_FILE" | tr -d '\r\n' | xargs)"
    if [ -n "$CANDIDATE_WORKSPACE" ] && [ -d "$CANDIDATE_WORKSPACE" ]; then
        export WORKSPACE_ROOT="$CANDIDATE_WORKSPACE"
    else
        echo "⚠️  active_workspace.txt found but points at a missing directory - using router.py's built-in default"
    fi
fi

echo "🚀 Starting Deployment Console (standalone)..."
echo "📂 Workspace: ${WORKSPACE_ROOT:-<router.py default>}"
echo "🔌 Port: $DEPLOYMENT_PORT"
echo ""

cd "$FEATURE_DIR"
python3 backend/server.py --port "$DEPLOYMENT_PORT" &
SERVER_PID=$!

echo "$SERVER_PID" > "$PID_FILE"

echo "✅ Deployment console started successfully!"
echo "🌐 Access it at: http://localhost:$DEPLOYMENT_PORT"
echo "🔄 Server PID: $SERVER_PID"
echo "💡 To stop it, run: ./stop-deployment.sh"
echo ""

echo "Press Ctrl+C to stop the deployment console"
trap 'echo ""; echo "🛑 Stopping deployment console..."; "$SCRIPT_DIR"/stop-deployment.sh; exit 0' INT

wait "$SERVER_PID" 2>/dev/null || true
