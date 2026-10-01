"""Outgoing Webhooks (Slack / Discord / Teams) for Dev Deployment Console.

Automates team alerts on deployment completion or failure.
Dispatches formatted cards containing:
- App name, flavor, platform, version & build number
- Duration (formatted: Xm Ys)
- Git commit message summary (hash, subject, author)
- Direct download link (for local APKs) / Play Console / TestFlight track

Python standard library only (urllib.request, json, threading).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Optional
import urllib.error
import urllib.request

from config import (
    _detect_app_in_dir,
    _resolve_app_dir,
    get_apps_config_file,
    get_workspace_root,
    load_deploy_config,
)


def detect_webhook_provider(url: str, override: str = "auto") -> str:
    """Detect destination service from URL hostname or return user override."""
    override_clean = (override or "auto").strip().lower()
    if override_clean in ("slack", "discord", "teams", "generic"):
        return override_clean

    url_lower = (url or "").lower()
    if "hooks.slack.com" in url_lower or "slack.com/services" in url_lower:
        return "slack"
    if "discord.com/api/webhooks" in url_lower or "discordapp.com/api/webhooks" in url_lower:
        return "discord"
    if (
        "webhook.office.com" in url_lower
        or "office.com/webhook" in url_lower
        or "logic.azure.com" in url_lower
    ):
        return "teams"
    return "generic"


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


# ─────────────────────────────────────────────────────────────────────────────
# Payload Builders for Slack, Discord, Microsoft Teams, and Generic JSON
# ─────────────────────────────────────────────────────────────────────────────

def build_slack_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format rich Slack message using Block Kit."""
    status = event.get("status", "success").lower()
    is_success = status == "success"
    status_icon = "✅" if is_success else "❌"
    status_label = "SUCCEEDED" if is_success else ("STOPPED" if status == "stopped" else "FAILED")

    app_name = event.get("appName") or event.get("app") or "App"
    flavor = event.get("flavor") or "default"
    platform = event.get("platform") or "Mobile"
    version = event.get("version") or "1.0.0"
    duration = event.get("durationFormatted") or "0s"
    commit = event.get("commit") or {}
    download_url = event.get("downloadUrl") or ""
    track = event.get("track") or ""

    title = f"{status_icon} Deployment {status_label.title()}: {app_name}"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title[:150],
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*App:*\n{app_name}"},
                {"type": "mrkdwn", "text": f"*Flavor:*\n{flavor}"},
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform}"},
                {"type": "mrkdwn", "text": f"*Version:*\n{version}"},
                {"type": "mrkdwn", "text": f"*Duration:*\n{duration}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status_label}"},
            ],
        },
    ]

    extra_parts = []
    if event.get("buildSizeSummary"):
        extra_parts.append(f"*Build Size:* {event['buildSizeSummary']}")
    if track:
        extra_parts.append(f"*Track / Target:* {track}")
    if commit.get("hash") or commit.get("subject"):
        c_hash = f"`{commit.get('hash')}`" if commit.get("hash") else ""
        c_sub = commit.get("subject", "")
        c_auth = f"({commit.get('author')})" if commit.get("author") else ""
        extra_parts.append(f"*Commit:* {c_hash} {c_sub} {c_auth}".strip())
    if download_url:
        extra_parts.append(f"*Direct Download:* <{download_url}|Click to Install APK>")

    if extra_parts:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(extra_parts),
            },
        })

    if download_url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📱 Download APK",
                        "emoji": True,
                    },
                    "url": download_url,
                    "style": "primary",
                }
            ],
        })

    fallback_text = f"{title} | {flavor} | {duration}"
    return {"text": fallback_text, "blocks": blocks}


