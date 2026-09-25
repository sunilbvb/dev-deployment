#!/bin/bash

# Deployment Console — Standalone Restarter

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Restarting Deployment Console..."
echo ""

echo "🛑 Stopping existing deployment console..."
"$SCRIPT_DIR"/stop-deployment.sh || true

sleep 2

echo "🚀 Starting deployment console..."
"$SCRIPT_DIR"/start-deployment.sh
