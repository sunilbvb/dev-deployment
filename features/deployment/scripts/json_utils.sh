#!/usr/bin/env bash
# Backward-compatibility delegator for core/json_utils.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/core/json_utils.sh" "$@"
