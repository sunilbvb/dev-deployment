#!/usr/bin/env bash
set -euo pipefail

# Ensure rbenv, CocoaPods, Dart, Melos, Flutter, and Homebrew binaries are in PATH
export PATH="$HOME/.rbenv/shims:$HOME/.rbenv/bin:$HOME/.rbenv/versions/3.2.0/bin:$HOME/.pub-cache/bin:$HOME/fvm/default/bin:$HOME/development/flutter/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Usage:
#   APP_NAME="App" ENV_NAME="dev" ENV_JSON="apps/my_app/env/dev.json" \
#     bash features/deployment/scripts/chat/chat_notify.sh -- flutter build ipa
#
# Env:
#   GOOGLE_CHAT_WEBHOOK_URL (optional, overrides ENV_JSON lookup)
#   ENV_JSON (optional) JSON file containing GOOGLE_CHAT_WEBHOOK_URL
#   APP_NAME (optional, default: Deployment)
#   ENV_NAME (optional, default: workspace)
#   BRANCH_NAME (optional)
#   BUILD_NO (optional)
#   CONTEXT / CHANGE_CONTEXT (optional)
#   DOWNLOAD_URL (optional) link appended to message
#   CI_LOG_URL (optional) direct link to CI/runner full logs
#   RERUN_URL (optional) direct link to rerun/retrigger pipeline
#   LOCAL_DASHBOARD_URL (optional, auto-detected if unset)
#   REQUIRE_CHAT_NOTIFY (optional) when "1", missing webhook is fatal

die() { echo "ERROR: $*" >&2; exit 1; }

resolve_chat_scripts_dir() {
  if [ -n "${MELOS_ROOT_PATH:-}" ]; then
    if [ -d "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/chat" ]; then
      echo "$MELOS_ROOT_PATH/developer-dashboard/features/deployment/scripts/chat"
      return
    elif [ -d "$MELOS_ROOT_PATH/features/deployment/scripts/chat" ]; then
      echo "$MELOS_ROOT_PATH/features/deployment/scripts/chat"
      return
    fi
  fi
  local git_root
  git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$git_root" ]; then
    if [ -d "$git_root/developer-dashboard/features/deployment/scripts/chat" ]; then
      echo "$git_root/developer-dashboard/features/deployment/scripts/chat"
      return
    elif [ -d "$git_root/features/deployment/scripts/chat" ]; then
      echo "$git_root/features/deployment/scripts/chat"
      return
    fi
  fi
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}
CHAT_SCRIPT_DIR="$(resolve_chat_scripts_dir)"

