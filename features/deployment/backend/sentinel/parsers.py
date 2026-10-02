"""ASN.1, binary certificate, and date parsing utilities for expiry sentinels."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any, Optional

import credentials

EXPIRY_THRESHOLD_DAYS = 30


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
