#!/bin/bash
# ===========================================================================
# Google Chat Notification iOS Utilities
# ===========================================================================

get_ios_platform_badge() {
  echo "iOS IPA"
}

get_ios_platform_icon_json() {
  echo ',"icon": {"iconUrl": "https://img.icons8.com/ios-filled/512/737373/mac-os.png"}'
}

analyze_ios_failure_logs() {
  local lc="$1"
  local root_cause=""
  local checklist=""
  
  if printf '%s' "$lc" | grep -Eq "provisioning profile|no profiles found|signing certificate|certificate"; then
    root_cause="Most likely cause: iOS signing or provisioning profile issue."
    checklist="• Check Apple Developer credentials in env file<br>• Verify App Store Connect API keys are valid<br>• Ensure Xcode project development team matches"
  elif printf '%s' "$lc" | grep -Eq "pod install|cocoapods|podfile|stale pods"; then
    root_cause="Most likely cause: CocoaPods dependency resolution failure."
    checklist="• Clean Pods directory and reinstall pods<br>• Verify Podfile and Podfile.lock match dependencies<br>• Run: flutter clean && flutter pub get && pod install --repo-update"
  elif printf '%s' "$lc" | grep -Eq "xcodebuild.*failed|xcodebuild error"; then
    root_cause="Most likely cause: Xcode build / compilation failure."
    checklist="• Check for Swift or Objective-C syntax compilation errors<br>• Validate Xcode scheme and target configurations<br>• Open runner in Xcode and build locally to debug"
  fi
  
  if [ -n "$root_cause" ]; then
    echo "${root_cause}|${checklist}"
  fi
}
