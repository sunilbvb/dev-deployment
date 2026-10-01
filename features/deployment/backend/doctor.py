"""App Doctor: 1-Click Pre-flight Diagnostics for Deployment Console.

Checks toolchains, SDKs, Android/iOS environments, signing credentials,
and Git readiness before running long-running deployment jobs and pipelines.
Python standard library only.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
from typing import Any, Optional

from config import (
    _resolve_app_dir,
    get_workspace_root,
    load_deploy_config,
)
import credentials
import jobs


def _check_tool(cmd: str, flag: str = "--version", timeout: float = 2.5) -> dict[str, Any]:
    """Locate executable and retrieve its version output."""
    path = shutil.which(cmd)
    if not path:
        return {"available": False, "path": None, "version": None, "raw": None}
    try:
        res = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=timeout)
        raw = (res.stdout or res.stderr or "").strip()
        first_line = raw.splitlines()[0] if raw else "available"
        return {"available": True, "path": path, "version": first_line, "raw": raw}
    except Exception as exc:
        return {"available": True, "path": path, "version": "available", "raw": str(exc)}


def _check_flutter_sdk() -> dict[str, Any]:
    """Check Flutter SDK availability, version, channel, and Dart version."""
    path = shutil.which("flutter")
    if not path:
        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "fail",
            "message": "Flutter CLI not found in PATH",
            "hint": "Install Flutter SDK and ensure 'flutter/bin' is added to your PATH.",
        }

    try:
        res = subprocess.run(["flutter", "--version"], capture_output=True, text=True, timeout=3.5)
        raw = (res.stdout or res.stderr or "").strip()
        lines = raw.splitlines()
        first_line = lines[0] if lines else "Flutter available"

        version_match = re.search(r"Flutter\s+([0-9]+\.[0-9]+\.[0-9]+[^\s]*)", raw)
        channel_match = re.search(r"channel\s+([a-zA-Z0-9_-]+)", raw)
        dart_match = re.search(r"Dart\s+([0-9]+\.[0-9]+\.[0-9]+[^\s]*)", raw)

        flutter_ver = version_match.group(1) if version_match else ""
        channel = channel_match.group(1) if channel_match else ""
        dart_ver = dart_match.group(1) if dart_match else ""

        detail_parts = []
        if flutter_ver:
            detail_parts.append(f"v{flutter_ver}")
        if channel:
            detail_parts.append(f"channel {channel}")
        if dart_ver:
            detail_parts.append(f"Dart {dart_ver}")

        detail_str = " • ".join(detail_parts) if detail_parts else first_line

        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "pass",
            "message": f"Flutter {detail_str}",
            "path": path,
            "version": flutter_ver or first_line,
            "dartVersion": dart_ver,
            "channel": channel,
        }
    except Exception as exc:
        return {
            "id": "flutter_sdk",
            "category": "toolchain",
            "name": "Flutter SDK",
            "status": "pass",
            "message": f"Flutter available at {path} (version check timed out)",
            "path": path,
            "version": "available",
            "raw": str(exc),
        }


def _check_toolchain(ws_root: Path) -> list[dict[str, Any]]:
    """Check base CLI utilities: Flutter, Git, Bash, Melos."""
    checks = []

    # 1. Flutter SDK
    checks.append(_check_flutter_sdk())

    # 2. Git
    git_info = _check_tool("git")
    if git_info["available"]:
        checks.append({
            "id": "git_cli",
            "category": "toolchain",
            "name": "Git CLI",
            "status": "pass",
            "message": git_info["version"] or "Git available",
            "path": git_info["path"],
        })
    else:
        checks.append({
            "id": "git_cli",
            "category": "toolchain",
            "name": "Git CLI",
            "status": "fail",
            "message": "Git executable not found in PATH",
            "hint": "Install Git using your system package manager (e.g. apt install git or brew install git).",
        })

    # 3. Bash
    bash_path = shutil.which("bash")
    if bash_path:
        checks.append({
            "id": "bash_shell",
            "category": "toolchain",
            "name": "Bash Shell",
            "status": "pass",
            "message": f"Bash available ({bash_path})",
            "path": bash_path,
        })
    else:
        checks.append({
            "id": "bash_shell",
            "category": "toolchain",
            "name": "Bash Shell",
            "status": "fail",
            "message": "Bash shell not found in PATH",
            "hint": "Bash is required to execute deployment scripts.",
        })

    # 4. Melos (if monorepo)
    melos_yaml = ws_root / "melos.yaml"
    melos_info = _check_tool("melos")
    if melos_yaml.exists():
        if melos_info["available"]:
            checks.append({
                "id": "melos_cli",
                "category": "toolchain",
                "name": "Melos Monorepo CLI",
                "status": "pass",
                "message": f"Melos installed ({melos_info['version']})",
                "path": melos_info["path"],
            })
        else:
            checks.append({
                "id": "melos_cli",
                "category": "toolchain",
                "name": "Melos Monorepo CLI",
                "status": "warn",
                "message": "Workspace has melos.yaml, but 'melos' binary was not found in PATH",
                "hint": "Run: dart pub global activate melos and add ~/.pub-cache/bin to your PATH.",
            })

    return checks


def _check_app_project(app_id: str, app_dir: Path) -> list[dict[str, Any]]:
    """Check app pubspec.yaml, version, and dependency resolution."""
    checks = []

    if not app_dir.is_dir():
        checks.append({
            "id": "app_folder",
            "category": "project",
            "name": "App Directory",
            "status": "fail",
            "message": f"App folder not found at '{app_dir}'",
            "hint": "Verify app folder exists in workspace or update app path in Setup.",
        })
        return checks

    checks.append({
        "id": "app_folder",
        "category": "project",
        "name": "App Directory",
        "status": "pass",
        "message": f"Found at {app_dir.name}/ ({app_dir})",
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


def _check_git_status(target_dir: Path) -> list[dict[str, Any]]:
    """Check Git working tree cleanliness, branch name, and upstream sync."""
    checks = []
    # Check if target_dir or parent is a git work tree
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if res.returncode != 0 or res.stdout.strip() != "true":
            checks.append({
                "id": "git_repo",
                "category": "git",
                "name": "Git Repository",
                "status": "info",
                "message": "Not a Git repository (or git not initialized).",
            })
            return checks
    except Exception:
        checks.append({
            "id": "git_repo",
            "category": "git",
            "name": "Git Repository",
            "status": "info",
            "message": "Git status check skipped.",
        })
        return checks

    # 1. Branch name
    try:
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        branch = branch_res.stdout.strip()
        if branch == "HEAD":
            checks.append({
                "id": "git_branch",
                "category": "git",
                "name": "Git Branch",
                "status": "warn",
                "message": "Detached HEAD state. Releases should be tagged from a named branch (e.g. main/develop).",
                "hint": "Switch to a valid branch: git checkout <branch-name>",
            })
        elif branch:
            checks.append({
                "id": "git_branch",
                "category": "git",
                "name": "Git Branch",
                "status": "pass",
                "message": f"Active branch: {branch}",
                "branch": branch,
            })
    except Exception as exc:
        checks.append({
            "id": "git_branch",
            "category": "git",
            "name": "Git Branch",
            "status": "info",
            "message": f"Could not determine branch: {exc}",
        })

    # 2. Dirty tree check
    try:
        stat_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        dirty_lines = [item for item in (stat_res.stdout or "").splitlines() if item.strip()]
        if dirty_lines:
            untracked = sum(1 for item in dirty_lines if item.startswith("??"))
            modified = len(dirty_lines) - untracked
            checks.append({
                "id": "git_dirty",
                "category": "git",
                "name": "Working Tree Status",
                "status": "warn",
                "message": f"{len(dirty_lines)} uncommitted file(s) ({modified} modified, {untracked} untracked).",
                "hint": "Recommended to commit or stash uncommitted changes before production releases: git status",
            })
        else:
            checks.append({
                "id": "git_dirty",
                "category": "git",
                "name": "Working Tree Status",
                "status": "pass",
                "message": "Clean working tree (no uncommitted or untracked changes)",
            })
    except Exception as exc:
        checks.append({
            "id": "git_dirty",
            "category": "git",
            "name": "Working Tree Status",
            "status": "info",
            "message": f"Could not check working tree: {exc}",
        })

    # 3. Upstream sync check
    try:
        sync_res = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if sync_res.returncode == 0:
            counts = sync_res.stdout.strip().split()
            if len(counts) == 2:
                ahead, behind = int(counts[0]), int(counts[1])
                if ahead > 0 and behind > 0:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "warn",
                        "message": f"Branch has diverged from remote ({ahead} ahead, {behind} behind).",
                        "hint": "Pull and rebase or merge remote changes: git pull --rebase",
                    })
                elif ahead > 0:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "warn",
                        "message": f"Local branch has {ahead} unpushed commit(s) ahead of remote.",
                        "hint": "Push commits before creating release tags: git push",
                    })
                elif behind > 0:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "warn",
                        "message": f"Local branch is {behind} commit(s) behind remote.",
                        "hint": "Pull remote updates before building: git pull",
                    })
                else:
                    checks.append({
                        "id": "git_sync",
                        "category": "git",
                        "name": "Remote Sync",
                        "status": "pass",
                        "message": "Branch is in sync with upstream remote",
                    })
    except Exception:
        pass  # Upstream might not be configured, skip silently

    return checks


def _check_android_env(app_dir: Path, app_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Check JDK, JAVA_HOME, Android SDK, and gradlew executable."""
    android_dir = app_dir / "android"
    if not android_dir.is_dir():
        return []

    checks = []

    # 1. Java / JDK
    java_path = shutil.which("java")

    if not java_path:
        checks.append({
            "id": "android_jdk",
            "category": "android",
            "name": "Java Development Kit (JDK)",
            "status": "fail",
            "message": "Java runtime ('java') not found in PATH. Android builds will fail.",
            "hint": "Install OpenJDK 17 or 21 and configure JAVA_HOME.",
        })
    else:
        # Check java version
        try:
            res = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=2.5)
            raw = (res.stdout or res.stderr or "").strip()
            # Common patterns: "openjdk version 17.0.2" or "java version 1.8.0_292"
            ver_match = re.search(r'version\s+"([0-9]+)(\.[0-9]+)?', raw)
            major_ver = 0
            if ver_match:
                part1 = int(ver_match.group(1))
                if part1 == 1 and ver_match.group(2):
                    major_ver = int(ver_match.group(2).lstrip("."))
                else:
                    major_ver = part1

            raw_first = raw.splitlines()[0] if raw else "Java available"

            if major_ver > 0 and major_ver < 17:
                checks.append({
                    "id": "android_jdk",
                    "category": "android",
                    "name": "Java Development Kit (JDK)",
                    "status": "warn",
                    "message": f"{raw_first} (JDK {major_ver} detected). Modern Gradle 8+ recommends JDK 17+.",
                    "hint": "Consider upgrading to OpenJDK 17 or JDK 21 for modern Flutter Gradle compatibility.",
                    "path": java_path,
                })
            else:
                checks.append({
                    "id": "android_jdk",
                    "category": "android",
                    "name": "Java Development Kit (JDK)",
                    "status": "pass",
                    "message": f"{raw_first} ({java_path})",
                    "path": java_path,
                })
        except Exception as exc:
            checks.append({
                "id": "android_jdk",
                "category": "android",
                "name": "Java Development Kit (JDK)",
                "status": "pass",
                "message": f"Java found at {java_path}",
                "path": java_path,
                "raw": str(exc),
            })

    # 2. JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        jh_path = Path(java_home)
        if jh_path.is_dir():
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
        # Check standard default locations
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

    # 1. Platform constraint
    if not is_macos:
        checks.append({
            "id": "ios_host",
            "category": "ios",
            "name": "iOS Build Host",
            "status": "info",
            "message": f"Host OS is {platform.system()}. iOS archive/IPA generation requires macOS (or CI/CD runner). Android builds are unaffected.",
        })
    else:
        # Xcode
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

        # CocoaPods
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

    # 2. Bundle ID
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

    # 3. Cert Expiry Check (delegates to jobs.check_ios_expiry)
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


