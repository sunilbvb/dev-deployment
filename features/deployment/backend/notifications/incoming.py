"""Incoming CI/CD Webhook Ingestion Gateway (GitHub, GitLab, Slack, cURL)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import parse_qs


def verify_incoming_webhook_auth(
    headers: dict[str, str],
    raw_body: bytes,
    query_params: dict[str, list[str]],
    webhook_secret: str,
) -> bool:
    """Validate incoming webhook payload against configured secret via HMAC or token headers."""
    if not webhook_secret:
        return False

    # 1. Shared secret headers (GitHub / GitLab / Custom)
    provided_secret = (
        headers.get("X-Webhook-Secret")
        or headers.get("X-Gitlab-Token")
        or ""
    ).strip()
    if provided_secret and hmac.compare_digest(provided_secret, webhook_secret):
        return True

    # 2. Bearer Authorization header
    auth_header = (headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()
        if bearer_token and hmac.compare_digest(bearer_token, webhook_secret):
            return True

    # 3. Query string secret
    q_secret = (query_params.get("secret") or query_params.get("token") or [""])[0].strip()
    if q_secret and hmac.compare_digest(q_secret, webhook_secret):
        return True

    # 4. GitHub HMAC SHA-256 signature
    signature_header = (headers.get("X-Hub-Signature-256") or "").strip()
    if signature_header.startswith("sha256="):
        expected_sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature_header[7:], expected_sig):
            return True

    # 5. Slack request signature (v0=...)
    slack_sig = (headers.get("X-Slack-Signature") or "").strip()
    if slack_sig:
        slack_time = headers.get("X-Slack-Request-Timestamp", "")
        sig_basestring = f"v0:{slack_time}:{raw_body.decode('utf-8', errors='replace')}".encode("utf-8")
        expected_slack_sig = "v0=" + hmac.new(webhook_secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()
        if hmac.compare_digest(slack_sig, expected_slack_sig):
            return True

    return False


def parse_incoming_webhook_payload(
    content_type_header: str,
    raw_body: bytes,
) -> tuple[dict[str, Any], bool]:
    """Parse JSON or form-encoded payload into a data dictionary, flagging Slack slash commands."""
    data: dict[str, Any] = {}
    is_slack_slash = False

    if content_type_header.startswith("application/x-www-form-urlencoded"):
        form = parse_qs(raw_body.decode("utf-8", errors="replace"))
        if "payload" in form:
            try:
                data = json.loads(form["payload"][0])
            except Exception:
                data = {}
        elif "command" in form or "text" in form:
            is_slack_slash = True
            raw_text = (form.get("text") or [""])[0].strip()
            tokens = raw_text.split()
            if tokens:
                if tokens[0].lower() in ("pipe", "pipeline", "run-pipeline") and len(tokens) >= 2:
                    data = {"pipeline": tokens[1]}
                    if len(tokens) >= 3:
                        data["flavor"] = tokens[2]
                elif tokens[0].lower() in ("app", "run", "build", "deploy") and len(tokens) >= 3:
                    data = {"app": tokens[1], "templateId": tokens[2]}
                    if len(tokens) >= 4:
                        data["flavor"] = tokens[3]
                else:
                    data = {"pipeline": tokens[0]}
                    if len(tokens) >= 2:
                        data["flavor"] = tokens[1]
    else:
        try:
            data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            data = {}

    return data, is_slack_slash
