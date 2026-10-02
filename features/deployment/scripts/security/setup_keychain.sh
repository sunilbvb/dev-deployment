#!/usr/bin/env bash
#------------------------------------------------------------------------------
# setup_keychain.sh - Stores secrets securely in the macOS Keychain
#------------------------------------------------------------------------------
set -euo pipefail

FLAVOR="${1:-}"
KEY_NAME="${2:-}"
KEY_VALUE="${3:-}"

if [ -z "$FLAVOR" ] || [ -z "$KEY_NAME" ]; then
    echo "Usage: $0 <dev|qa|prod> <KEY_NAME> [KEY_VALUE]"
    echo "Note: If KEY_VALUE is omitted, you will be prompted to enter it securely."
    exit 1
fi

if [ "$FLAVOR" != "dev" ] && [ "$FLAVOR" != "qa" ] && [ "$FLAVOR" != "prod" ]; then
    echo "Error: Flavor must be dev, qa, or prod" >&2
    exit 1
fi

SERVICE_NAME="${KEYCHAIN_SERVICE_NAME:-com.example.app}.$FLAVOR"

# Store or update the secret in the default login keychain
# If KEY_VALUE is provided as 3rd arg, use it. Otherwise, security will prompt via stdin.
if [ -n "${KEY_VALUE:-}" ]; then
    security add-generic-password -a "$KEY_NAME" -s "$SERVICE_NAME" -w "$KEY_VALUE" -U -A
else
    echo "Enter secret value for $KEY_NAME:"
    security add-generic-password -a "$KEY_NAME" -s "$SERVICE_NAME" -U -w -A
fi

echo "✅ Successfully stored $KEY_NAME for flavor '$FLAVOR' in macOS Keychain (Service: $SERVICE_NAME)."
