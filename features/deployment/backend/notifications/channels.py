"""Outgoing webhook channels (Slack, Discord, Teams, Google Chat, WhatsApp, Generic) and dispatchers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Optional
import urllib.error
import urllib.request

from config import get_workspace_root, load_deploy_config
from .templates import (
    compile_event_data,
    get_git_commit_summary,
    render_template,
    resolve_app_details,
)


def detect_webhook_provider(url: str, override: str = "auto") -> str:
    """Detect destination service from URL hostname or return user override."""
    override_clean = (override or "auto").strip().lower()
    if override_clean in ("slack", "discord", "teams", "google_chat", "whatsapp", "custom", "generic"):
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
    if "chat.googleapis.com" in url_lower:
        return "google_chat"
    if (
        "graph.facebook.com" in url_lower
        or "api.twilio.com" in url_lower
        or "whatsapp" in url_lower
    ):
        return "whatsapp"
    return "generic"


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

    action_buttons = []
    if event.get("itmsUrl"):
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "🍎 Install iOS OTA (10s)", "emoji": True},
            "url": event["itmsUrl"],
            "style": "primary",
        })
    if download_url:
        is_ios = "ios" in platform.lower() or download_url.endswith(".ipa")
        btn_label = "🍎 Download IPA" if is_ios else "📱 Download APK"
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": btn_label, "emoji": True},
            "url": download_url,
            "style": "primary" if not event.get("itmsUrl") else "default",
        })
    if event.get("qrUrl"):
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "📷 Scan QR Code", "emoji": True},
            "url": event["qrUrl"],
        })

    if action_buttons:
        blocks.append({
            "type": "actions",
            "elements": action_buttons,
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


def build_google_chat_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format Google Chat webhook payload with Card v2 and fallback text."""
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

    title = f"{status_icon} [{app_name}] Deploy {status_label} ({flavor})"
    header_subtitle = f"{platform} · v{version} · {duration}"

    widgets = [
        {"decoratedText": {"topLabel": "Application", "text": app_name}},
        {"decoratedText": {"topLabel": "Environment / Flavor", "text": flavor.upper() if flavor else "DEFAULT"}},
        {"decoratedText": {"topLabel": "Platform", "text": platform}},
        {"decoratedText": {"topLabel": "Duration", "text": duration}},
    ]

    if track:
        widgets.append({"decoratedText": {"topLabel": "Store Track", "text": track}})

    if event.get("buildSizeSummary"):
        widgets.append({"decoratedText": {"topLabel": "Build Size", "text": event["buildSizeSummary"]}})

    if commit.get("hash") or commit.get("subject"):
        c_text = f"<b>{commit.get('hash', '')}</b> {commit.get('subject', '')}"
        if commit.get("author"):
            c_text += f" ({commit.get('author')})"
        widgets.append({"decoratedText": {"topLabel": "Git Commit", "text": c_text}})

    if download_url:
        widgets.append({
            "buttonList": {
                "buttons": [
                    {
                        "text": "📱 Download APK",
                        "onClick": {"openLink": {"url": download_url}}
                    }
                ]
            }
        })

    card = {
        "header": {
            "title": title,
            "subtitle": header_subtitle,
        },
        "sections": [
            {
                "widgets": widgets
            }
        ]
    }

    fallback_text = f"{title} | {flavor} | {duration}"
    return {
        "text": fallback_text,
        "cardsV2": [
            {
                "cardId": "deploy-notification-card",
                "card": card
            }
        ]
    }


