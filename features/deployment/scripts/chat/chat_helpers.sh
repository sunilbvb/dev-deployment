#!/usr/bin/env bash
#------------------------------------------------------------------------------
# chat_helpers.sh - Google Chat Notification Helper & Driver Functions
#------------------------------------------------------------------------------

resolve_env_json_path() {
  local candidate="$1"
  if [ -z "$candidate" ]; then return 1; fi
  if [ -f "$candidate" ]; then echo "$candidate"; return 0; fi
  local script_root
  script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd || true)"
  if [ -n "$script_root" ] && [ -f "$script_root/$candidate" ]; then echo "$script_root/$candidate"; return 0; fi
  if [ -n "${MELOS_ROOT_PATH:-}" ] && [ -f "$MELOS_ROOT_PATH/$candidate" ]; then echo "$MELOS_ROOT_PATH/$candidate"; return 0; fi
  local git_root
  git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$git_root" ] && [ -f "$git_root/$candidate" ]; then echo "$git_root/$candidate"; return 0; fi
  return 1
}

json_escape() {
  printf '%s' "$1" | perl -0777 -pe 's/\\/\\\\/g; s/"/\\"/g; s/\r/\\r/g; s/\n/\\n/g;'
}

has_rg() {
  command -v rg >/dev/null 2>&1
}

derive_commit_sha() {
  git rev-parse --short HEAD 2>/dev/null || echo "unknown"
}

derive_build_version() {
  local app="${APP_NAME:-}"
  local pubspec=""
  if [ -n "$app" ] && [ -f "apps/${app}/pubspec.yaml" ]; then
    pubspec="apps/${app}/pubspec.yaml"
  elif [ -f "pubspec.yaml" ]; then
    pubspec="pubspec.yaml"
  fi
  if [ -z "$pubspec" ]; then
    echo "unknown"
    return
  fi
  local ver
  ver="$(sed -n 's/^version:[[:space:]]*//p' "$pubspec" | head -n 1 | tr -d '\r' | xargs)"
  if [ -z "$ver" ]; then
    echo "unknown"
    return
  fi
  echo "$ver"
}

derive_platform_badge() {
  local cmd="$1"
  local lower
  lower="$(printf '%s' "$cmd" | tr '[:upper:]' '[:lower:]')"
  if printf '%s' "$lower" | grep -Eq "aab|bundle"; then
    get_android_platform_badge
    return
  fi
  if printf '%s' "$lower" | grep -Eq "ipa|ios"; then
    get_ios_platform_badge
    return
  fi
  echo "Generic Build"
}

derive_platform_icon_json() {
  local cmd="$1"
  local lower
  lower="$(printf '%s' "$cmd" | tr '[:upper:]' '[:lower:]')"
  if printf '%s' "$lower" | grep -Eq "aab|bundle"; then
    get_android_platform_icon_json
    return
  fi
  if printf '%s' "$lower" | grep -Eq "ipa|ios"; then
    get_ios_platform_icon_json
    return
  fi
  echo ',"icon": {"knownIcon": "MEMBERSHIP"}'
}

get_profile_val() {
  local app_name="$1"
  local key="$2"
  local default_val="$3"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
  local config_file="$script_dir/build_profiles.json"
  if [ ! -f "$config_file" ]; then
    local root="${MELOS_ROOT_PATH:-}"
    if [ -z "$root" ]; then
      root="$(pwd | sed -E 's|/apps/[^/]+||' | sed -E 's|/packages/[^/]+||')"
    fi
    config_file="$root/developer-dashboard/features/deployment/scripts/build_profiles.json"
    if [ ! -f "$config_file" ]; then
      config_file="$root/features/deployment/scripts/build_profiles.json"
    fi
  fi
  if [ ! -f "$config_file" ]; then
    echo "$default_val"
    return
  fi

  local val
  val="$(python3 -c "
import json
data = json.load(open('$config_file'))
for prof, val in data.items():
    if val.get('app_name') == '$app_name':
        print(val.get('$key', ''))
        break
" 2>/dev/null)"

  if [ -z "$val" ]; then
    echo "$default_val"
  else
    echo "$val"
  fi
}

