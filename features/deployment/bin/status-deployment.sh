#!/bin/bash

# Deployment Console — Standalone Status Checker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PID_FILE="$FEATURE_DIR/deployment.pid"
PORT="${DEPLOYMENT_PORT:-18112}"

echo "📊 Deployment Console Status"
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Deployment console is NOT running"
    echo "💡 To start it, run: ./start-deployment.sh"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "❌ Deployment console process not found (PID: $PID)"
    echo "🧹 Stale PID file detected"
    echo "💡 To start it, run: ./start-deployment.sh"
    exit 1
fi

PROCESS_INFO=$(ps -p "$PID" -o pid,ppid,etime,command --no-headers 2>/dev/null || echo "$PID - - python3 backend/server.py")

echo "✅ Deployment console is RUNNING"
echo "🔄 PID: $PID"
echo "📊 Process: $PROCESS_INFO"
echo "🌐 Access URL: http://localhost:$PORT"
echo "💡 Management commands:"
echo "   - Stop: ./stop-deployment.sh"
echo "   - Restart: ./restart-deployment.sh"
echo "   - Status: ./status-deployment.sh"
