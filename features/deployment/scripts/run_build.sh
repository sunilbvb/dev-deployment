#!/bin/bash
# ===========================================================================
# Unified Build Script Entrypoint
# Resolves workspace root, sources json_utils.sh, and executes requested action.
# ===========================================================================
set -euo pipefail

# Ensure rbenv, CocoaPods, Dart, Melos, Flutter, and Homebrew binaries are in PATH
export PATH="$HOME/.rbenv/shims:$HOME/.rbenv/bin:$HOME/.rbenv/versions/3.2.0/bin:$HOME/.pub-cache/bin:$HOME/fvm/default/bin:$HOME/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# 1. Dynamically locate workspace root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
ROOT="${MELOS_ROOT_PATH:-}"
if [ -z "$ROOT" ] || [ ! -f "$ROOT/pubspec.yaml" ]; then
    if [ -f "$(pwd)/pubspec.yaml" ]; then
        ROOT="$(pwd)"
    elif [ -f "$(cd "$SCRIPT_DIR/../../.." && pwd)/pubspec.yaml" ]; then
        ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
    elif [ -f "$(cd "$SCRIPT_DIR/../../../config" 2>/dev/null && pwd)/active_workspace.txt" ]; then
        ACTIVE_WS="$(cat "$(cd "$SCRIPT_DIR/../../../config" && pwd)/active_workspace.txt" 2>/dev/null | tr -d '\r\n' | xargs)"
        if [ -n "$ACTIVE_WS" ] && [ -f "$ACTIVE_WS/pubspec.yaml" ]; then
            ROOT="$ACTIVE_WS"
        fi
    else
        ROOT="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
    fi
fi
export MELOS_ROOT_PATH="$ROOT"

# 2. Source main json utility script relative to this script
source "$SCRIPT_DIR/json_utils.sh"

# 3. Extract requested action and execute with shifted arguments
ACTION="$1"
shift

"$ACTION" "$@"
