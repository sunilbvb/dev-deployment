"""Project and platform environment checks (Android, iOS, Credentials, Pubspec)."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
from typing import Any

import credentials
import jobs
from .tool_checks import _check_tool


def _check_app_project(app_id: str, app_dir: Path) -> list[dict[str, Any]]:
    """Verify app structure, pubspec.yaml existence, dependencies lockfile, and package name."""
    checks = []

    if not app_dir.is_dir():
        checks.append({
            "id": "app_dir_exists",
            "category": "project",
            "name": "App Directory",
            "status": "fail",
            "message": f"Resolved app directory does not exist: {app_dir}",
            "hint": "Check workspace app layout or rescan project in Dashboard Setup.",
        })
        return checks

    checks.append({
        "id": "app_dir_exists",
        "category": "project",
        "name": "App Directory",
        "status": "pass",
        "message": f"App root directory exists ({app_dir.name})",
        "path": str(app_dir),
    })

    pubspec_file = app_dir / "pubspec.yaml"
    if not pubspec_file.exists():
        checks.append({
            "id": "pubspec_yaml",
            "category": "project",
            "name": "pubspec.yaml",
            "status": "fail",
            "message": "pubspec.yaml missing in app directory",
            "hint": "Flutter app requires a valid pubspec.yaml file.",
        })
        return checks

    try:
        content = pubspec_file.read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*([a-zA-Z0-9_-]+)", content, re.MULTILINE)
        version_match = re.search(r"^version:\s*([0-9a-zA-Z\.\+\-_]+)", content, re.MULTILINE)
        sdk_match = re.search(r"sdk:\s*['\"]?([^'\"\r\n]+)['\"]?", content)

        app_name = name_match.group(1) if name_match else app_id
        version = version_match.group(1) if version_match else "unknown"
        sdk_constraint = sdk_match.group(1).strip() if sdk_match else "unspecified"

        checks.append({
            "id": "pubspec_yaml",
            "category": "project",
            "name": "pubspec.yaml",
            "status": "pass",
            "message": f"Package '{app_name}' v{version} (SDK constraint: {sdk_constraint})",
            "version": version,
            "appName": app_name,
        })
    except Exception as exc:
        checks.append({
            "id": "pubspec_yaml",
            "category": "project",
            "name": "pubspec.yaml",
            "status": "warn",
            "message": f"Could not parse pubspec.yaml: {exc}",
        })

    lock_file = app_dir / "pubspec.lock"
    if lock_file.exists():
        checks.append({
            "id": "pubspec_lock",
            "category": "project",
            "name": "Dependencies Lockfile",
            "status": "pass",
            "message": "Dependencies resolved (pubspec.lock present)",
        })
    else:
        checks.append({
            "id": "pubspec_lock",
            "category": "project",
            "name": "Dependencies Lockfile",
            "status": "warn",
            "message": "pubspec.lock missing — packages have not been resolved yet",
            "hint": "Run 'flutter pub get' in the app directory before building.",
        })

    return checks


def _check_android_env(app_dir: Path, app_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Check Android SDK, JDK, ANDROID_HOME, and gradlew wrapper."""
    android_dir = app_dir / "android"
    if not android_dir.is_dir():
        return []

    checks = []

    # 1. Java / JDK
    java_path = shutil.which("java")
    if java_path:
        java_info = _check_tool("java", "-version")
        ver_str = java_info["version"] or "available"
        checks.append({
            "id": "android_java",
            "category": "android",
            "name": "Java / JDK Runtime",
            "status": "pass",
            "message": f"Java available ({ver_str})",
            "path": java_path,
        })
    else:
        checks.append({
            "id": "android_java",
            "category": "android",
            "name": "Java / JDK Runtime",
            "status": "fail",
            "message": "Java (JDK) not found in PATH",
            "hint": "Install OpenJDK 17 or JDK 21 (e.g. apt install openjdk-17-jdk or brew install openjdk@17).",
        })

    # 2. JAVA_HOME variable
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        if Path(java_home).is_dir():
            checks.append({
                "id": "android_java_home",
                "category": "android",
                "name": "JAVA_HOME Variable",
                "status": "pass",
                "message": f"JAVA_HOME is set: {java_home}",
            })
        else:
            checks.append({
                "id": "android_java_home",
                "category": "android",
                "name": "JAVA_HOME Variable",
                "status": "fail",
                "message": f"JAVA_HOME points to non-existent directory: '{java_home}'",
                "hint": "Update JAVA_HOME in your ~/.bashrc or ~/.zshrc profile to a valid JDK path.",
            })
    else:
        checks.append({
            "id": "android_java_home",
            "category": "android",
            "name": "JAVA_HOME Variable",
            "status": "warn",
            "message": "JAVA_HOME environment variable is not set.",
            "hint": "Export JAVA_HOME to prevent Gradle build failures: export JAVA_HOME=$(dirname $(dirname $(which java)))",
        })

    # 3. Android SDK (ANDROID_HOME / ANDROID_SDK_ROOT)
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    sdk_found_path = None
    if android_home and Path(android_home).is_dir():
        sdk_found_path = Path(android_home)
    else:
        home = Path.home()
        candidates = [
            home / "Android" / "Sdk",
            home / "Library" / "Android" / "sdk",
            Path("/usr/lib/android-sdk"),
            home / ".android-sdk",
        ]
        for c in candidates:
            if c.is_dir():
                sdk_found_path = c
                break

    if sdk_found_path:
        if android_home:
            checks.append({
                "id": "android_sdk",
                "category": "android",
                "name": "Android SDK",
                "status": "pass",
                "message": f"Android SDK located at {sdk_found_path}",
            })
        else:
            checks.append({
                "id": "android_sdk",
                "category": "android",
                "name": "Android SDK",
                "status": "warn",
                "message": f"Found Android SDK at '{sdk_found_path}', but ANDROID_HOME is not exported.",
                "hint": f"Export variable: export ANDROID_HOME=\"{sdk_found_path}\"",
            })
    else:
        checks.append({
            "id": "android_sdk",
            "category": "android",
            "name": "Android SDK",
            "status": "warn",
            "message": "Android SDK not found and ANDROID_HOME is unset.",
            "hint": "Install Android Command Line Tools or Android Studio and set ANDROID_HOME.",
        })

    # 4. Gradle wrapper
    gradlew = android_dir / "gradlew"
    if gradlew.exists():
        if os.access(gradlew, os.X_OK):
            checks.append({
                "id": "android_gradlew",
                "category": "android",
                "name": "Gradle Wrapper",
                "status": "pass",
                "message": "Gradle wrapper present and executable (android/gradlew)",
            })
        else:
            checks.append({
                "id": "android_gradlew",
                "category": "android",
                "name": "Gradle Wrapper",
                "status": "fail",
                "message": "android/gradlew exists but lacks execute permissions (+x)",
                "hint": f"Fix permissions: chmod +x {gradlew}",
            })
    else:
        checks.append({
            "id": "android_gradlew",
            "category": "android",
            "name": "Gradle Wrapper",
            "status": "warn",
            "message": "android/gradlew wrapper is missing",
            "hint": "Run 'flutter create .' in app directory to restore standard Android wrapper.",
        })

    # 5. Android Package ID
    cfg_pkg = app_cfg.get("android_package") or app_cfg.get("android_id_prod") or app_cfg.get("android_id_default")
    if cfg_pkg:
        checks.append({
            "id": "android_package_id",
            "category": "android",
            "name": "Android Package ID",
            "status": "pass",
            "message": f"Configured Package ID: {cfg_pkg}",
        })
    else:
        checks.append({
            "id": "android_package_id",
            "category": "android",
            "name": "Android Package ID",
            "status": "warn",
            "message": "Android package ID not configured in deploy_config.json.",
            "hint": "Set package ID in Dashboard Setup -> General tab.",
        })

    return checks


