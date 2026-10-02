"""Apple App Store Connect .p8 key, certificate, and provisioning profile expiry sentinel."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import _resolve_app_dir, get_workspace_root, load_deploy_config
import jobs
from .parsers import (
    EXPIRY_THRESHOLD_DAYS,
    _inspect_p8_key,
)


def check_apple_expiry(
    app_id: str,
    flavor: str = "prod",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Check Apple App Store Connect .p8 key and distribution certificate / profile expiry."""
    ws = ws_root or get_workspace_root()
    app_dir = (ws / app_id) if (app_id and (ws / app_id).is_dir()) else (_resolve_app_dir(app_id) if app_id else ws)
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})

    has_ios = (app_dir / "ios").is_dir()
    if not has_ios:
        return {
            "applicable": False,
            "status": "not_applicable",
            "message": "App has no iOS target",
            "alerts": [],
        }

    alerts = []
    now = datetime.now(timezone.utc).date()

    # A. Check Apple App Store Connect API Key (.p8)
    import sys
    sentinel_mod = sys.modules.get("sentinel")
    p8_inspector = getattr(sentinel_mod, "_inspect_p8_key", _inspect_p8_key) if sentinel_mod else _inspect_p8_key
    p8_info = p8_inspector(app_dir, app_cfg, app_id=app_id)
    p8_key_id = p8_info.get("key_id") or ""
    p8_path = Path(p8_info["p8_path"]) if p8_info.get("p8_path") else None
    p8_expiry_date = p8_info.get("expires_at") or ""

    if p8_expiry_date:
        try:
            days = (date.fromisoformat(p8_expiry_date) - now).days
            if days < 0:
                alerts.append({
                    "id": "apple_api_key_expired",
                    "category": "apple",
                    "severity": "critical",
                    "title": "Apple .p8 API Key Expired",
                    "message": f"App Store Connect API key ({p8_key_id or 'AuthKey'}) expired on {p8_expiry_date} ({abs(days)} days ago).",
                    "expiresOn": p8_expiry_date,
                    "daysRemaining": days,
                    "hint": "Generate a new App Store Connect API Key in Apple Developer Portal.",
                })
            elif days <= EXPIRY_THRESHOLD_DAYS:
                alerts.append({
                    "id": "apple_api_key_expiring",
                    "category": "apple",
                    "severity": "warning",
                    "title": "Apple .p8 API Key Expiring Soon",
                    "message": f"App Store Connect API key ({p8_key_id or 'AuthKey'}) expires in {days} days on {p8_expiry_date}.",
                    "expiresOn": p8_expiry_date,
                    "daysRemaining": days,
                    "hint": "Renew or regenerate App Store Connect API Key before release.",
                })
        except Exception:
            pass

    # B. Check Apple Distribution Certificate & Provisioning Profile
    ios_expiry = jobs.check_ios_expiry(app_id, flavor=flavor or "prod")
    cert = ios_expiry.get("certificate") or {}
    profile = ios_expiry.get("provisioningProfile") or {}

    for item, item_kind in [(cert, "Distribution Certificate"), (profile, "Provisioning Profile")]:
        exp_on = item.get("expiresOn")
        if not exp_on:
            continue
        try:
            days = (date.fromisoformat(exp_on) - now).days
            if days < 0:
                alerts.append({
                    "id": f"apple_{item_kind.lower().replace(' ', '_')}_expired",
                    "category": "apple",
                    "severity": "critical",
                    "title": f"Apple {item_kind} Expired",
                    "message": f"Apple {item_kind} for '{app_id}' expired on {exp_on} ({abs(days)} days ago).",
                    "expiresOn": exp_on,
                    "daysRemaining": days,
                    "source": item.get("source"),
                    "hint": f"Regenerate {item_kind} in Apple Developer Portal and update signing identity.",
                })
            elif days <= EXPIRY_THRESHOLD_DAYS:
                alerts.append({
                    "id": f"apple_{item_kind.lower().replace(' ', '_')}_expiring",
                    "category": "apple",
                    "severity": "warning",
                    "title": f"Apple {item_kind} Expiring Soon",
                    "message": f"Apple {item_kind} for '{app_id}' expires in {days} days on {exp_on}.",
                    "expiresOn": exp_on,
                    "daysRemaining": days,
                    "source": item.get("source"),
                    "hint": f"Renew {item_kind} in Apple Developer Portal before release.",
                })
        except Exception:
            pass

    status = "ok"
    if any(a["severity"] == "critical" for a in alerts):
        status = "critical"
    elif any(a["severity"] == "warning" for a in alerts):
        status = "warning"

    return {
        "applicable": True,
        "status": status,
        "p8KeyId": p8_key_id,
        "p8Configured": bool(p8_path and p8_path.exists()),
        "certificate": cert,
        "provisioningProfile": profile,
        "alerts": alerts,
    }