def build_whatsapp_payload(event: dict[str, Any], custom_phone: str = "") -> dict[str, Any]:
    """Format WhatsApp payload supporting WhatsApp Cloud API, Twilio, and webhook gateways."""
    status = event.get("status", "success").lower()
    is_success = status == "success"
    status_icon = "✅" if is_success else "❌"
    status_label = "SUCCEEDED" if is_success else ("STOPPED" if status == "stopped" else "FAILED")

    app_name = event.get("appName") or event.get("app_name") or event.get("app") or "App"
    flavor = (event.get("flavor") or "default").upper()
    platform = event.get("platform") or "Mobile"
    version = event.get("version") or "1.0.0"
    duration = event.get("durationFormatted") or event.get("duration") or "0s"
    commit = event.get("commit") or {}
    download_url = event.get("downloadUrl") or event.get("download_url") or ""
    track = event.get("track") or ""

    lines = [
        f"{status_icon} *[{app_name}] Deployment {status_label}*",
        f"• *Platform:* {platform}",
        f"• *Flavor:* {flavor}",
        f"• *Version:* v{version}",
        f"• *Duration:* {duration}",
    ]
    if track:
        lines.append(f"• *Track:* {track}")
    if event.get("buildSizeSummary"):
        lines.append(f"• *Build Size:* {event['buildSizeSummary']}")
    if commit.get("hash") or commit.get("subject"):
        c_str = f"`{commit.get('hash', '')}` {commit.get('subject', '')}"
        if commit.get("author"):
            c_str += f" ({commit.get('author')})"
        lines.append(f"• *Commit:* {c_str}")
    if download_url:
        lines.append(f"\n📲 *Download Artifact:*\n{download_url}")

    msg_body = "\n".join(lines)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "type": "text",
        "text": {"preview_url": True, "body": msg_body},
        "message": msg_body,
        "body": msg_body,
        "Body": msg_body,
    }
    if custom_phone:
        payload["to"] = custom_phone
        payload["To"] = f"whatsapp:{custom_phone}" if not custom_phone.startswith("whatsapp:") else custom_phone
    return payload


