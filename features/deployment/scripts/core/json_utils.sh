#!/usr/bin/env bash
# ===========================================================================
# Unified Deployment Utilities Hub
# Modular coordinator hub sourcing domain-specific build, deploy, and release helpers.
# ===========================================================================
# Ensure rbenv, CocoaPods, Dart, Melos, Flutter, and Homebrew binaries are in PATH
export PATH="$HOME/.rbenv/shims:$HOME/.rbenv/bin:$HOME/.rbenv/versions/3.2.0/bin:$HOME/.pub-cache/bin:$HOME/fvm/default/bin:$HOME/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Resolve directories
resolve_scripts_dir() {
    local dir
    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    if [ -d "$dir/android" ]; then
        echo "$dir"
    elif [ -d "$dir/../android" ]; then
        cd "$dir/.." >/dev/null 2>&1 && pwd
    else
        echo "$dir"
    fi
}
JSON_SCRIPT_DIR="$(resolve_scripts_dir)"
CORE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

# 1. Source core modules
source "$CORE_SCRIPT_DIR/melos_runner.sh"
source "$CORE_SCRIPT_DIR/fastlane_utils.sh"
source "$CORE_SCRIPT_DIR/project_resolver.sh"
source "$CORE_SCRIPT_DIR/retry_utils.sh"
source "$CORE_SCRIPT_DIR/release_commands.sh"

# 2. Source platform-specific utilities
# shellcheck source=developer-dashboard/features/deployment/scripts/android/android_utils.sh
if [ -f "$JSON_SCRIPT_DIR/android/android_utils.sh" ]; then
    source "$JSON_SCRIPT_DIR/android/android_utils.sh"
fi

# shellcheck source=developer-dashboard/features/deployment/scripts/ios/ios_utils.sh
if [ -f "$JSON_SCRIPT_DIR/ios/ios_utils.sh" ]; then
    source "$JSON_SCRIPT_DIR/ios/ios_utils.sh"
fi

# 3. Source multiplatform coordinator (depends on android_utils and ios_utils)
source "$CORE_SCRIPT_DIR/multiplatform.sh"
