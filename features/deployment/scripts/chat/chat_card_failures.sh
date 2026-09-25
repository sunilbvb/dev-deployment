#!/usr/bin/env bash
#------------------------------------------------------------------------------
# chat_card_failures.sh - Google Chat Card Failure Diagnostic Widgets
#------------------------------------------------------------------------------

build_root_cause_widget() {
  local escaped_root_cause="$1"
  [ -z "$escaped_root_cause" ] && return
  cat <<EOF
            ,{
              "header": "Smart Root Cause",
              "widgets": [{"textParagraph": {"text": "<b>$escaped_root_cause</b>"}}]
            }
EOF
}

build_checklist_widget() {
  local checklist="$1"
  [ -z "$checklist" ] && return
  cat <<EOF
            ,{
              "header": "Try This First",
              "widgets": [{"textParagraph": {"text": "$checklist"}}]
            }
EOF
}

build_error_logs_widget() {
  local grouped_bullets="$1"
  local full_log_link_html="$2"
  [ -z "$grouped_bullets" ] && return
  cat <<EOF
            ,{
              "header": "Error Logs (Bulleted)",
              "widgets": [
                {
                  "textParagraph": {
                    "text": "<font color=\\"#ffb3b3\\">$grouped_bullets</font>$full_log_link_html"
                  }
                }
              ]
            }
EOF
}

build_fingerprint_widget() {
  local fingerprint_id="$1"
  local seen_count="$2"
  local build_health_color="$3"
  local build_health="$4"
  [ -z "$fingerprint_id" ] && return
  cat <<EOF
            ,{
              "header": "Failure Fingerprint",
              "widgets": [{"textParagraph": {"text": "ID: <code>${fingerprint_id}</code><br>Seen <b>${seen_count}</b> time(s) this week<br><b>Build Health:</b> <font color=\\"${build_health_color}\\"><b>${build_health}</b></font>"}}]
            }
EOF
}
