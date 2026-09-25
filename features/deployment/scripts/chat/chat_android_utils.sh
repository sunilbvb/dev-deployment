#!/bin/bash
# ===========================================================================
# Google Chat Notification Android Utilities
# ===========================================================================

get_android_platform_badge() {
  echo "Android AAB"
}

get_android_platform_icon_json() {
  echo ',"icon": {"iconUrl": "https://img.icons8.com/color/512/android-os.png"}'
}

analyze_android_failure_logs() {
  local lc="$1"
  local root_cause=""
  local checklist=""
  
  if printf '%s' "$lc" | grep -Eq "keystore|signing|key.properties|storepassword"; then
    root_cause="Most likely cause: Android signing/keystore configuration issue."
    checklist="• Verify key.properties exists and has correct passwords<br>• Validate keystore path and alias<br>• Re-run after confirming signing config"
  elif printf '%s' "$lc" | grep -Eq "jdk|java|unsupported class file|gradle.*version"; then
    root_cause="Most likely cause: JDK/Gradle compatibility mismatch."
    checklist="• Check active Java version matches Flutter/Gradle requirements<br>• Run flutter doctor and gradle wrapper check<br>• Clear Gradle cache and rebuild"
  fi
  
  if [ -n "$root_cause" ]; then
    echo "${root_cause}|${checklist}"
  fi
}