derive_app_icon() {
  local app
  app="$(printf '%s' "${APP_NAME:-}" | tr '[:upper:]' '[:lower:]')"
  get_profile_val "$app" "app_icon" "🛠️"
}

derive_app_logo_url() {
  local fallback_icon_url="$1"
  local app
  app="$(printf '%s' "${APP_NAME:-}" | tr '[:upper:]' '[:lower:]')"
  get_profile_val "$app" "app_logo_url" "$fallback_icon_url"
}

send_chat_text() {
  if [ -z "${GOOGLE_CHAT_WEBHOOK_URL:-}" ]; then
    return 0
  fi
  local text escaped http_code
  text="$1"
  escaped="$(json_escape "$text")"
  set +e
  http_code="$(
    curl -sS -X POST -H "Content-Type: application/json; charset=utf-8" \
      --data "{\"text\":\"$escaped\"}" \
      "$GOOGLE_CHAT_WEBHOOK_URL" \
      -w "%{http_code}" -o /dev/null
  )"
  set -e
}

send_chat_card() {
  if [ -z "${GOOGLE_CHAT_WEBHOOK_URL:-}" ]; then
    if [ "${REQUIRE_CHAT_NOTIFY:-0}" = "1" ]; then
      echo "ERROR: GOOGLE_CHAT_WEBHOOK_URL is missing (ENV_JSON=${ENV_JSON:-unset}${ENV_JSON_RESOLVED:+ -> $ENV_JSON_RESOLVED})." >&2
      return 2
    fi
    return 0
  fi

  local icon_url
  if [ "$EXIT_CODE" -eq 0 ]; then
    icon_url="https://raw.githubusercontent.com/google/material-design-icons/master/png/action/check_circle/ios/production_check_circle_3x_ios_48dp.png"
  else
    icon_url="https://raw.githubusercontent.com/google/material-design-icons/master/png/alert/error/ios/production_error_3x_ios_48dp.png"
  fi

  local escaped_context escaped_download_url escaped_ci_log_url escaped_rerun_url
  escaped_context="$(json_escape "$CONTEXT")"
  escaped_download_url="$(json_escape "${DOWNLOAD_URL:-}")"
  local local_log_url local_rerun_url
  local host_port="${LOCAL_DASHBOARD_URL#*//}"
  local host="${host_port%%:*}"
  local port="${host_port##*:}"
  if [ "$port" = "$host" ] || [ -z "$port" ]; then
    port="18082"
  fi
  local ssl_port="$((port + 1))"
  local_log_url="https://${host}:${ssl_port}/?tab=server&view=logs&app=${APP_NAME}&env=${ENV_NAME}&build=${BUILD_NO}"
  local_rerun_url="https://${host}:${ssl_port}/?tab=dashboard&action=rerun&app=${APP_NAME}&env=${ENV_NAME}&build=${BUILD_NO}"
  escaped_ci_log_url="$(json_escape "${CI_LOG_URL:-$local_log_url}")"
  escaped_rerun_url="$(json_escape "${RERUN_URL:-$local_rerun_url}")"

  local escaped_root_cause=""
  local checklist=""
  local grouped_bullets=""
  local fingerprint_id=""
  local seen_count=""
  local build_health_color=""
  local build_health=""
  local full_log_link_html=""
  if [ "$EXIT_CODE" -ne 0 ]; then
    local raw_tail
    raw_tail="$(tail -n 80 "$LOG_FILE" 2>/dev/null | tail -c 5000 || true)"
    # Strip ANSI escape codes (e.g. colors like [32m) using Perl
    raw_tail="$(printf '%s' "$raw_tail" | perl -pe 's/\e\[[0-9;]*[a-zA-Z]//g')"
    raw_tail="$(printf '%s' "$raw_tail" | sed '/^[[:space:]]*$/d')"
    full_log_link_html="View full log in CI/terminal artifact"
    if [ -n "${CI_LOG_URL:-}" ]; then
      full_log_link_html="<a href=\\\"$escaped_ci_log_url\\\">View full log</a>"
    fi
    local error_points
    error_points="$(printf '%s\n' "$raw_tail" | sed 's/^[[:space:]]*//' | sed '/^[[:space:]]*$/d' || true)"
    if [ -n "$error_points" ]; then
      local error_bullets=""
      local warning_bullets=""
      local failure_bullets=""
      local first_match
      first_match="$(printf '%s\n' "$error_points" | head -n 1)"
      local lc
      lc="$(printf '%s' "$raw_tail" | tr '[:upper:]' '[:lower:]')"
      # Delegate root cause analysis to platform-specific scripts
      local root_cause=""
      local checklist=""
      
      local lower_cmd
      lower_cmd="$(printf '%s' "$CMD_STR" | tr '[:upper:]' '[:lower:]')"
      
      if printf '%s' "$lower_cmd" | grep -Eq "aab|bundle"; then
        # Android
        local res
        res="$(analyze_android_failure_logs "$lc")"
        if [ -n "$res" ]; then
          root_cause="${res%%|*}"
          checklist="${res#*|}"
        fi
      elif printf '%s' "$lower_cmd" | grep -Eq "ipa|ios"; then
        # iOS
        local res
        res="$(analyze_ios_failure_logs "$lc")"
        if [ -n "$res" ]; then
          root_cause="${res%%|*}"
          checklist="${res#*|}"
        fi
      fi
      
      # Generic fallback if no platform-specific root cause was identified
      if [ -z "$root_cause" ]; then
        if printf '%s' "$lc" | grep -Eq "not found|no such file|missing"; then
          root_cause="Most likely cause: missing file or path configuration."
          checklist="• Verify referenced files/paths exist<br>• Check environment variables used by build scripts<br>• Re-run after fixing missing resources"
        elif printf '%s' "$lc" | grep -Eq "permission denied|eacces"; then
          root_cause="Most likely cause: file permission issue."
          checklist="• Ensure script/file execute permissions are set<br>• Check workspace write permissions<br>• Retry with corrected permissions"
        else
          root_cause="Build/runtime failure detected from logs."
          checklist="• Retry once with clean cache<br>• Check latest failing command output"
        fi
      fi
      local escaped_root_cause
      escaped_root_cause="$(json_escape "$root_cause")"

      while IFS= read -r line; do
        [ -z "$line" ] && continue
        if [ "${#line}" -gt 180 ]; then
          line="${line:0:177}..."
        fi
        local lc_line
        lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
        # Skip tool update warnings, eol warnings, bundler notices, changelog bullets, and success lines in the error block
        if printf '%s' "$lc_line" | grep -Eq "is available|latest version|please update|bundle update|improvements|via |appreciate fastlane|opencollective|new releases|ruby.*eol|rubygems|bundle exec fastlane|upload completed|build completed|^\* \[[^]]+\]|^\* [a-z0-9_-]+(\([^)]+\))?:"; then
          continue
        fi
        local escaped_line
        escaped_line="$(json_escape "$line")"
        if printf '%s' "$lc_line" | grep -Eq "warning|warn"; then
          warning_bullets="${warning_bullets}• ${escaped_line}<br>"
        elif printf '%s' "$lc_line" | grep -Eq "fail|failure|failed|exit code"; then
          failure_bullets="${failure_bullets}• ${escaped_line}<br>"
        else
          error_bullets="${error_bullets}• ${escaped_line}<br>"
        fi
      done <<< "$error_points"
      local grouped_bullets=""
      if [ -n "$error_bullets" ]; then
        grouped_bullets="${grouped_bullets}<b>Errors</b><br>${error_bullets}<br>"
      fi
      if [ -n "$warning_bullets" ]; then
        grouped_bullets="${grouped_bullets}<b>Warnings</b><br>${warning_bullets}<br>"
      fi
      if [ -n "$failure_bullets" ]; then
        grouped_bullets="${grouped_bullets}<b>Failures</b><br>${failure_bullets}<br>"
      fi
      if [ -z "$grouped_bullets" ]; then
        grouped_bullets="<i>No categorized lines found.</i><br>"
      fi

      local fingerprint_source
      fingerprint_source="$(printf '%s\n%s' "$first_match" "$CONTEXT" | tr -s ' ')"
      local fingerprint_id
      fingerprint_id="$(printf '%s' "$fingerprint_source" | shasum | awk '{print substr($1,1,10)}')"
      local fp_dir="${DEPLOYMENT_TMP_DIR:-${TMPDIR:-/tmp}}/chat_notify_fingerprints"
      local fp_file
      fp_file="$fp_dir/week_$(date +%G%V).txt"
      mkdir -p "$fp_dir" >/dev/null 2>&1 || true
      touch "$fp_file" >/dev/null 2>&1 || true
      printf '%s\n' "$fingerprint_id" >> "$fp_file"
      local seen_count
      if has_rg; then
        seen_count="$(rg -n "^${fingerprint_id}$" "$fp_file" | wc -l | tr -d '[:space:]')"
      else
        seen_count="$(grep -Ec "^${fingerprint_id}$" "$fp_file" | tr -d '[:space:]')"
      fi
      local build_health="Recovered"
      local build_health_color="#3498db"
      if [ "${seen_count:-0}" -ge 5 ]; then
        build_health="Flaky"
        build_health_color="#f39c12"
      fi
    fi
  fi

  local commit_sha build_version platform_badge platform_icon_json app_icon
  commit_sha="$(derive_commit_sha)"
  build_version="$(derive_build_version)"
  platform_badge="$(derive_platform_badge "$CMD_STR")"
  platform_icon_json="$(derive_platform_icon_json "$CMD_STR")"
  app_icon="$(derive_app_icon)"

  local status_text status_color status_emoji pipeline_stages_text
  if [ "$EXIT_CODE" -eq 0 ]; then
    status_text="SUCCESS"
    status_color="#1D9E75"
    status_emoji="✅"
    pipeline_stages_text="✅ Checkout  →  ✅ Build  →  ✅ Test  →  ✅ Package  →  ✅ Deploy"
  else
    status_text="FAILURE"
    status_color="#e74c3c"
    status_emoji="❌"
    pipeline_stages_text="✅ Checkout  →  ❌ Failure  →  ⏭️ Skipped"
  fi

  local triggered_by
  triggered_by="$(git config user.name 2>/dev/null || echo "CI/User")"
  local escaped_triggered_by
  escaped_triggered_by="$(json_escape "$triggered_by")"

  # Handle filesystem image path or public app logo URL
  local logo_image_url=""
  local webhook_dest_image_url="$logo_image_url"
  if [[ "${GOOGLE_CHAT_WEBHOOK_URL:-}" == https://chat.googleapis.com/* ]]; then
    webhook_dest_image_url="$(derive_app_logo_url "$icon_url")"
  fi

  local env_upper
  env_upper="$(echo "${ENV_NAME}" | tr '[:lower:]' '[:upper:]')"

  # Construct new action buttons array
  local action_buttons_json=""
  if [ -n "${DOWNLOAD_URL:-}" ]; then
    action_buttons_json="${action_buttons_json}
                    {
                      \"text\": \"📦 Open Artifact\",
                      \"onClick\": { \"openLink\": { \"url\": \"$escaped_download_url\" } }
                    },"
  fi
  action_buttons_json="${action_buttons_json}
                    {
                      \"text\": \"📋 CI Log\",
                      \"onClick\": { \"openLink\": { \"url\": \"$escaped_ci_log_url\" } }
                    },"
  action_buttons_json="${action_buttons_json}
                    {
                      \"text\": \"🔁 Rerun\",
                      \"onClick\": { \"openLink\": { \"url\": \"$escaped_rerun_url\" } }
                    },"
  action_buttons_json="$(printf '%s' "$action_buttons_json" | perl -0777 -pe 's/,[[:space:]]*\z//')"

  local card_payload
  card_payload="$(cat <<EOF
{
  "cardsV2": [
    {
      "cardId": "deployment-card",
      "card": {
        $(build_header_widget "$app_icon" "$APP_NAME" "$BUILD_NO" "$platform_badge" "$BRANCH_NAME" "$ENV_NAME" "$webhook_dest_image_url"),
        "sections": [
          $(build_status_section "$status_color" "$status_emoji" "$status_text" "$DURATION_TEXT" "$escaped_download_url"),
          $(build_details_section "$escaped_triggered_by" "$NOW" "$env_upper" "$commit_sha" "$escaped_context"),
          $(build_build_info_section "$build_version" "$platform_badge" "$platform_icon_json"),
          $(build_buttons_section "$action_buttons_json")
          $(build_root_cause_widget "${escaped_root_cause:-}")
          $(build_checklist_widget "${checklist:-}")
          $(build_error_logs_widget "${grouped_bullets:-}" "${full_log_link_html:-}")
          $(build_fingerprint_widget "${fingerprint_id:-}" "${seen_count:-}" "${build_health_color:-}" "${build_health:-}")
        ]
      }
    }
  ]
}
EOF
)"

  # Try to stash the payload for the 'Send to Official Group' forwarder
  local build_id="${commit_sha}_${BUILD_NO}"
  local stash_code
  set +e
  stash_code="$(curl -sS -X POST -H "Content-Type: application/json; charset=utf-8" \
    --data "$card_payload" \
    "${LOCAL_DASHBOARD_URL:-http://localhost:18082}/api/webhook/stash?id=$build_id" \
    -w "%{http_code}" -o /dev/null || echo "000")"
  set -e
  
  if [ "$stash_code" = "200" ]; then
    action_buttons_json="${action_buttons_json},
                    {
                      \"text\": \"🚀 Send to Official Group\",
                      \"onClick\": { \"openLink\": { \"url\": \"${LOCAL_DASHBOARD_URL:-http://localhost:18082}/api/webhook/forward?id=$build_id\" } }
                    }"
    # Rebuild with new buttons
    card_payload="$(cat <<EOF
{
  "cardsV2": [
    {
      "cardId": "deployment-card",
      "card": {
        $(build_header_widget "$app_icon" "$APP_NAME" "$BUILD_NO" "$platform_badge" "$BRANCH_NAME" "$ENV_NAME" "$webhook_dest_image_url"),
        "sections": [
          $(build_status_section "$status_color" "$status_emoji" "$status_text" "$DURATION_TEXT" "$escaped_download_url"),
          $(build_details_section "$escaped_triggered_by" "$NOW" "$env_upper" "$commit_sha" "$escaped_context"),
          $(build_build_info_section "$build_version" "$platform_badge" "$platform_icon_json"),
          $(build_buttons_section "$action_buttons_json")
          $(build_root_cause_widget "${escaped_root_cause:-}")
          $(build_checklist_widget "${checklist:-}")
          $(build_error_logs_widget "${grouped_bullets:-}" "${full_log_link_html:-}")
          $(build_fingerprint_widget "${fingerprint_id:-}" "${seen_count:-}" "${build_health_color:-}" "${build_health:-}")
        ]
      }
    }
  ]
}
EOF
)"
  fi

  set +e
  local http_code response_body_file
  response_body_file="$(mktemp "${DEPLOYMENT_TMP_DIR:-${TMPDIR:-/tmp}}/chat_resp.XXXXXX" 2>/dev/null || echo "/tmp/chat_resp.json")"
  http_code="$(
    curl -sS -X POST -H "Content-Type: application/json; charset=utf-8" \
      --data "$card_payload" \
      "$GOOGLE_CHAT_WEBHOOK_URL" \
      -w "%{http_code}" -o "$response_body_file"
  )"
  local curl_exit="$?"
  set -e
  if [ "$curl_exit" -ne 0 ] || [ -z "$http_code" ]; then
    http_code="000"
  fi
  if [ "$http_code" = "000" ] || [ "$http_code" -ge 400 ]; then
    echo "ERROR: Google Chat webhook post failed (HTTP $http_code)." >&2
    if [ -f "$response_body_file" ]; then
      echo "--- Response Body ---" >&2
      cat "$response_body_file" >&2
      echo "" >&2
      rm -f "$response_body_file"
    fi
    echo "--- Sent Card Payload ---" >&2
    echo "$card_payload" >&2
    # Fallback to simple text if card payload fails
    send_chat_text "$TITLE
$BODY"
    return 3
  fi
  rm -f "$response_body_file" >/dev/null 2>&1 || true
}
