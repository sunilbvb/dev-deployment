"""Android Keystore & Upload Key Expiry Sentinel."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Optional

from config import _resolve_app_dir, get_workspace_root, load_deploy_config
from .parsers import (
    EXPIRY_THRESHOLD_DAYS,
    _days_until,
    extract_validity_from_keystore_bytes,
)


def _locate_android_keystore(app_dir: Path, app_cfg: dict[str, Any]) -> tuple[Optional[Path], str]:
    """Locate Android signing keystore file and return (path, password)."""
    explicit = app_cfg.get("android_keystore_path") or app_cfg.get("upload_keystore_path")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = app_dir / p
        if p.is_file():
            return p.resolve(), str(app_cfg.get("android_keystore_password") or "")

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
        m = re.search(r"until:\s+([A-Za-z0-9: ]+)", raw, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip()
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
    exp = _parse_keystore_expiry_keytool(keystore_path, store_pass)
    if exp:
        return exp

    exp = _parse_keystore_expiry_openssl(keystore_path, store_pass)
    if exp:
        return exp

    try:
        raw_bytes = keystore_path.read_bytes()
        validities = extract_validity_from_keystore_bytes(raw_bytes)
        if validities:
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