if [ -f "$CHAT_SCRIPT_DIR/chat_android_utils.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_android_utils.sh
  source "$CHAT_SCRIPT_DIR/chat_android_utils.sh"
fi
if [ -f "$CHAT_SCRIPT_DIR/chat_ios_utils.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_ios_utils.sh
  source "$CHAT_SCRIPT_DIR/chat_ios_utils.sh"
fi
if [ -f "$CHAT_SCRIPT_DIR/chat_card_header.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_card_header.sh
  source "$CHAT_SCRIPT_DIR/chat_card_header.sh"
fi
if [ -f "$CHAT_SCRIPT_DIR/chat_card_sections.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_card_sections.sh
  source "$CHAT_SCRIPT_DIR/chat_card_sections.sh"
fi
if [ -f "$CHAT_SCRIPT_DIR/chat_card_failures.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_card_failures.sh
  source "$CHAT_SCRIPT_DIR/chat_card_failures.sh"
fi
if [ -f "$CHAT_SCRIPT_DIR/chat_helpers.sh" ]; then
  # shellcheck source=developer-dashboard/features/deployment/scripts/chat/chat_helpers.sh
  source "$CHAT_SCRIPT_DIR/chat_helpers.sh"
fi

if [ "${1:-}" != "--" ]; then
  die "Expected '--' before command. Example: chat_notify.sh -- melos run ..."
fi
shift
if [ "$#" -eq 0 ]; then
  die "Missing command after '--'."
fi
# shellcheck disable=SC2034
CMD_STR="$*"

ENV_JSON_RESOLVED=""
if [ -n "${ENV_JSON:-}" ]; then
  ENV_JSON_RESOLVED="$(resolve_env_json_path "$ENV_JSON" || true)"
fi

if [ -z "${GOOGLE_CHAT_WEBHOOK_URL:-}" ] && [ -n "$ENV_JSON_RESOLVED" ]; then
  GOOGLE_CHAT_WEBHOOK_URL="$(
    sed -n 's/.*"GOOGLE_CHAT_WEBHOOK_URL"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ENV_JSON_RESOLVED" \
      | tr -d '\r' \
      | xargs
  )"
  export GOOGLE_CHAT_WEBHOOK_URL
fi

APP_NAME="${APP_NAME:-Deployment}"
ENV_NAME="${ENV_NAME:-workspace}"
if [ -z "${LOCAL_DASHBOARD_URL:-}" ]; then
  DASHBOARD_HOST="${DEPLOYMENT_DASHBOARD_HOST:-${DASHBOARD_HOST:-localhost}}"
  DASHBOARD_PORT="${DEPLOYMENT_PORT:-${DASHBOARD_PORT:-18112}}"
  LOCAL_DASHBOARD_URL="http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
fi

if [ -z "${BRANCH_NAME:-}" ]; then
  BRANCH_NAME="${GITHUB_REF_NAME:-${CI_COMMIT_REF_NAME:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)}}"
fi

if [ -z "${BUILD_NO:-}" ]; then
  BUILD_NO="${GITHUB_RUN_NUMBER:-${BUILD_NUMBER:-${CI_PIPELINE_IID:-$(date +%Y%m%d%H%M)}}}"
fi

if [ -z "${CONTEXT:-}" ]; then
  CONTEXT="${CHANGE_CONTEXT:-$(git log -1 --pretty=%s 2>/dev/null || echo "$*")}"
fi

# Use a writable temp dir with more predictable capacity than /var/folders.
TMP_BASE="${TMPDIR:-/tmp}"
if [[ "${TMP_BASE%/}" == */deployment_dashboard_tmp ]]; then
  DEPLOYMENT_TMP_DIR="${TMP_BASE%/}"
else
  DEPLOYMENT_TMP_DIR="${TMP_BASE%/}/deployment_dashboard_tmp"
fi
mkdir -p "$DEPLOYMENT_TMP_DIR" >/dev/null 2>&1 || true

LOG_FILE=""
for _i in {1..5}; do
  LOG_FILE="$(mktemp "$DEPLOYMENT_TMP_DIR/deploy_cmd.XXXXXX" 2>/dev/null || true)"
  if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
    break
  fi
  LOG_FILE=""
done
if [ -z "$LOG_FILE" ]; then
  echo "ERROR: mktemp failed under: $DEPLOYMENT_TMP_DIR" >&2
  exit 1
fi

START_TS="$(date +%s)"

EXIT_CODE=0
if ! "$@" 2>&1 | tee "$LOG_FILE"; then
  EXIT_CODE=1
fi
END_TS="$(date +%s)"
DURATION_SEC="$((END_TS - START_TS))"
# shellcheck disable=SC2034
DURATION_TEXT="${DURATION_SEC}s"
if [ "$DURATION_SEC" -ge 60 ]; then
  # shellcheck disable=SC2034
  DURATION_TEXT="$((DURATION_SEC / 60))m $((DURATION_SEC % 60))s"
fi

NOW="$(date "+%A %e %B, %Y %I:%M %p" | tr -s ' ')"
if [ "$EXIT_CODE" -eq 0 ]; then
  STATUS_TEXT="SUCCESS"
else
  STATUS_TEXT="FAILURE"
fi

# shellcheck disable=SC2034
TITLE="$APP_NAME • $ENV_NAME • $BRANCH_NAME • #$BUILD_NO • $STATUS_TEXT"
BODY="Context: $CONTEXT
Time: $NOW
Command: $*"

if [ -n "${DOWNLOAD_URL:-}" ]; then
  BODY="$BODY
Download: $DOWNLOAD_URL"
fi

if [ "$EXIT_CODE" -ne 0 ]; then
  TAIL="$(tail -n 80 "$LOG_FILE" 2>/dev/null | tail -c 3500 || true)"
  BODY="$BODY

--- Last 80 log lines ---
$TAIL
Exit: $EXIT_CODE"
fi

NOTIFY_EXIT=0
if ! send_chat_card; then
  NOTIFY_EXIT=1
fi

rm -f "$LOG_FILE" >/dev/null 2>&1 || true
if [ "$NOTIFY_EXIT" -ne 0 ]; then
  exit "$NOTIFY_EXIT"
fi
exit "$EXIT_CODE"