def build_generic_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Format clean generic JSON payload for custom webhooks."""
    return {
        "event": "deployment_finished",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **event,
    }


def build_webhook_payload(provider: str, event_data: dict[str, Any], custom_template: str = "", phone: str = "") -> Any:
    """Select and construct appropriate payload for the target webhook provider."""
    provider_clean = (provider or "generic").strip().lower()
    if provider_clean == "slack":
        return build_slack_payload(event_data)
    if provider_clean == "discord":
        return build_discord_payload(event_data)
    if provider_clean == "teams":
        return build_teams_payload(event_data)
    if provider_clean == "google_chat":
        return build_google_chat_payload(event_data)
    if provider_clean == "whatsapp":
        return build_whatsapp_payload(event_data, custom_phone=phone)
    if provider_clean == "custom" or custom_template:
        return render_template(custom_template, event_data)
    return build_generic_payload(event_data)


def send_outgoing_webhook(
    url: str,
    payload: Any,
    timeout: float = 8.0,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Send formatted JSON or form payload to outgoing webhook URL via HTTP POST."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return {"success": False, "error": "Invalid webhook URL: must start with http:// or https://"}

    if isinstance(payload, bytes):
        data_bytes = payload
    elif isinstance(payload, str):
        data_bytes = payload.encode("utf-8")
    else:
        data_bytes = json.dumps(payload).encode("utf-8")

    req_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "DevDeployment-Webhook/1.0",
    }
    if headers and isinstance(headers, dict):
        for k, v in headers.items():
            if k and v:
                req_headers[str(k)] = str(v)

    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers=req_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            body = response.read().decode("utf-8", errors="replace")
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


def get_webhook_config_for_app(app_id: str, ws_root: Optional[Path] = None) -> dict[str, Any]:
    """Look up primary notification settings for an app with fallback to workspace-level webhook."""
    channels = get_webhook_channels_for_app(app_id, ws_root=ws_root)
    if channels:
        return channels[0]
    return {"enabled": False, "url": "", "scope": "none"}


def get_webhook_channels_for_app(app_id: str, ws_root: Optional[Path] = None) -> list[dict[str, Any]]:
    """Return list of all configured webhook destinations for app, merging app channels and workspace channels."""
    deploy_cfg = load_deploy_config(ws_root)
    apps = deploy_cfg.get("apps", {})
    app_cfg = apps.get(app_id, {}) if isinstance(apps, dict) else {}
    channels: list[dict[str, Any]] = []

    # 1. Multi-webhook array in app_cfg
    if isinstance(app_cfg.get("webhooks"), list):
        for w in app_cfg["webhooks"]:
            if isinstance(w, dict) and w.get("url"):
                channels.append({
                    "id": str(w.get("id") or f"app-{len(channels)}"),
                    "name": str(w.get("name") or "App Webhook"),
                    "url": str(w["url"]).strip(),
                    "enabled": bool(w.get("enabled", True)),
                    "provider": str(w.get("provider", "auto")),
                    "notify_on_success": bool(w.get("notify_on_success", True)),
                    "notify_on_failure": bool(w.get("notify_on_failure", True)),
                    "custom_template": str(w.get("custom_template") or ""),
                    "custom_headers": w.get("custom_headers") if isinstance(w.get("custom_headers"), dict) else {},
                    "phone": str(w.get("phone") or ""),
                    "scope": "app",
                })

    # Legacy single app webhook_url
    legacy_app_url = (app_cfg.get("webhook_url") or "").strip()
    if legacy_app_url and not any(c["url"] == legacy_app_url for c in channels):
        channels.append({
            "id": "legacy-app",
            "name": f"{app_id} Primary",
            "url": legacy_app_url,
            "enabled": bool(app_cfg.get("webhook_enabled", True)),
            "provider": str(app_cfg.get("webhook_provider", "auto")),
            "notify_on_success": bool(app_cfg.get("notify_on_success", True)),
            "notify_on_failure": bool(app_cfg.get("notify_on_failure", True)),
            "custom_template": "",
            "custom_headers": {},
            "phone": "",
            "scope": "app",
        })

    # 2. Workspace channels
    ws_channels: list[dict[str, Any]] = []
    if isinstance(deploy_cfg.get("workspace_webhooks"), list):
        for w in deploy_cfg["workspace_webhooks"]:
            if isinstance(w, dict) and w.get("url"):
                ws_channels.append({
                    "id": str(w.get("id") or f"ws-{len(ws_channels)}"),
                    "name": str(w.get("name") or "Workspace Channel"),
                    "url": str(w["url"]).strip(),
                    "enabled": bool(w.get("enabled", True)),
                    "provider": str(w.get("provider", "auto")),
                    "notify_on_success": bool(w.get("notify_on_success", True)),
                    "notify_on_failure": bool(w.get("notify_on_failure", True)),
                    "custom_template": str(w.get("custom_template") or ""),
                    "custom_headers": w.get("custom_headers") if isinstance(w.get("custom_headers"), dict) else {},
                    "phone": str(w.get("phone") or ""),
                    "scope": "workspace",
                })

    legacy_ws_url = (deploy_cfg.get("workspace_webhook_url") or "").strip()
    if legacy_ws_url and not any(c["url"] == legacy_ws_url for c in ws_channels):
        ws_channels.append({
            "id": "legacy-ws",
            "name": "Workspace Default",
            "url": legacy_ws_url,
            "enabled": bool(deploy_cfg.get("workspace_webhook_enabled", True)),
            "provider": str(deploy_cfg.get("workspace_webhook_provider", "auto")),
            "notify_on_success": bool(deploy_cfg.get("workspace_notify_on_success", True)),
            "notify_on_failure": bool(deploy_cfg.get("workspace_notify_on_failure", True)),
            "custom_template": "",
            "custom_headers": {},
            "phone": "",
            "scope": "workspace",
        })

    seen_urls = set()
    result: list[dict[str, Any]] = []
    for ch in channels + ws_channels:
        if ch["url"] not in seen_urls:
            seen_urls.add(ch["url"])
            result.append(ch)
    return result


def notify_job_finished(job: dict[str, Any], ws_root: Optional[Path] = None) -> None:
    """Evaluate and dispatch webhook notification across all configured channels when a deployment finishes."""
    if not job or job.get("is_pipeline_step"):
        return

    status = (job.get("status") or "error").lower()
    if status not in ("success", "error", "stopped"):
        return

    app = job.get("app") or ""
    channels = get_webhook_channels_for_app(app, ws_root=ws_root)
    if not channels:
        return

    is_success = status == "success"

    started = job.get("started_at")
    finished = job.get("finished_at") or time.time()
    duration_sec = int(finished - started) if started else None

    err_raw = (job.get("error") or "").strip()
    error_excerpt = "\n".join(err_raw.splitlines()[-5:]) if err_raw else ""

    event_data = compile_event_data(
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

    for ch in channels:
        if not ch.get("enabled") or not ch.get("url"):
            continue
        if is_success and not ch.get("notify_on_success", True):
            continue
        if not is_success and not ch.get("notify_on_failure", True):
            continue

        ch_url = ch["url"]
        provider = detect_webhook_provider(ch_url, ch.get("provider", "auto"))
        payload = build_webhook_payload(
            provider,
            event_data,
            custom_template=ch.get("custom_template", ""),
            phone=ch.get("phone", ""),
        )
        ch_headers = ch.get("custom_headers")

        def _async_send(target_url=ch_url, target_payload=payload, target_headers=ch_headers):
            try:
                res = send_outgoing_webhook(target_url, target_payload, headers=target_headers)
                if not res.get("success"):
                    logging.warning("Outgoing webhook to %s failed: %s", target_url, res.get("error"))
            except Exception:
                logging.exception("Exception during outgoing webhook dispatch")

        threading.Thread(target=_async_send, name="WebhookNotifyThread", daemon=True).start()

    # Two-way ChatOps: reply directly to trigger channel if response_url is present
    chatops_url = job.get("response_url")
    if chatops_url:
        chatops_payload = build_slack_payload(event_data)
        def _async_send_chatops(target_url=chatops_url, p=chatops_payload):
            try:
                res = send_outgoing_webhook(target_url, p)
                if not res.get("success"):
                    logging.warning("ChatOps response_url dispatch failed: %s", res.get("error"))
            except Exception:
                logging.exception("Exception during ChatOps response_url dispatch")

        threading.Thread(target=_async_send_chatops, name="ChatOpsReplyThread", daemon=True).start()


def notify_pipeline_finished(run: dict[str, Any], ws_root: Optional[Path] = None) -> None:
    """Evaluate and dispatch webhook notifications across all configured channels when a pipeline finishes."""
    if not run:
        return

    status = (run.get("status") or "error").lower()
    if status not in ("success", "error", "stopped"):
        return

    app = run.get("app") or ""
    channels = get_webhook_channels_for_app(app, ws_root=ws_root)
    if not channels:
        return

    is_success = status == "success"

    duration_sec = run.get("durationSeconds")
    if duration_sec is None and run.get("startedAt") and run.get("finishedAt"):
        duration_sec = int(run["finishedAt"] - run["startedAt"])

    event_data = compile_event_data(
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

    for ch in channels:
        if not ch.get("enabled") or not ch.get("url"):
            continue
        if is_success and not ch.get("notify_on_success", True):
            continue
        if not is_success and not ch.get("notify_on_failure", True):
            continue

        ch_url = ch["url"]
        provider = detect_webhook_provider(ch_url, ch.get("provider", "auto"))
        payload = build_webhook_payload(
            provider,
            event_data,
            custom_template=ch.get("custom_template", ""),
            phone=ch.get("phone", ""),
        )
        ch_headers = ch.get("custom_headers")

        def _async_send(target_url=ch_url, target_payload=payload, target_headers=ch_headers):
            try:
                res = send_outgoing_webhook(target_url, target_payload, headers=target_headers)
                if not res.get("success"):
                    logging.warning("Pipeline webhook to %s failed: %s", target_url, res.get("error"))
            except Exception:
                logging.exception("Exception during pipeline webhook dispatch")

        threading.Thread(target=_async_send, name="PipelineWebhookNotifyThread", daemon=True).start()


def test_webhook(
    url: str,
    provider: str = "auto",
    app_id: Optional[str] = None,
    ws_root: Optional[Path] = None,
    custom_template: str = "",
    custom_headers: Optional[dict[str, str]] = None,
    phone: str = "",
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

    payload = build_webhook_payload(
        detected_provider,
        sample_event,
        custom_template=custom_template,
        phone=phone,
    )
    result = send_outgoing_webhook(clean_url, payload, timeout=6.0, headers=custom_headers)
    result["provider"] = detected_provider
    return result
