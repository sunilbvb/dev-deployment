"""Universal Webhooks & Notifications package for Dev Deployment Console.

Modular architecture:
- templates: Dynamic variable substitution & event compilation
- channels: Multi-destination outgoing dispatchers (Slack, Discord, Teams, Google Chat, WhatsApp, Custom)
- incoming: Universal CI/CD ingestion gateway (GitHub, GitLab, Slack, cURL)
"""

from .templates import (
    compile_event_data,
    detect_platform_and_track,
    format_duration,
    get_git_commit_summary,
    render_template,
    resolve_app_details,
)
from .channels import (
    build_discord_payload,
    build_generic_payload,
    build_google_chat_payload,
    build_slack_payload,
    build_teams_payload,
    build_webhook_payload,
    build_whatsapp_payload,
    detect_webhook_provider,
    get_webhook_channels_for_app,
    get_webhook_config_for_app,
    notify_job_finished,
    notify_pipeline_finished,
    send_outgoing_webhook,
    test_webhook,
)
from .incoming import (
    parse_incoming_webhook_payload,
    verify_incoming_webhook_auth,
)

# Alias for backward compatibility
build_custom_template_payload = render_template

__all__ = [
    "detect_webhook_provider",
    "get_git_commit_summary",
    "format_duration",
    "resolve_app_details",
    "detect_platform_and_track",
    "render_template",
    "build_slack_payload",
    "build_discord_payload",
    "build_teams_payload",
    "build_google_chat_payload",
    "build_whatsapp_payload",
    "build_custom_template_payload",
    "build_generic_payload",
    "build_webhook_payload",
    "send_outgoing_webhook",
    "get_webhook_config_for_app",
    "get_webhook_channels_for_app",
    "compile_event_data",
    "notify_job_finished",
    "notify_pipeline_finished",
    "test_webhook",
    "verify_incoming_webhook_auth",
    "parse_incoming_webhook_payload",
]