def _check_ios_env(app_id: str, app_dir: Path, app_cfg: dict[str, Any], flavor: str = "prod") -> list[dict[str, Any]]:
    """Check Xcode, CocoaPods, Bundle ID, and iOS certificates / profiles."""
    ios_dir = app_dir / "ios"
    if not ios_dir.is_dir():
        return []

    checks = []
    is_macos = platform.system() == "Darwin"

    if not is_macos:
        checks.append({
            "id": "ios_host",
            "category": "ios",
            "name": "iOS Build Host",
            "status": "info",
            "message": f"Host OS is {platform.system()}. iOS archive/IPA generation requires macOS (or CI/CD runner). Android builds are unaffected.",
        })
    else:
        xcode_path = shutil.which("xcodebuild")
        if xcode_path:
            xcode_info = _check_tool("xcodebuild", "-version")
            checks.append({
                "id": "ios_xcode",
                "category": "ios",
                "name": "Xcode Command Line Tools",
                "status": "pass",
                "message": xcode_info["version"] or f"Xcode available ({xcode_path})",
                "path": xcode_path,
            })
        else:
            checks.append({
                "id": "ios_xcode",
                "category": "ios",
                "name": "Xcode Command Line Tools",
                "status": "fail",
                "message": "xcodebuild not found in PATH",
                "hint": "Install Xcode from the Mac App Store and run: xcode-select --install",
            })

        pod_path = shutil.which("pod")
        if pod_path:
            pod_info = _check_tool("pod", "--version")
            checks.append({
                "id": "ios_cocoapods",
                "category": "ios",
                "name": "CocoaPods",
                "status": "pass",
                "message": f"CocoaPods v{pod_info['version'] or 'available'}",
                "path": pod_path,
            })
        else:
            checks.append({
                "id": "ios_cocoapods",
                "category": "ios",
                "name": "CocoaPods",
                "status": "warn",
                "message": "CocoaPods ('pod') not found in PATH.",
                "hint": "Install CocoaPods: sudo gem install cocoapods or brew install cocoapods",
            })

    bundle_id = app_cfg.get("bundle_id") or app_cfg.get("bundle_id_prod") or app_cfg.get("bundle_id_default")
    if bundle_id:
        checks.append({
            "id": "ios_bundle_id",
            "category": "ios",
            "name": "iOS Bundle Identifier",
            "status": "pass",
            "message": f"Configured Bundle ID: {bundle_id}",
        })
    else:
        checks.append({
            "id": "ios_bundle_id",
            "category": "ios",
            "name": "iOS Bundle Identifier",
            "status": "warn",
            "message": "iOS Bundle Identifier not configured in deploy_config.json.",
            "hint": "Set Bundle ID in Dashboard Setup -> iOS tab.",
        })

    try:
        cert_res = jobs.check_ios_expiry(app_id, flavor=flavor or "prod")
        status_key = cert_res.get("status")
        if status_key == "ok":
            checks.append({
                "id": "ios_cert_status",
                "category": "ios",
                "name": "iOS Signing & Provisioning Profile",
                "status": "pass",
                "message": f"Prod distribution certificate & profile valid until {cert_res.get('provisioningProfile', {}).get('expiresOn') or cert_res.get('certificate', {}).get('expiresOn') or 'OK'}",
            })
        elif status_key == "warning":
            checks.append({
                "id": "ios_cert_status",
                "category": "ios",
                "name": "iOS Signing & Provisioning Profile",
                "status": "warn",
                "message": "iOS Certificate or Provisioning Profile is expiring soon (<30 days)!",
                "hint": "Renew distribution certificate / profile in Apple Developer Portal.",
            })
        elif status_key == "expired":
            checks.append({
                "id": "ios_cert_status",
                "category": "ios",
                "name": "iOS Signing & Provisioning Profile",
                "status": "fail",
                "message": "iOS Distribution Certificate or Provisioning Profile is EXPIRED! Builds will fail.",
                "hint": "Generate a new certificate / profile in Apple Developer Portal.",
            })
    except Exception:
        pass

    return checks


