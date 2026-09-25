#!/bin/bash

# Deployment Console — Standalone Stopper

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEATURE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PID_FILE="$FEATURE_DIR/deployment.pid"

echo "🛑 Stopping Deployment Console..."
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Deployment console is not running (no PID file found)"
    echo "💡 To start it, run: ./start-deployment.sh"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "❌ Deployment console process not found (PID: $PID)"
    echo "🧹 Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

echo "🔄 Stopping deployment console process (PID: $PID)..."
kill "$PID"

for i in {1..10}; do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "✅ Deployment console stopped successfully"
        rm -f "$PID_FILE"
        exit 0
    fi
    echo "⏳ Waiting for process to stop... ($i/10)"
    sleep 1
done

echo "⚡ Force stopping deployment console process..."
kill -9 "$PID" 2>/dev/null || true
rm -f "$PID_FILE"

echo "✅ Deployment console stopped (forced)"
