"""Apple App Store Connect .p8 key, certificate, and provisioning profile expiry sentinel."""

from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from pathlib import Path
import plistlib
import re
import subprocess
from typing import Any, Optional

from config import _resolve_app_dir, get_workspace_root, load_deploy_config
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
    ios_expiry = check_ios_expiry(app_id, flavor=flavor or "prod")
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


def _app_has_ios(app_id: str) -> bool:
    app_dir = _resolve_app_dir(app_id)
    return (app_dir / "ios").exists()


def _run_cli(args: list[str], input_bytes: Optional[bytes] = None, timeout: float = 5.0) -> tuple[int, bytes, bytes]:
    try:
        r = subprocess.run(args, input=input_bytes, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception:
        return 1, b"", b""


def _find_keychain_distribution_certs() -> list[dict]:
    rc, out, _ = _run_cli(["security", "find-certificate", "-a", "-c", "Apple Distribution", "-p", "login.keychain"])
    if rc != 0 or not out:
        return []
    pem_blocks = re.findall(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", out, re.DOTALL)
    results = []
    for block in pem_blocks:
        rc2, out2, _ = _run_cli(["openssl", "x509", "-noout", "-subject", "-enddate", "-fingerprint", "-sha1"], input_bytes=block)
        if rc2 != 0:
            continue
        text = out2.decode(errors="replace")
        end_match = re.search(r"notAfter=(.+)", text)
        subj_match = re.search(r"subject=(.+)", text)
        expires_on = None
        if end_match:
            try:
                expires_on = datetime.strptime(end_match.group(1).strip(), "%b %d %H:%M:%S %Y %Z").date().isoformat()
            except Exception:
                logging.exception("Failed to parse certificate expiration date")
        if expires_on:
            results.append({"name": subj_match.group(1).strip() if subj_match else None, "expiresOn": expires_on})
    return sorted(results, key=lambda c: c["expiresOn"])


def _find_local_mobileprovision_files(app_id: str) -> list[Path]:
    search_dir = get_workspace_root() / "private_keys" / app_id
    if not search_dir.exists():
        return []
    return list(search_dir.rglob("*.mobileprovision"))


def _read_mobileprovision_metadata(path: Path) -> Optional[dict]:
    rc, out, _ = _run_cli(["security", "cms", "-D", "-i", str(path)])
    if rc != 0 or not out:
        return None
    try:
        plist = plistlib.loads(out)
    except Exception:
        return None
    expires = plist.get("ExpirationDate")
    entitlements = plist.get("Entitlements", {}) or {}
    return {
        "path": str(path),
        "name": plist.get("Name"),
        "uuid": plist.get("UUID"),
        "applicationIdentifier": entitlements.get("application-identifier"),
        "isDistributionStyle": "ProvisionedDevices" not in plist,
        "expiresOn": expires.date().isoformat() if hasattr(expires, "date") else None,
    }


def _select_matching_profile(candidates: list[dict], app_id: str, flavor: str) -> Optional[dict]:
    if not candidates:
        return None
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})
    bundle_id = str(app_cfg.get(f"bundle_id_{flavor}") or app_cfg.get("bundle_id_prod") or "").strip()
    scored = []
    for c in candidates:
        app_identifier = str(c.get("applicationIdentifier") or "")
        matches_bundle = bool(bundle_id) and app_identifier.endswith(bundle_id)
        scored.append((matches_bundle, c.get("isDistributionStyle", False), c))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scored[0][2] if scored else None


def _find_last_distribution_summary(app_id: str) -> Optional[Path]:
    app_dir = _resolve_app_dir(app_id)
    candidate = app_dir / "build" / "ios" / "ipa" / "DistributionSummary.plist"
    return candidate if candidate.exists() else None


def _parse_distribution_summary_expiry(raw: str) -> dict:
    try:
        a, b, yy = (int(x) for x in raw.split("/"))
    except Exception:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "unparseable"}
    year = 2000 + yy
    if a > 12:
        day, month = a, b
    elif b > 12:
        day, month = b, a
    else:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "ambiguous"}
    try:
        d = date(year, month, day)
        return {"raw": raw, "expiresOn": d.isoformat(), "formatConfidence": "day_first_unambiguous"}
    except ValueError:
        return {"raw": raw, "expiresOn": None, "formatConfidence": "unparseable"}


def check_ios_expiry(app: str, flavor: str = "prod") -> dict[str, Any]:
    if not app:
        return {"success": False, "error": "app is required"}
    if not _app_has_ios(app):
        return {"success": True, "app": app, "flavor": flavor, "status": "not_ios_app"}

    warnings: list[str] = []
    now = datetime.now(timezone.utc)

    def _status_for(expires_on: Optional[str]) -> str:
        if not expires_on:
            return "unknown"
        days = (date.fromisoformat(expires_on) - now.date()).days
        if days < 0:
            return "expired"
        if days < EXPIRY_THRESHOLD_DAYS:
            return "warning"
        return "ok"

    certs = _find_keychain_distribution_certs()
    cert_result = None
    if certs:
        best = certs[0]
        cert_result = {**best, "source": "keychain", "confidence": "high", "status": _status_for(best["expiresOn"]), "candidates": certs if len(certs) > 1 else None}
        if len(certs) > 1:
            warnings.append(f"{len(certs)} 'Apple Distribution' identities found in Keychain - showing the soonest-expiring; verify which one Xcode will actually pick.")

    profile_result = None
    local_files = _find_local_mobileprovision_files(app)
    profiles = [m for m in (_read_mobileprovision_metadata(p) for p in local_files) if m]
    matched = _select_matching_profile(profiles, app, flavor)
    if matched:
        profile_result = {**matched, "source": "local_mobileprovision", "confidence": "high", "status": _status_for(matched["expiresOn"])}

    summary_path = _find_last_distribution_summary(app)
    if summary_path and (not cert_result or not profile_result):
        try:
            summary = plistlib.load(summary_path.open("rb"))
            build_key = next(iter(summary))
            entry = summary[build_key][0]
            cert_parsed = _parse_distribution_summary_expiry(entry["certificate"]["dateExpires"])
            profile_parsed = _parse_distribution_summary_expiry(entry["profile"]["dateExpires"])
            stale_days = (now - datetime.fromtimestamp(summary_path.stat().st_mtime, timezone.utc)).days
            if cert_result is None:
                cert_result = {**cert_parsed, "source": "last_build_summary", "confidence": "low", "bestEffort": True, "staleBuildDays": stale_days, "status": _status_for(cert_parsed["expiresOn"]) if cert_parsed["expiresOn"] else "unknown"}
            if profile_result is None:
                profile_result = {**profile_parsed, "source": "last_build_summary", "confidence": "low", "bestEffort": True, "staleBuildDays": stale_days, "status": _status_for(profile_parsed["expiresOn"]) if profile_parsed["expiresOn"] else "unknown"}
            if "Cloud Managed" in entry["certificate"].get("type", "") and local_files:
                warnings.append("Local .mobileprovision file(s) found on disk, but the last real build was signed with a Cloud Managed (Xcode-automatic) identity - the local files may be stale test artifacts, not what will actually be used.")
        except Exception:
            logging.exception("Failed to parse distribution summary plist")

    return {
        "success": True,
        "app": app,
        "flavor": flavor,
        "thresholdDays": EXPIRY_THRESHOLD_DAYS,
        "checkedAt": now.isoformat(),
        "certificate": cert_result or {"status": "unknown", "source": "none"},
        "provisioningProfile": profile_result or {"status": "unknown", "source": "none"},
        "warnings": warnings,
    }

