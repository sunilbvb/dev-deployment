#!/usr/bin/env bash
#------------------------------------------------------------------------------
# build_secrets.sh - Fetches build secrets from macOS Keychain at compile time
#------------------------------------------------------------------------------
set -eo pipefail

FLAVOR="${1:-}"

if [ -z "$FLAVOR" ]; then
    echo "❌ Error: Flavor argument is required (dev, qa, or prod)" >&2
    exit 1
fi

if [ "$FLAVOR" != "dev" ] && [ "$FLAVOR" != "qa" ] && [ "$FLAVOR" != "prod" ]; then
    echo "❌ Error: Flavor must be dev, qa, or prod (received: $FLAVOR)" >&2
    exit 1
fi

SERVICE_NAME="${KEYCHAIN_SERVICE_NAME:-com.example.app}.$FLAVOR"

# List of all required secret keys for the build
SECRETS=(
    "APPLE_API_KEY"
    "APPLE_API_ISSUER"
    "APPSFLYER_DEV_KEY"
    "APPCOCKPIT_PUBLIC_KEY"
    "IAP_IOS_KEY"
    "IAP_ANDROID_KEY"
    "GOOGLE_MAPS_KEY"
    "FACEBOOK_CLIENT_TOKEN"
    "GOOGLE_CHAT_WEBHOOK_URL"
    "SENTRY_DSN"
)

DEFINES_STR=""

for key in "${SECRETS[@]}"; do
    # Fetch key from keychain. security find-generic-password prints only the password value to stdout.
    # We silence stderr to avoid showing keychain system errors in the log.
    val=$(security find-generic-password -a "$key" -s "$SERVICE_NAME" -w 2>/dev/null || true)
    
    if [ -z "$val" ] || [ "$val" == "REPLACE_ME" ]; then
        echo "⚠️ WARNING: Secret '$key' is empty, REPLACE_ME, or not set in Keychain for flavor '$FLAVOR'. Skipping to allow fallback to env config." >&2
    else
        # Append --dart-define in-memory string
        DEFINES_STR="$DEFINES_STR --dart-define=$key=$val"
    fi
done

# Output in-memory defines directly to stdout for capture
echo -n "$DEFINES_STR"
