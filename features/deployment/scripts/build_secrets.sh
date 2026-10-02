#!/usr/bin/env bash
# Backward-compatibility delegator for security/build_secrets.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/security/build_secrets.sh" "$@"
