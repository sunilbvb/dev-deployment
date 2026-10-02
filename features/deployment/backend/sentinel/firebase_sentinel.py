"""Firebase project configuration mismatch and environment sync sentinel."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import plistlib
from typing import Any, Optional

from config import _resolve_app_dir, get_workspace_root, load_deploy_config


def _locate_firebase_android_config(app_dir: Path, flavor: str = "", app_cfg: Optional[dict[str, Any]] = None) -> Optional[Path]:
    """Find google-services.json for given app and flavor."""
    app_cfg = app_cfg or {}
    cfg_path = app_cfg.get(f"google_services_json_{flavor}") or app_cfg.get("google_services_json")
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve()

    candidates = [
        app_dir / "android" / "app" / "src" / flavor / "google-services.json",
        app_dir / "android" / "app" / "google-services.json",
        app_dir / "android" / "google-services.json",
        app_dir / "google-services.json",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()

    return None


def _locate_firebase_ios_config(app_dir: Path, flavor: str = "", app_cfg: Optional[dict[str, Any]] = None) -> Optional[Path]:
    """Find GoogleService-Info.plist for given app and flavor."""
    app_cfg = app_cfg or {}
    cfg_path = app_cfg.get(f"google_service_info_plist_{flavor}") or app_cfg.get("google_service_info_plist")
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve()

    candidates = [
        app_dir / "ios" / "Runner" / flavor / "GoogleService-Info.plist",
        app_dir / "ios" / "Firebase" / flavor / "GoogleService-Info.plist",
        app_dir / "ios" / "Runner" / "GoogleService-Info.plist",
        app_dir / "ios" / "GoogleService-Info.plist",
        app_dir / "GoogleService-Info.plist",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()

    return None


def check_firebase_mismatch(
    app_id: str,
    flavor: str = "prod",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Check for cross-platform Project ID mismatches and prod environment discrepancies."""
    ws = ws_root or get_workspace_root()
    app_dir = (ws / app_id) if (app_id and (ws / app_id).is_dir()) else (_resolve_app_dir(app_id) if app_id else ws)
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})

    android_path = _locate_firebase_android_config(app_dir, flavor=flavor, app_cfg=app_cfg)
    ios_path = _locate_firebase_ios_config(app_dir, flavor=flavor, app_cfg=app_cfg)

    android_info: dict[str, Any] = {}
    ios_info: dict[str, Any] = {}

    if android_path and android_path.is_file():
        try:
            data = json.loads(android_path.read_text(encoding="utf-8"))
            p_info = data.get("project_info", {})
            pkgs = []
            for c in data.get("client", []):
                pkg = (((c or {}).get("client_info") or {}).get("android_client_info") or {}).get("package_name")
                if pkg:
                    pkgs.append(str(pkg))
            android_info = {
                "path": str(android_path),
                "projectId": str(p_info.get("project_id") or ""),
                "projectNumber": str(p_info.get("project_number") or ""),
                "packages": pkgs,
            }
        except Exception:
            logging.exception("Failed to parse google-services.json at %s", android_path)

    if ios_path and ios_path.is_file():
        try:
            plist = plistlib.loads(ios_path.read_bytes())
            ios_info = {
                "path": str(ios_path),
                "projectId": str(plist.get("PROJECT_ID") or ""),
                "bundleId": str(plist.get("BUNDLE_ID") or ""),
                "googleAppId": str(plist.get("GOOGLE_APP_ID") or ""),
            }
        except Exception:
            logging.exception("Failed to parse GoogleService-Info.plist at %s", ios_path)

    alerts = []
    has_android_fb = bool(android_info.get("projectId"))
    has_ios_fb = bool(ios_info.get("projectId"))

    if not has_android_fb and not has_ios_fb:
        return {
            "applicable": False,
            "status": "not_configured",
            "message": "Firebase configuration files not present",
            "alerts": [],
        }

    # 1. Cross-platform Project ID Mismatch
    if has_android_fb and has_ios_fb:
        p_android = android_info["projectId"].strip()
        p_ios = ios_info["projectId"].strip()
        if p_android.lower() != p_ios.lower():
            alerts.append({
                "id": "firebase_project_mismatch",
                "category": "firebase",
                "severity": "critical",
                "title": "Firebase Project ID Mismatch (Android vs iOS)",
                "message": f"Android google-services.json points to '{p_android}', but iOS GoogleService-Info.plist points to '{p_ios}'.",
                "androidProjectId": p_android,
                "iosProjectId": p_ios,
                "hint": "Ensure both Android and iOS configurations point to the same Firebase project before releasing.",
            })

    # 2. Production Flavor using Non-Prod Firebase Project
    is_prod_flavor = (flavor or "").lower() in ("prod", "production", "release")
    test_keywords = ("-dev", "_dev", ".dev", "-stage", "-staging", "_stage", "-qa", "_qa", "-test", "_test", "-sandbox")

    for platform_label, info in [("Android", android_info), ("iOS", ios_info)]:
        pid = info.get("projectId", "").lower()
        if is_prod_flavor and any(kw in pid for kw in test_keywords):
            alerts.append({
                "id": f"firebase_{platform_label.lower()}_env_mismatch",
                "category": "firebase",
                "severity": "warning",
                "title": f"Production Flavor using Non-Prod Firebase ({platform_label})",
                "message": f"Production build flavor '{flavor}' is using a development/test Firebase project: '{info.get('projectId')}'.",
                "projectId": info.get("projectId"),
                "hint": f"Switch {platform_label} Firebase config to the production project in Setup -> Firebase tab.",
            })

    status = "ok"
    if any(a["severity"] == "critical" for a in alerts):
        status = "critical"
    elif any(a["severity"] == "warning" for a in alerts):
        status = "warning"

    return {
        "applicable": True,
        "status": status,
        "android": android_info,
        "ios": ios_info,
        "alerts": alerts,
    }


check_firebase_sync = check_firebase_mismatch
