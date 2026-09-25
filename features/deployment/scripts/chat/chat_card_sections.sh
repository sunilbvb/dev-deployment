#!/usr/bin/env bash
#------------------------------------------------------------------------------
# chat_card_sections.sh - Google Chat Card Section Widgets
#------------------------------------------------------------------------------

build_status_section() {
  local status_color="$1"
  local status_emoji="$2"
  local status_text="$3"
  local duration_text="$4"
  local escaped_download_url="$5"

  cat <<EOF
            {
              "header": "Build Status",
              "collapsible": false,
              "widgets": [
                {
                  "decoratedText": {
                    "topLabel": "Status",
                    "text": "<font color=\\"$status_color\\"><b>$status_emoji $status_text</b></font>"
                  }
                },
                {
                  "decoratedText": {
                    "topLabel": "Duration",
                    "text": "$duration_text",
                    "startIcon": { "knownIcon": "CLOCK" }
                  }
                }$(
                  if [ -n "$escaped_download_url" ]; then
                    cat <<SUB_EOF
                ,{
                  "decoratedText": {
                    "topLabel": "Download Link",
                    "text": "<a href=\\"$escaped_download_url\\">$escaped_download_url</a>"
                  }
                }
SUB_EOF
                  fi
                )
              ]
            }
EOF
}

build_pipeline_stages_section() {
  local pipeline_stages_text="$1"
  cat <<EOF
            {
              "header": "Pipeline Stages",
              "collapsible": false,
              "widgets": [
                {
                  "textParagraph": {
                    "text": "$pipeline_stages_text"
                  }
                }
              ]
            }
EOF
}

build_details_section() {
  local escaped_triggered_by="$1"
  local now="$2"
  local env_upper="$3"
  local commit_sha="$4"
  local escaped_context="$5"

  cat <<EOF
            {
              "header": "Details",
              "collapsible": false,
              "widgets": [
                {
                  "columns": {
                    "columnItems": [
                      {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "widgets": [
                          {
                            "decoratedText": {
                              "topLabel": "Triggered by",
                              "text": "$escaped_triggered_by"
                            }
                          },
                          {
                            "decoratedText": {
                              "topLabel": "Time",
                              "text": "$now"
                            }
                          }
                        ]
                      },
                      {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "widgets": [
                          {
                            "decoratedText": {
                              "topLabel": "Environment",
                              "text": "$env_upper"
                            }
                          },
                          {
                            "decoratedText": {
                              "topLabel": "Commit",
                              "text": "$commit_sha"
                            }
                          },
                          {
                            "decoratedText": {
                              "topLabel": "Context",
                              "text": "$escaped_context"
                            }
                          }
                        ]
                      }
                    ]
                  }
                }
              ]
            }
EOF
}

build_build_info_section() {
  local build_version="$1"
  local platform_badge="$2"
  local platform_icon_json="$3"

  cat <<EOF
            {
              "header": "Build Info",
              "collapsible": false,
              "widgets": [
                {
                  "columns": {
                    "columnItems": [
                      {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "widgets": [
                          {
                            "decoratedText": {
                              "topLabel": "Version",
                              "text": "$build_version"
                            }
                          }
                        ]
                      },
                      {
                        "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                        "widgets": [
                          {
                            "decoratedText": {
                              "topLabel": "Platform",
                              "text": "$platform_badge"
                              $platform_icon_json
                            }
                          }
                        ]
                      }
                    ]
                  }
                }
              ]
            }
EOF
}

build_buttons_section() {
  local action_buttons_json="$1"

  cat <<EOF
            {
              "widgets": [
                {
                  "buttonList": {
                    "buttons": [
                      $action_buttons_json
                    ]
                  }
                }
              ]
            }
EOF
}
