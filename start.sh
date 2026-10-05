#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Verify Python version >= 3.10
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || {
    echo "❌ Error: Python 3.10 or higher is required. Found $(python3 --version 2>&1 || echo 'none')."
    exit 1
}

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
        CANDIDATE="$(tr -d '\r\n' < "$ACTIVE_WS_FILE" | xargs)"
        if [ -n "$CANDIDATE" ] && [ -d "$CANDIDATE" ]; then
            WORKSPACE_ROOT="$CANDIDATE"
        fi
    fi
fi

# Fallback to current directory if no external workspace specified
export WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(pwd)}"

PORT="${DEPLOYMENT_PORT:-18112}"

# Generate random auth token if not provided
TOKEN_DIR="${HOME}/.config/dev-deployment"
TOKEN_FILE="${TOKEN_DIR}/auth_token.txt"

if [ -z "${DEPLOYMENT_AUTH_TOKEN:-}" ]; then
    mkdir -p "$TOKEN_DIR"
    chmod 700 "$TOKEN_DIR" 2>/dev/null || true
    if [ -f "$TOKEN_FILE" ]; then
        DEPLOYMENT_AUTH_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
    fi
    if [ -z "${DEPLOYMENT_AUTH_TOKEN:-}" ] && [ -f "$WORKSPACE_ROOT/.dev-dashboard/auth_token.txt" ]; then
        DEPLOYMENT_AUTH_TOKEN="$(tr -d '\r\n' < "$WORKSPACE_ROOT/.dev-dashboard/auth_token.txt")"
        if [ -n "$DEPLOYMENT_AUTH_TOKEN" ]; then
            echo "$DEPLOYMENT_AUTH_TOKEN" > "$TOKEN_FILE"
            chmod 600 "$TOKEN_FILE"
            rm -f "$WORKSPACE_ROOT/.dev-dashboard/auth_token.txt"
        fi
    fi
    if [ -z "${DEPLOYMENT_AUTH_TOKEN:-}" ]; then
        DEPLOYMENT_AUTH_TOKEN="$(openssl rand -hex 16 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(16))')"
        echo "$DEPLOYMENT_AUTH_TOKEN" > "$TOKEN_FILE"
        chmod 600 "$TOKEN_FILE"
    fi
    export DEPLOYMENT_AUTH_TOKEN
fi

TOKEN_MASKED="${DEPLOYMENT_AUTH_TOKEN:0:4}...${DEPLOYMENT_AUTH_TOKEN: -4}"

echo "🚀 Starting Deployment Console..."
echo "📂 Workspace Root: $WORKSPACE_ROOT"
echo "🌐 URL: http://localhost:$PORT"
echo "🔑 Auth Token: $TOKEN_MASKED"
echo ""

# Auto-open browser in background if --open or AUTO_OPEN=1 is set
OPEN_BROWSER=0
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--open" ] || [ "$arg" = "--browser" ]; then
        OPEN_BROWSER=1
    else
        ARGS+=("$arg")
    fi
done

if [ "$OPEN_BROWSER" = "1" ] || [ "${AUTO_OPEN:-0}" = "1" ]; then
    (
        sleep 1
        if command -v xdg-open >/dev/null 2>&1; then
            xdg-open "http://localhost:$PORT/" >/dev/null 2>&1 || true
        elif command -v open >/dev/null 2>&1; then
            open "http://localhost:$PORT/" >/dev/null 2>&1 || true
        fi
    ) &
fi

exec python3 "features/deployment/backend/server.py" --port "$PORT" ${ARGS[@]+"${ARGS[@]}"}
