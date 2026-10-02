"""Template and event metadata compilation engine for deployment notifications."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
from typing import Any, Optional

from config import (
    _detect_app_in_dir,
    _resolve_app_dir,
    get_apps_config_file,
    get_workspace_root,
    load_deploy_config,
)


def get_git_commit_summary(ws_root: Optional[Path] = None) -> dict[str, str]:
    """Retrieve last commit's hash, subject, and author."""
    target_dir = ws_root or get_workspace_root()
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h%x09%s%x09%an"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split("\t")
            return {
                "hash": parts[0].strip() if len(parts) > 0 else "",
                "subject": parts[1].strip() if len(parts) > 1 else "",
                "author": parts[2].strip() if len(parts) > 2 else "",
            }
    except Exception:
        pass
    return {"hash": "", "subject": "", "author": ""}


def format_duration(seconds: Optional[int | float]) -> str:
    """Format duration in seconds to human-readable string (e.g. 1m 24s or 45s)."""
    if seconds is None or seconds < 0:
        return "unknown"
    sec = int(seconds)
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    return f"{m}m {s}s" if s else f"{m}m"


def resolve_app_details(app_id: str, ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Resolve app display name, version, stack, and platform from workspace files."""
    name = app_id
    version = "1.0.0 (1)"
    stack = "flutter"

    apps_file = get_apps_config_file()
    if apps_file.exists():
        try:
            saved_apps = json.loads(apps_file.read_text(encoding="utf-8"))
            if isinstance(saved_apps, list):
                for a in saved_apps:
                    if isinstance(a, dict) and a.get("id") == app_id:
                        if a.get("name"):
                            name = a["name"]
                        if a.get("version"):
                            version = a["version"]
                        if a.get("stack"):
                            stack = a["stack"]
                        return {"name": name, "version": version, "stack": stack}
        except Exception:
            logging.exception("Failed to read apps_config.json for app details")

    try:
        app_dir = _resolve_app_dir(app_id)
        detected = _detect_app_in_dir(app_dir)
        if detected:
            name = detected.get("name") or name
            version = detected.get("version") or version
            stack = detected.get("stack") or stack
    except Exception:
        pass

    return {"name": name, "version": version, "stack": stack}


def detect_platform_and_track(
    command: str = "",
    template_id: str = "",
    app_details: Optional[dict[str, Any]] = None,
    app_cfg: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    """Derive platform label and store distribution track from command / config."""
    cmd_lower = (command or "").lower()
    tmpl_lower = (template_id or "").lower()
    app_details = app_details or {}
    app_cfg = app_cfg or {}

    # Platform detection
    if "apk" in cmd_lower or "apk" in tmpl_lower:
        platform = "Android (APK)"
    elif "aab" in cmd_lower or "appbundle" in cmd_lower or "aab" in tmpl_lower:
        platform = "Android (AAB)"
    elif "ipa" in cmd_lower or "ios" in cmd_lower or "ipa" in tmpl_lower:
        platform = "iOS (IPA)"
    elif "web" in cmd_lower or "web" in tmpl_lower:
        platform = "Web"
    elif "macos" in cmd_lower or "macos" in tmpl_lower:
        platform = "macOS"
    elif "windows" in cmd_lower or "windows" in tmpl_lower:
        platform = "Windows"
    elif "linux" in cmd_lower or "linux" in tmpl_lower:
        platform = "Linux"
    else:
        stack = app_details.get("stack", "").lower()
        if stack == "react-native":
            platform = "React Native"
        elif stack == "flutter":
            platform = "Flutter (Mobile)"
        else:
            platform = "Application"

    # Track / target detection
    configured_track = app_cfg.get("play_console_track") or app_cfg.get("track") or ""
    if configured_track:
        track = configured_track
    elif "bundletool" in cmd_lower or "deploy_aab" in tmpl_lower:
        track = "Google Play (Internal Testing)"
    elif "ipatool" in cmd_lower or "deploy_ipa" in tmpl_lower or "upload_ipa" in tmpl_lower:
        track = "Apple App Store / TestFlight"
    elif "release_push" in tmpl_lower or "release" in tmpl_lower:
        track = "Git Release / Remote Tag"
    else:
        track = ""

    return platform, track


def render_template(template_str: str, event_data: dict[str, Any]) -> Any:
    """Evaluate custom template string with event variables. If valid JSON, return parsed object, else text dict."""
    if not template_str or not template_str.strip():
        return {
            "event": "deployment_finished",
            "timestamp": event_data.get("timestamp") or "",
            **event_data,
        }

    app_name = str(event_data.get("appName") or event_data.get("app_name") or event_data.get("app") or "")
    app_id = str(event_data.get("app") or event_data.get("app_id") or "")
    flavor = str(event_data.get("flavor") or "")
    platform = str(event_data.get("platform") or "")
    version = str(event_data.get("version") or "")
    status = str(event_data.get("status") or "")
    duration = str(event_data.get("durationFormatted") or event_data.get("duration") or "")
    duration_sec = str(event_data.get("durationSeconds") or "")
    download_url = str(event_data.get("downloadUrl") or event_data.get("download_url") or "")
    track = str(event_data.get("track") or "")
    commit = event_data.get("commit") or {}
    commit_hash = str(commit.get("hash") or "")
    commit_subject = str(commit.get("subject") or "")
    commit_author = str(commit.get("author") or "")
    build_size = str(event_data.get("buildSizeSummary") or "")

    rendered = (
        template_str
        .replace("{appName}", json.dumps(app_name)[1:-1])
        .replace("{appId}", json.dumps(app_id)[1:-1])
        .replace("{flavor}", json.dumps(flavor)[1:-1])
        .replace("{platform}", json.dumps(platform)[1:-1])
        .replace("{version}", json.dumps(version)[1:-1])
        .replace("{status}", json.dumps(status)[1:-1])
        .replace("{duration}", json.dumps(duration)[1:-1])
        .replace("{durationSeconds}", duration_sec)
        .replace("{downloadUrl}", json.dumps(download_url)[1:-1])
        .replace("{track}", json.dumps(track)[1:-1])
        .replace("{commitHash}", json.dumps(commit_hash)[1:-1])
        .replace("{commitSubject}", json.dumps(commit_subject)[1:-1])
        .replace("{commitAuthor}", json.dumps(commit_author)[1:-1])
        .replace("{buildSize}", json.dumps(build_size)[1:-1])
    )

    try:
        return json.loads(rendered)
    except Exception:
        return {"text": rendered, "content": rendered, "raw": rendered}


def compile_event_data(
    app: str,
    flavor: str,
    status: str,
    duration_sec: Optional[int],
    command: str = "",
    template_id: str = "",
    artifact: Optional[dict[str, Any]] = None,
    ws_root: Optional[Path] = None,
    error_excerpt: str = "",
    build_size: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble all parameters required for rich card rendering."""
    ws = ws_root or get_workspace_root()
    app_details = resolve_app_details(app, ws)
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app, {})

    platform, track = detect_platform_and_track(
        command=command,
        template_id=template_id,
        app_details=app_details,
        app_cfg=app_cfg,
    )

    commit = get_git_commit_summary(ws)

    download_url = ""
    if artifact and artifact.get("download_url"):
        download_url = artifact["download_url"]
    elif artifact and artifact.get("path"):
        try:
            import artifacts
            dl_info = artifacts.get_apk_download_info(app_id=app, flavor=flavor)
            if dl_info.get("hasApk") and dl_info.get("downloadUrl"):
                download_url = dl_info["downloadUrl"]
        except Exception:
            pass

    build_size_summary = (build_size or {}).get("summary", "")

    return {
        "app": app,
        "appName": app_details.get("name") or app,
        "flavor": flavor or "default",
        "platform": platform,
        "version": app_details.get("version") or "1.0.0",
        "status": status,
        "durationSeconds": duration_sec or 0,
        "durationFormatted": format_duration(duration_sec),
        "commit": commit,
        "downloadUrl": download_url,
        "track": track,
        "command": command,
        "templateId": template_id,
        "errorExcerpt": error_excerpt,
        "buildSizeSummary": build_size_summary,
    }