def diagnose_app(app_id: Optional[str] = None, flavor: str = "prod", ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Run full diagnostic check for an app (or workspace if app_id is None)."""
    started_at = time.time()
    ws_root = ws_root or get_workspace_root()

    all_checks: list[dict[str, Any]] = []

    # 1. Base Toolchain
    all_checks.extend(_check_toolchain(ws_root))

    app_dir = ws_root
    app_cfg = {}
    if app_id:
        try:
            app_dir = _resolve_app_dir(app_id)
            deploy_cfg = load_deploy_config()
            app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
        except Exception:
            app_dir = ws_root / app_id

        # 2. App Project & Dependencies
        all_checks.extend(_check_app_project(app_id, app_dir))

        # 3. Android Environment
        all_checks.extend(_check_android_env(app_dir, app_cfg))

        # 4. iOS Environment
        all_checks.extend(_check_ios_env(app_id, app_dir, app_cfg, flavor=flavor))

        # 5. Credentials & Secrets
        all_checks.extend(_check_credentials(app_id, app_dir))

        # 6. Certificate & Keystore Sentinel (Expiry & Firebase Mismatches)
        try:
            import sentinel
            sentinel_res = sentinel.check_app_sentinel(app_id, flavor=flavor, ws_root=ws_root)
            sentinel_alerts = sentinel_res.get("alerts", [])
            if sentinel_alerts:
                for a in sentinel_alerts:
                    all_checks.append({
                        "id": a["id"],
                        "category": a.get("category", "credentials"),
                        "name": f"Sentinel: {a['title']}",
                        "status": "fail" if a["severity"] == "critical" else "warn",
                        "message": a["message"],
                        "hint": a.get("hint", ""),
                    })
            else:
                all_checks.append({
                    "id": "sentinel_status_ok",
                    "category": "credentials",
                    "name": "Certificate & Keystore Sentinel",
                    "status": "pass",
                    "message": "Apple certificates, Android keystore, and Firebase project IDs are healthy.",
                })
        except Exception:
            logging.exception("Failed to run sentinel checks in doctor")

    # 7. Git Status
    all_checks.extend(_check_git_status(app_dir))

    # Calculate Score & Overall Status
    pass_count = sum(1 for c in all_checks if c.get("status") == "pass")
    warn_count = sum(1 for c in all_checks if c.get("status") == "warn")
    fail_count = sum(1 for c in all_checks if c.get("status") == "fail")
    info_count = sum(1 for c in all_checks if c.get("status") == "info")
    total_count = len(all_checks)

    if fail_count > 0:
        overall_status = "fail"
        summary_headline = f"{fail_count} critical issue(s) detected that will break builds."
    elif warn_count > 0:
        overall_status = "warn"
        summary_headline = f"Ready to build with {warn_count} warning(s) to review."
    else:
        overall_status = "pass"
        summary_headline = "All pre-flight diagnostic checks passed successfully!"

    duration_ms = int((time.time() - started_at) * 1000)

    # Generate Markdown Report
    report_lines = [
        "# App Doctor Diagnostic Report",
        f"**App**: {app_id or 'Workspace'} | **Flavor**: {flavor} | **Overall Status**: {overall_status.upper()}",
        f"**Checked At**: {time.strftime('%Y-%m-%d %H:%M:%S')} ({duration_ms}ms)",
        "",
        f"### Summary: {summary_headline}",
        f"- Passed: **{pass_count}**",
        f"- Warnings: **{warn_count}**",
        f"- Failures: **{fail_count}**",
        "",
        "| Category | Check | Status | Details |",
        "| :--- | :--- | :---: | :--- |",
    ]

    status_icons = {"pass": "PASS (OK)", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    for c in all_checks:
        icon = status_icons.get(c.get("status"), c.get("status", "").upper())
        cat = c.get("category", "").capitalize()
        name = c.get("name", "")
        msg = c.get("message", "")
        hint = f" *[Hint: {c['hint']}]*" if c.get("hint") else ""
        report_lines.append(f"| {cat} | {name} | {icon} | {msg}{hint} |")

    markdown_report = "\n".join(report_lines)

    return {
        "success": True,
        "app": app_id,
        "flavor": flavor,
        "overallStatus": overall_status,
        "summary": summary_headline,
        "passCount": pass_count,
        "warnCount": warn_count,
        "failCount": fail_count,
        "infoCount": info_count,
        "totalCount": total_count,
        "durationMs": duration_ms,
        "checks": all_checks,
        "reportMarkdown": markdown_report,
    }
