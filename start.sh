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

# Generate random auth token if not provided
TOKEN_DIR="${HOME}/.config/dev-deployment"
TOKEN_FILE="${TOKEN_DIR}/auth_token.txt"

if [ -z "${DEPLOYMENT_AUTH_TOKEN:-}" ]; then
    mkdir -p "$TOKEN_DIR"
    chmod 700 "$TOKEN_DIR" 2>/dev/null || true
    if [ -f "$TOKEN_FILE" ]; then
        DEPLOYMENT_AUTH_TOKEN="$(cat "$TOKEN_FILE" | tr -d '\r\n')"
    fi
    if [ -z "${DEPLOYMENT_AUTH_TOKEN:-}" ] && [ -f "$WORKSPACE_ROOT/.dev-dashboard/auth_token.txt" ]; then
        DEPLOYMENT_AUTH_TOKEN="$(cat "$WORKSPACE_ROOT/.dev-dashboard/auth_token.txt" | tr -d '\r\n')"
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

exec python3 "features/deployment/backend/server.py" --port "$PORT" "$@"
