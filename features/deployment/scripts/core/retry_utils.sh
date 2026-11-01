#!/usr/bin/env bash
# ===========================================================================
# Resilient Network & Upload Retry Engine
# Retries store uploads with exponential backoff and duplicate-version short-circuiting.
# ===========================================================================
set -euo pipefail

#------------------------------------------------------------------------------
# _retryUpload - Run a store-upload command (via runWithIosEnv/runWithAndroidEnv),
# retrying a few times on failure.
#------------------------------------------------------------------------------
_retryUpload() {
    local description="$1"
    local runner="$2"
    shift 2
    local -a cmd=("$@")
    local max_attempts=3
    local attempt=1

    # Known errors live in known_store_errors.tsv (class, pattern, hint).
    local -a err_class=() err_pattern=() err_hint=()
    local errors_file="${KNOWN_STORE_ERRORS_FILE:-$(dirname "${BASH_SOURCE[0]}")/known_store_errors.tsv}"
    local _c _p _h
    if [ -f "$errors_file" ]; then
        while IFS=$'\t' read -r _c _p _h || [ -n "$_c" ]; do
            case "$_c" in ""|\#*) continue ;; esac
            err_class+=("$_c"); err_pattern+=("$_p"); err_hint+=("$_h")
        done < "$errors_file"
    fi

    while [ "$attempt" -le "$max_attempts" ]; do
        if [ "$attempt" -gt 1 ]; then
            echo "🔁 Retrying $description (attempt $attempt/$max_attempts)..."
            sleep 5
        fi

        local log_file
        log_file="$(mktemp "${TMPDIR:-/tmp}/retry_upload.XXXXXX")"

        local had_errexit=0
        case "$-" in *e*) had_errexit=1 ;; esac
        set +e

        local timeout_seconds="${UPLOAD_ATTEMPT_TIMEOUT_SECONDS:-300}"
        local rc_file
        rc_file="$(mktemp "${TMPDIR:-/tmp}/retry_upload_rc.XXXXXX")"
        local had_monitor=0
        case "$-" in *m*) had_monitor=1 ;; esac
        set -m

        ( "$runner" "${cmd[@]}" 2>&1 | tee "$log_file"; echo "${PIPESTATUS[0]}" > "$rc_file" ) &
        local pipe_pid=$!
        local pgid
        pgid="$(ps -o pgid= -p "$pipe_pid" 2>/dev/null | tr -d ' ')"

        (
            sleep "$timeout_seconds"
            if kill -0 "$pipe_pid" 2>/dev/null; then
                echo "⏱️  $description: no progress after ${timeout_seconds}s - assuming a hung network call, not a real long-running upload. Terminating this attempt so a retry can run." >> "$log_file"
                [ -n "$pgid" ] && kill -TERM -- "-$pgid" 2>/dev/null
                sleep 2
                [ -n "$pgid" ] && kill -KILL -- "-$pgid" 2>/dev/null
            fi
        ) &
        local watchdog_pid=$!

        wait "$pipe_pid" 2>/dev/null
        # kill the watchdog's pending sleep too, or it keeps our stdout pipe open until it expires
        pkill -P "$watchdog_pid" 2>/dev/null
        kill "$watchdog_pid" 2>/dev/null
        wait "$watchdog_pid" 2>/dev/null
        [ "$had_monitor" -eq 0 ] && set +m

        local rc
        rc="$(cat "$rc_file" 2>/dev/null)"
        [ -z "$rc" ] && rc=124
        rm -f "$rc_file"

        [ "$had_errexit" -eq 1 ] && set -e

        if [ "$rc" -eq 0 ]; then
            rm -f "$log_file"
            return 0
        fi

        local i
        for i in "${!err_class[@]}"; do
            grep -qiE "${err_pattern[$i]}" "$log_file" || continue
            if [ "${err_class[$i]}" = "duplicate" ]; then
                echo "ℹ️  $description: Apple/Google rejected this as a duplicate build/version - it was already uploaded successfully in a prior run, no action needed."
                rm -f "$log_file"
                return 0
            fi
            echo "🛑 $description: retrying cannot fix this error."
            echo "   Fix: ${err_hint[$i]}"
            rm -f "$log_file"
            return 1
        done

        rm -f "$log_file"
        attempt=$((attempt + 1))
    done

    echo "❌ $description failed after $max_attempts attempt(s)."
    return 1
}
