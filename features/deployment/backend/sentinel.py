"""Certificate & Keystore Expiry Sentinel for Dev Deployment Console.

Prevents panic releases by proactively monitoring:
1. Apple .p8 API keys and Apple Distribution certificates expiring within 30 days (or expired).
2. Android upload keys and keystore certificates nearing expiration (<= 30 days or expired).
3. Firebase project configuration mismatches (Android google-services.json vs iOS GoogleService-Info.plist,
   production flavor using test project IDs, or package/bundle ID divergence).

Python standard library only (datetime, pathlib, re, json, subprocess, plistlib).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
from typing import Any, Optional

from config import (
    _resolve_app_dir,
    get_apps_config_file,
    get_workspace_root,
    load_deploy_config,
)
import credentials

EXPIRY_THRESHOLD_DAYS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Helpers & Parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_asn1_time(tag: int, val_bytes: bytes) -> Optional[str]:
    """Parse ASN.1 UTCTime (0x17) or GeneralizedTime (0x18) string to ISO YYYY-MM-DD."""
    s = val_bytes.decode("ascii", errors="ignore").strip()
    try:
        if tag == 0x17 and len(s) >= 12:  # YYMMDDHHMMSSZ
            year = int(s[:2])
            full_year = 1900 + year if year >= 50 else 2000 + year
            dt = datetime.strptime(f"{full_year:04d}" + s[2:12], "%Y%m%d%H%M%S")
            return dt.date().isoformat()
        elif tag == 0x18 and len(s) >= 14:  # YYYYMMDDHHMMSSZ
            dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
            return dt.date().isoformat()
    except Exception:
        pass
    return None


def extract_validity_from_keystore_bytes(data: bytes) -> list[tuple[str, str]]:
    """Scan raw keystore/certificate bytes for ASN.1 Validity sequences."""
    matches = re.findall(
        rb"\x30[\x18-\x2c]"
        rb"(\x17|\x18)([\x0b-\x13])([0-9]{10,14}[A-Za-z])"
        rb"(\x17|\x18)([\x0b-\x13])([0-9]{10,14}[A-Za-z])",
        data,
    )
    results = []
    for tag1_b, _, time1_b, tag2_b, _, time2_b in matches:
        tag1 = tag1_b[0]
        tag2 = tag2_b[0]
        t1 = _parse_asn1_time(tag1, time1_b)
        t2 = _parse_asn1_time(tag2, time2_b)
        if t1 and t2:
            results.append((t1, t2))
    return results


def _days_until(iso_date: str) -> int:
    """Return integer days from today (UTC) until given ISO date."""
    target = date.fromisoformat(iso_date)
    today = datetime.now(timezone.utc).date()
    return (target - today).days


def _inspect_p8_key(app_dir: Path, app_cfg: dict[str, Any], app_id: str = "") -> dict[str, Any]:
    """Inspect Apple App Store Connect .p8 key from app config, directory, credentials, or standard home path."""
    p8_key_id = app_cfg.get("apple_key_id") or ""
    p8_path = None
    if p8_key_id:
        cand = Path.home() / ".appstoreconnect" / "private_keys" / f"AuthKey_{p8_key_id}.p8"
        if cand.is_file():
            p8_path = cand

    if not p8_path:
        p8_files = list(app_dir.glob("AuthKey_*.p8")) + list(app_dir.glob("*.p8"))
        if p8_files:
            p8_path = p8_files[0]
            if not p8_key_id:
                m = re.search(r"AuthKey_([A-Za-z0-9]+)\.p8", p8_path.name)
                if m:
                    p8_key_id = m.group(1)

    if not p8_path and app_id:
        try:
            cred_stat = credentials.get_credentials_status(app_id)
            apple_cred = cred_stat.get("apple") or {}
            if not p8_key_id and apple_cred.get("key_id"):
                p8_key_id = apple_cred.get("key_id")
            if not p8_path and apple_cred.get("path"):
                p8_path = Path(apple_cred["path"])
        except Exception:
            pass

    expires_at = app_cfg.get("apple_p8_expires_on") or app_cfg.get("apple_key_expires_on") or ""
    return {
        "key_id": p8_key_id,
        "p8_path": str(p8_path) if p8_path else None,
        "expires_at": expires_at,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Apple .p8 & Distribution Certificate Sentinel
# ─────────────────────────────────────────────────────────────────────────────

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
    p8_info = _inspect_p8_key(app_dir, app_cfg, app_id=app_id)
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
    import jobs
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


# ─────────────────────────────────────────────────────────────────────────────
# 2. Android Keystore & Upload Key Sentinel
# ─────────────────────────────────────────────────────────────────────────────

def _locate_android_keystore(app_dir: Path, app_cfg: dict[str, Any]) -> tuple[Optional[Path], str]:
    """Locate Android signing keystore file and return (path, password)."""
    # 1. Check explicit config in deploy_config.json
    explicit = app_cfg.get("android_keystore_path") or app_cfg.get("upload_keystore_path")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve(), str(app_cfg.get("android_keystore_password") or "")

    # 2. Check key.properties / keystore.properties in android/
    for prop_name in ("key.properties", "keystore.properties"):
        prop_file = app_dir / "android" / prop_name
        if prop_file.is_file():
            try:
                content = prop_file.read_text(encoding="utf-8", errors="replace")
                store_file_rel = ""
                store_pass = ""
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("storeFile="):
                        store_file_rel = line.split("=", 1)[1].strip()
                    elif line.startswith("storePassword="):
                        store_pass = line.split("=", 1)[1].strip()
                if store_file_rel:
                    cand = (app_dir / "android" / store_file_rel).resolve()
                    if cand.is_file():
                        return cand, store_pass
                    cand2 = (app_dir / store_file_rel).resolve()
                    if cand2.is_file():
                        return cand2, store_pass
            except Exception:
                pass

    # 3. Check standard conventions in android/app/ and android/
    candidates = [
        app_dir / "android" / "app" / "upload-keystore.jks",
        app_dir / "android" / "app" / "keystore.jks",
        app_dir / "android" / "upload-keystore.jks",
        app_dir / "android" / "app" / "release.jks",
        app_dir / "android" / "app" / "release.keystore",
        app_dir / "android" / "release.keystore",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve(), ""

    return None, ""


def _parse_keystore_expiry_keytool(keystore_path: Path, store_pass: str = "") -> Optional[str]:
    """Extract keystore expiration using keytool CLI if available."""
    keytool = shutil.which("keytool")
    if not keytool:
        return None

    cmd = [keytool, "-list", "-v", "-keystore", str(keystore_path)]
    if store_pass:
        cmd.extend(["-storepass", store_pass])
    else:
        cmd.extend(["-storepass", ""])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.5)
        raw = res.stdout + res.stderr
        # Look for: "until: Mon Oct 26 12:00:00 UTC 2026" or similar
        m = re.search(r"until:\s+([A-Za-z0-9: ]+)", raw, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip()
            # Try parsing standard keytool date formats
            for fmt in (
                "%a %b %d %H:%M:%S %Z %Y",
                "%b %d, %Y",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def _parse_keystore_expiry_openssl(keystore_path: Path, store_pass: str = "") -> Optional[str]:
    """Extract keystore expiration using openssl pkcs12 if available."""
    openssl = shutil.which("openssl")
    if not openssl:
        return None

    p1 = None
    p2 = None
    try:
        p1 = subprocess.Popen(
            [openssl, "pkcs12", "-in", str(keystore_path), "-nodes", "-nokeys", "-passin", f"pass:{store_pass}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            [openssl, "x509", "-noout", "-enddate"],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if p1.stdout:
            p1.stdout.close()
        out, _ = p2.communicate(timeout=3.5)
        p1.wait(timeout=1.0)
        m = re.search(r"notAfter=(.+)", out)
        if m:
            raw_date = m.group(1).strip()
            try:
                dt = datetime.strptime(raw_date, "%b %d %H:%M:%S %Y %Z")
                return dt.date().isoformat()
            except ValueError:
                pass
    except Exception:
        pass
    finally:
        for p in (p1, p2):
            if p is not None:
                try:
                    if p.stdout and not p.stdout.closed:
                        p.stdout.close()
                    if p.stderr and not p.stderr.closed:
                        p.stderr.close()
                    if p.poll() is None:
                        p.kill()
                        p.wait(timeout=0.5)
                except Exception:
                    pass
    return None


def inspect_android_keystore_expiry(keystore_path: Path, store_pass: str = "") -> Optional[str]:
    """Multi-tiered keystore certificate expiry extractor (keytool -> openssl -> pure Python ASN.1)."""
    # Tier 1: keytool CLI
    exp = _parse_keystore_expiry_keytool(keystore_path, store_pass)
    if exp:
        return exp

    # Tier 2: openssl pkcs12
    exp = _parse_keystore_expiry_openssl(keystore_path, store_pass)
    if exp:
        return exp

    # Tier 3: Pure Python binary X.509 ASN.1 validity scan
    try:
        raw_bytes = keystore_path.read_bytes()
        validities = extract_validity_from_keystore_bytes(raw_bytes)
        if validities:
            # Pick the furthest expiration date (or earliest if multiple certs)
            not_afters = [v[1] for v in validities if v[1]]
            if not_afters:
                not_afters.sort()
                return not_afters[0]
    except Exception:
        pass

    return None


def check_android_keystore_expiry(
    app_id: str,
    flavor: str = "prod",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Check Android upload keystore certificate expiration status."""
    ws = ws_root or get_workspace_root()
    app_dir = (ws / app_id) if (app_id and (ws / app_id).is_dir()) else (_resolve_app_dir(app_id) if app_id else ws)
    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(app_id, {})

    has_android = (app_dir / "android").is_dir()
    if not has_android:
        return {
            "applicable": False,
            "status": "not_applicable",
            "message": "App has no Android target",
            "alerts": [],
        }

    keystore_path, store_pass = _locate_android_keystore(app_dir, app_cfg)
    if not keystore_path or not keystore_path.is_file():
        return {
            "applicable": True,
            "status": "missing",
            "keystoreFound": False,
            "message": "No upload keystore found for Android signing",
            "alerts": [],
        }

    expires_on = inspect_android_keystore_expiry(keystore_path, store_pass)
    alerts = []
    status = "ok"
    days_rem = None

    if expires_on:
        days_rem = _days_until(expires_on)
        if days_rem < 0:
            status = "critical"
            alerts.append({
                "id": "android_keystore_expired",
                "category": "android",
                "severity": "critical",
                "title": "Android Keystore Certificate Expired",
                "message": f"Upload keystore '{keystore_path.name}' expired on {expires_on} ({abs(days_rem)} days ago)! Play Store will reject uploads.",
                "keystorePath": str(keystore_path),
                "expiresOn": expires_on,
                "daysRemaining": days_rem,
                "hint": "Generate a new upload key and request a key reset in Google Play Console.",
            })
        elif days_rem <= EXPIRY_THRESHOLD_DAYS:
            status = "warning"
            alerts.append({
                "id": "android_keystore_expiring",
                "category": "android",
                "severity": "warning",
                "title": "Android Keystore Nearing Expiration",
                "message": f"Upload keystore '{keystore_path.name}' expires in {days_rem} days on {expires_on}.",
                "keystorePath": str(keystore_path),
                "expiresOn": expires_on,
                "daysRemaining": days_rem,
                "hint": "Plan upload key renewal in Google Play Console before expiration.",
            })

    return {
        "applicable": True,
        "status": status,
        "keystoreFound": True,
        "keystorePath": str(keystore_path),
        "filename": keystore_path.name,
        "expiresOn": expires_on,
        "validTo": expires_on,
        "daysRemaining": days_rem,
        "alerts": alerts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Firebase Config Project ID Mismatch Sentinel
# ─────────────────────────────────────────────────────────────────────────────

def _locate_firebase_android_config(app_dir: Path, flavor: str = "", app_cfg: Optional[dict[str, Any]] = None) -> Optional[Path]:
    """Find google-services.json for given app and flavor."""
    app_cfg = app_cfg or {}
    # 1. Configured path
    cfg_path = app_cfg.get(f"google_services_json_{flavor}") or app_cfg.get("google_services_json")
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve()

    # 2. Standard flutter / android paths
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
    # 1. Configured path
    cfg_path = app_cfg.get(f"google_service_info_plist_{flavor}") or app_cfg.get("google_service_info_plist")
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve()

    # 2. Standard flutter / ios paths
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


# ─────────────────────────────────────────────────────────────────────────────
# 4. Master Sentinel Check
# ─────────────────────────────────────────────────────────────────────────────

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
