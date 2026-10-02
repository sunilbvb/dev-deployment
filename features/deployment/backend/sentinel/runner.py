"""Master Sentinel aggregator across Apple, Android, and Firebase monitors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from config import get_apps_config_file, get_workspace_root
from .android_sentinel import check_android_keystore_expiry
from .apple_sentinel import check_apple_expiry
from .firebase_sentinel import check_firebase_mismatch


def check_app_sentinel(
    app_id: str,
    flavor: str = "prod",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Run full Sentinel diagnostics for an app: Apple certs, Android keystores, and Firebase configs."""
    ws = ws_root or get_workspace_root()

    apple = check_apple_expiry(app_id, flavor=flavor, ws_root=ws)
    android = check_android_keystore_expiry(app_id, flavor=flavor, ws_root=ws)
    firebase = check_firebase_mismatch(app_id, flavor=flavor, ws_root=ws)

    all_alerts = []
    all_alerts.extend(apple.get("alerts", []))
    all_alerts.extend(android.get("alerts", []))
    all_alerts.extend(firebase.get("alerts", []))

    critical_count = sum(1 for a in all_alerts if a["severity"] == "critical")
    warning_count = sum(1 for a in all_alerts if a["severity"] == "warning")

    if critical_count > 0:
        overall_severity = "critical"
        badge_variant = "danger"
        badge_label = f"{critical_count} Panic Risk{'s' if critical_count > 1 else ''}"
    elif warning_count > 0:
        overall_severity = "warning"
        badge_variant = "warning"
        badge_label = f"{warning_count} Expiry / Config Warning{'s' if warning_count > 1 else ''}"
    else:
        overall_severity = "ok"
        badge_variant = "success"
        badge_label = "Sentinel OK"

    has_alert = len(all_alerts) > 0

    return {
        "success": True,
        "app": app_id,
        "flavor": flavor,
        "hasAlert": has_alert,
        "severity": overall_severity,
        "badge": {
            "hasAlert": has_alert,
            "count": len(all_alerts),
            "criticalCount": critical_count,
            "warningCount": warning_count,
            "label": badge_label,
            "variant": badge_variant,
        },
        "alerts": all_alerts,
        "checks": {
            "apple": apple,
            "android": android,
            "firebase": firebase,
        },
    }


def check_workspace_sentinel(
    ws_root: Optional[Path] = None,
    flavor: str = "prod",
) -> dict[str, Any]:
    """Scan all registered apps in the workspace and aggregate Sentinel alerts."""
    ws = ws_root or get_workspace_root()
    apps_file = ws / ".dev-dashboard" / "apps_config.json"
    if not apps_file.exists():
        apps_file = get_apps_config_file()
    apps_list = []
    if apps_file.exists():
        try:
            raw = json.loads(apps_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                apps_list = [a["id"] for a in raw if isinstance(a, dict) and a.get("id") and not a.get("is_package")]
        except Exception:
            pass

    if not apps_list:
        apps_list = [ws.name]

    per_app = {}
    aggregated_alerts = []

    for a_id in apps_list:
        res = check_app_sentinel(a_id, flavor=flavor, ws_root=ws)
        per_app[a_id] = res
        for al in res.get("alerts", []):
            al_copy = dict(al)
            al_copy["app"] = a_id
            aggregated_alerts.append(al_copy)

    critical_count = sum(1 for a in aggregated_alerts if a["severity"] == "critical")
    warning_count = sum(1 for a in aggregated_alerts if a["severity"] == "warning")
    has_alert = len(aggregated_alerts) > 0

    if critical_count > 0:
        overall_severity = "critical"
        badge_variant = "danger"
        badge_label = f"{critical_count} Panic Risk{'s' if critical_count > 1 else ''}"
    elif warning_count > 0:
        overall_severity = "warning"
        badge_variant = "warning"
        badge_label = f"{warning_count} Expiry Warning{'s' if warning_count > 1 else ''}"
    else:
        overall_severity = "ok"
        badge_variant = "success"
        badge_label = "Sentinel OK"

    return {
        "success": True,
        "hasAlert": has_alert,
        "severity": overall_severity,
        "badge": {
            "hasAlert": has_alert,
            "count": len(aggregated_alerts),
            "criticalCount": critical_count,
            "warningCount": warning_count,
            "label": badge_label,
            "variant": badge_variant,
        },
        "alerts": aggregated_alerts,
        "apps": per_app,
    }


check_credentials_expiry = check_app_sentinel