def build_discord_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format Discord message using Embeds."""
    status = event.get("status", "success").lower()
    is_success = status == "success"
    color = 0x10B981 if is_success else (0xF59E0B if status == "stopped" else 0xEF4444)
    status_icon = "✅" if is_success else "❌"
    status_label = "SUCCEEDED" if is_success else ("STOPPED" if status == "stopped" else "FAILED")

    app_name = event.get("appName") or event.get("app") or "App"
    flavor = event.get("flavor") or "default"
    platform = event.get("platform") or "Mobile"
    version = event.get("version") or "1.0.0"
    duration = event.get("durationFormatted") or "0s"
    commit = event.get("commit") or {}
    download_url = event.get("downloadUrl") or ""
    track = event.get("track") or ""

    fields = [
        {"name": "App", "value": app_name, "inline": True},
        {"name": "Flavor", "value": flavor, "inline": True},
        {"name": "Platform", "value": platform, "inline": True},
        {"name": "Version", "value": version, "inline": True},
        {"name": "Duration", "value": duration, "inline": True},
        {"name": "Status", "value": status_label, "inline": True},
    ]

    if event.get("buildSizeSummary"):
        fields.append({"name": "Build Size", "value": event["buildSizeSummary"], "inline": False})

    if track:
        fields.append({"name": "Track / Target", "value": track, "inline": False})

    if commit.get("hash") or commit.get("subject"):
        c_hash = f"`{commit.get('hash')}` " if commit.get("hash") else ""
        c_sub = commit.get("subject", "")
        c_auth = f" ({commit.get('author')})" if commit.get("author") else ""
        fields.append({"name": "Commit", "value": f"{c_hash}{c_sub}{c_auth}".strip(), "inline": False})

    if download_url:
        fields.append({
            "name": "Local APK Direct Download",
            "value": f"[📱 Download APK ({flavor})]({download_url})",
            "inline": False,
        })

    embed = {
        "title": f"{status_icon} Deployment {status_label.title()}: {app_name}",
        "color": color,
        "description": f"Build & deployment finished in **{duration}**",
        "fields": fields,
        "footer": {"text": "Dev Deployment Console"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if download_url:
        embed["url"] = download_url

    return {"embeds": [embed]}


def build_teams_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format Microsoft Teams webhook card using Office 365 Connector MessageCard format."""
    status = event.get("status", "success").lower()
    is_success = status == "success"
    theme_color = "10B981" if is_success else ("F59E0B" if status == "stopped" else "EF4444")
    status_icon = "✅" if is_success else "❌"
    status_label = "SUCCEEDED" if is_success else ("STOPPED" if status == "stopped" else "FAILED")

    app_name = event.get("appName") or event.get("app") or "App"
    flavor = event.get("flavor") or "default"
    platform = event.get("platform") or "Mobile"
    version = event.get("version") or "1.0.0"
    duration = event.get("durationFormatted") or "0s"
    commit = event.get("commit") or {}
    download_url = event.get("downloadUrl") or ""
    track = event.get("track") or ""

    facts = [
        {"name": "App", "value": app_name},
        {"name": "Flavor", "value": flavor},
        {"name": "Platform", "value": platform},
        {"name": "Version", "value": version},
        {"name": "Duration", "value": duration},
        {"name": "Status", "value": status_label},
    ]

    if event.get("buildSizeSummary"):
        facts.append({"name": "Build Size", "value": event["buildSizeSummary"]})

    if track:
        facts.append({"name": "Track", "value": track})

    if commit.get("hash") or commit.get("subject"):
        c_hash = f"`{commit.get('hash')}` " if commit.get("hash") else ""
        c_sub = commit.get("subject", "")
        c_auth = f" ({commit.get('author')})" if commit.get("author") else ""
        facts.append({"name": "Commit", "value": f"{c_hash}{c_sub}{c_auth}".strip()})

    card: dict[str, Any] = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": theme_color,
        "summary": f"Deployment {status_label}: {app_name}",
        "title": f"{status_icon} Deployment {status_label.title()}: {app_name}",
        "sections": [
            {
                "activityTitle": f"Deployment Completed ({duration})",
                "activitySubtitle": "Dev Deployment Console",
                "facts": facts,
                "markdown": True,
            }
        ],
    }

    if download_url:
        card["potentialAction"] = [
            {
                "@type": "OpenURI",
                "name": "📱 Download APK",
                "targets": [{"os": "default", "uri": download_url}],
            }
        ]

    return card