def _check_credentials(app_id: str, app_dir: Path) -> list[dict[str, Any]]:
    """Check Google Play and Apple App Store API credentials."""
    checks = []
    try:
        cred_stat = credentials.get_credentials_status(app_id)
    except Exception as exc:
        checks.append({
            "id": "credentials_status",
            "category": "credentials",
            "name": "Credentials Status",
            "status": "info",
            "message": f"Could not inspect credentials: {exc}",
        })
        return checks

    # 1. Google Play Service Account Key
    play = cred_stat.get("play")
    has_android = (app_dir / "android").is_dir()
    if play and play.get("exists") and play.get("valid"):
        client_email = play.get("client_email") or "service-account"
        checks.append({
            "id": "cred_play",
            "category": "credentials",
            "name": "Google Play API Key",
            "status": "pass",
            "message": f"Play Store service account configured ({client_email})",
        })
    elif has_android:
        checks.append({
            "id": "cred_play",
            "category": "credentials",
            "name": "Google Play API Key",
            "status": "warn",
            "message": "Play Store service account JSON is not configured.",
            "hint": "Android uploads will fail until a key is added. Go to Setup -> Android Credentials to import.",
        })

    # 2. Apple App Store Connect API Key (.p8)
    apple = cred_stat.get("apple")
    has_ios = (app_dir / "ios").is_dir()
    if apple and apple.get("exists"):
        key_id = apple.get("key_id") or "configured"
        checks.append({
            "id": "cred_apple",
            "category": "credentials",
            "name": "App Store Connect API Key (.p8)",
            "status": "pass",
            "message": f"App Store Connect key present (Key ID: {key_id})",
        })
    elif has_ios:
        checks.append({
            "id": "cred_apple",
            "category": "credentials",
            "name": "App Store Connect API Key (.p8)",
            "status": "warn",
            "message": "App Store Connect API key (.p8) is not configured.",
            "hint": "TestFlight uploads will fail until AuthKey_<KEYID>.p8 is uploaded in Setup -> iOS Credentials.",
        })

    return checks
