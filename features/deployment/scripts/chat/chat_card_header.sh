#!/usr/bin/env bash
#------------------------------------------------------------------------------
# chat_card_header.sh - Google Chat Card Header Widget
#------------------------------------------------------------------------------

build_header_widget() {
  local app_icon="$1"
  local app_name="$2"
  local build_no="$3"
  local platform_badge="$4"
  local branch_name="$5"
  local env_name="$6"
  local webhook_dest_image_url="$7"

  cat <<EOF
        "header": {
          "title": "$app_icon $app_name  •  #$build_no",
          "subtitle": "$platform_badge  •  Branch: $branch_name  •  $env_name",
          "imageUrl": "$webhook_dest_image_url",
          "imageType": "CIRCLE"
        }
EOF
}