def build_generic_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format clean generic JSON payload for custom webhooks."""
    return {
        "event": "deployment_finished",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **event,
    }


def build_webhook_payload(provider: str, event_data: dict[str, Any]) -> dict[str, Any]:
    """Select and construct appropriate payload for the target webhook provider."""
    provider_clean = (provider or "generic").strip().lower()
    if provider_clean == "slack":
        return build_slack_payload(event_data)
    if provider_clean == "discord":
        return build_discord_payload(event_data)
    if provider_clean == "teams":
        return build_teams_payload(event_data)
    return build_generic_payload(event_data)


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def send_outgoing_webhook(
    url: str,
    payload: dict[str, Any],
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Send formatted JSON payload to outgoing webhook URL via HTTP POST."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return {"success": False, "error": "Invalid webhook URL: must start with http:// or https://"}

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "DevDeployment-Webhook/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            body = response.read().decode("utf-8", errors="replace")
            # 2xx is considered success (Discord returns 204 No Content, Slack returns 200 "ok")
            is_ok = 200 <= status_code < 300
            return {
                "success": is_ok,
                "statusCode": status_code,
                "response": body[:200],
            }
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        return {
            "success": False,
            "statusCode": exc.code,
            "error": f"HTTP {exc.code}: {err_body[:200]}",
        }
    except Exception as exc:
        return {
            "success": False,
            "statusCode": 0,
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Resolution and Background Notification Dispatchers
# ─────────────────────────────────────────────────────────────────────────────

def get_webhook_config_for_app(app_id: str) -> dict[str, Any]:
    """Look up notification settings for an app with fallback to workspace-level webhook."""
    deploy_cfg = load_deploy_config()
    apps = deploy_cfg.get("apps", {})
    app_cfg = apps.get(app_id, {}) if isinstance(apps, dict) else {}

    # 1. Check app-specific webhook settings
    app_url = (app_cfg.get("webhook_url") or "").strip()
    if app_url:
        return {
            "url": app_url,
            "enabled": bool(app_cfg.get("webhook_enabled", True)),
            "provider": app_cfg.get("webhook_provider", "auto"),
            "notify_on_success": bool(app_cfg.get("notify_on_success", True)),
            "notify_on_failure": bool(app_cfg.get("notify_on_failure", True)),
            "play_console_track": app_cfg.get("play_console_track", ""),
            "scope": "app",
        }

    # 2. Check workspace-level fallback webhook
    ws_url = (deploy_cfg.get("workspace_webhook_url") or "").strip()
    if ws_url:
        return {
            "url": ws_url,
            "enabled": bool(deploy_cfg.get("workspace_webhook_enabled", True)),
            "provider": deploy_cfg.get("workspace_webhook_provider", "auto"),
            "notify_on_success": bool(deploy_cfg.get("workspace_notify_on_success", True)),
            "notify_on_failure": bool(deploy_cfg.get("workspace_notify_on_failure", True)),
            "play_console_track": deploy_cfg.get("workspace_play_console_track", ""),
            "scope": "workspace",
        }

    return {"enabled": False, "url": "", "scope": "none"}


def _compile_event_data(
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


def notify_job_finished(job: dict[str, Any], ws_root: Optional[Path] = None) -> None:
    """Evaluate and dispatch webhook notification when a standalone deployment job finishes."""
    if not job or job.get("is_pipeline_step"):
        # Suppress standalone notifications for individual pipeline steps
        return

    status = (job.get("status") or "error").lower()
    if status not in ("success", "error", "stopped"):
        return

    app = job.get("app") or ""
    cfg = get_webhook_config_for_app(app)
    if not cfg.get("enabled") or not cfg.get("url"):
        return

    is_success = status == "success"
    if is_success and not cfg.get("notify_on_success", True):
        return
    if not is_success and not cfg.get("notify_on_failure", True):
        return

    started = job.get("started_at")
    finished = job.get("finished_at") or time.time()
    duration_sec = int(finished - started) if started else None

    err_raw = (job.get("error") or "").strip()
    error_excerpt = "\n".join(err_raw.splitlines()[-5:]) if err_raw else ""

    event_data = _compile_event_data(
        app=app,
        flavor=job.get("flavor") or job.get("env") or "",
        status=status,
        duration_sec=duration_sec,
        command=job.get("command") or "",
        template_id=job.get("template_id") or "",
        artifact=job.get("artifact"),
        ws_root=ws_root,
        error_excerpt=error_excerpt,
        build_size=job.get("buildSize"),
    )

    provider = detect_webhook_provider(cfg["url"], cfg.get("provider", "auto"))
    payload = build_webhook_payload(provider, event_data)

    def _async_send():
        try:
            res = send_outgoing_webhook(cfg["url"], payload)
            if not res.get("success"):
                logging.warning("Outgoing webhook to %s failed: %s", cfg["url"], res.get("error"))
        except Exception:
            logging.exception("Exception during outgoing webhook dispatch")

    threading.Thread(target=_async_send, name="WebhookNotifyThread", daemon=True).start()


def notify_pipeline_finished(run: dict[str, Any], ws_root: Optional[Path] = None) -> None:
    """Evaluate and dispatch webhook notification when an automated pipeline finishes."""
    if not run:
        return

    status = (run.get("status") or "error").lower()
    if status not in ("success", "error", "stopped"):
        return

    app = run.get("app") or ""
    cfg = get_webhook_config_for_app(app)
    if not cfg.get("enabled") or not cfg.get("url"):
        return

    is_success = status == "success"
    if is_success and not cfg.get("notify_on_success", True):
        return
    if not is_success and not cfg.get("notify_on_failure", True):
        return

    duration_sec = run.get("durationSeconds")
    if duration_sec is None and run.get("startedAt") and run.get("finishedAt"):
        duration_sec = int(run["finishedAt"] - run["startedAt"])

    event_data = _compile_event_data(
        app=app,
        flavor=run.get("flavor") or "",
        status=status,
        duration_sec=duration_sec,
        command=f"Pipeline: {run.get('name')}",
        template_id="pipeline",
        artifact=run.get("artifact"),
        ws_root=ws_root,
    )
    event_data["platform"] = f"Pipeline ({len(run.get('steps', []))} steps)"

    provider = detect_webhook_provider(cfg["url"], cfg.get("provider", "auto"))
    payload = build_webhook_payload(provider, event_data)

    def _async_send():
        try:
            res = send_outgoing_webhook(cfg["url"], payload)
            if not res.get("success"):
                logging.warning("Pipeline webhook to %s failed: %s", cfg["url"], res.get("error"))
        except Exception:
            logging.exception("Exception during pipeline webhook dispatch")

    threading.Thread(target=_async_send, name="PipelineWebhookNotifyThread", daemon=True).start()


def test_webhook(
    url: str,
    provider: str = "auto",
    app_id: Optional[str] = None,
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Test webhook endpoint by sending an immediate test card to the given URL."""
    clean_url = (url or "").strip()
    if not clean_url:
        return {"success": False, "error": "Webhook URL cannot be empty"}

    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return {"success": False, "error": "Invalid webhook URL: must start with http:// or https://"}

    ws = ws_root or get_workspace_root()
    detected_provider = detect_webhook_provider(clean_url, provider)
    app = app_id or "demo_app"
    app_details = resolve_app_details(app, ws)
    commit = get_git_commit_summary(ws)

    sample_event = {
        "app": app,
        "appName": app_details.get("name") or "Sample App",
        "flavor": "prod",
        "platform": "Android (APK)",
        "version": app_details.get("version") or "1.0.0 (1)",
        "status": "success",
        "durationSeconds": 94,
        "durationFormatted": "1m 34s",
        "commit": commit if commit.get("hash") else {
            "hash": "a1b2c3d",
            "subject": "feat: test outgoing webhook notifications",
            "author": "DevDeployment User",
        },
        "downloadUrl": "http://192.168.1.50:18112/api/deployment/download/test",
        "track": "Internal Testing",
    }

    payload = build_webhook_payload(detected_provider, sample_event)
    result = send_outgoing_webhook(clean_url, payload, timeout=6.0)
    result["provider"] = detected_provider
    return result
