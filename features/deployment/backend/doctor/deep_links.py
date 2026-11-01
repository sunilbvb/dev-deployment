"""Pre-Release Deep Link & Universal Link Validator.

Inspects AndroidManifest.xml and iOS entitlements/project for registered web domains,
queries live `/.well-known/assetlinks.json` and `/.well-known/apple-app-site-association`,
and validates whether production keystore SHA-256 fingerprints and Apple Team IDs match.
Pure Python standard library only.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger("doctor.deep_links")


def extract_android_domains(app_dir: Path) -> list[str]:
    """Scan Android manifests for autoVerify HTTP/HTTPS intent-filters and extract domains."""
    domains: set[str] = set()
    manifests = list(app_dir.glob("android/app/src/*/AndroidManifest.xml"))
    if not manifests:
        manifests = list(app_dir.glob("**/AndroidManifest.xml"))

    for manifest_path in manifests:
        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
            ns = {"android": "http://schemas.android.com/apk/res/android"}
            for intent in root.findall(".//intent-filter", ns):
                auto_verify = intent.attrib.get(f"{{{ns['android']}}}autoVerify", "false")
                # Also inspect standard VIEW intents with https scheme
                has_view = any(
                    action.attrib.get(f"{{{ns['android']}}}name") == "android.intent.action.VIEW"
                    for action in intent.findall("action")
                )
                for data in intent.findall("data"):
                    scheme = data.attrib.get(f"{{{ns['android']}}}scheme", "")
                    host = data.attrib.get(f"{{{ns['android']}}}host", "")
                    if host and (scheme in ("http", "https") or auto_verify == "true" or has_view):
                        clean_host = host.lstrip("*.").strip()
                        if clean_host and "." in clean_host:
                            domains.add(clean_host)
        except Exception as e:
            logger.debug("Failed to parse manifest %s: %s", manifest_path, e)
    return sorted(domains)


def extract_ios_domains(app_dir: Path) -> list[str]:
    """Scan iOS Runner.entitlements for com.apple.developer.associated-domains."""
    domains: set[str] = set()
    entitlements = list(app_dir.glob("ios/Runner/*.entitlements")) + list(app_dir.glob("ios/*.entitlements"))
    for ent_path in entitlements:
        try:
            content = ent_path.read_text(encoding="utf-8", errors="replace")
            # Look for applinks:domain.com
            for match in re.finditer(r"applinks:([a-zA-Z0-9.\-_]+)", content):
                dom = match.group(1).strip()
                if dom and "." in dom:
                    domains.add(dom)
        except Exception as e:
            logger.debug("Failed to parse entitlements %s: %s", ent_path, e)
    return sorted(domains)


def _normalize_fingerprint(fp: str) -> str:
    """Normalize SHA-256 fingerprint by stripping colons, spaces, and converting to uppercase."""
    return re.sub(r"[^A-Fa-f0-9]", "", fp).upper()


def fetch_url_json(url: str, timeout: float = 3.5) -> tuple[Optional[Any], Optional[str]]:
    """Fetch URL and parse JSON with strict timeout and SSL handling."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DevDeploymentConsole-DeepLinkValidator/1.0 (+http://localhost)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None, f"HTTP {status}"
            raw = resp.read(1024 * 512).decode("utf-8", errors="replace")
            return json.loads(raw), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"Network unreachable: {e.reason}"
    except TimeoutError:
        return None, "Connection timed out (3.5s)"
    except json.JSONDecodeError:
        return None, "Invalid JSON content returned"
    except Exception as e:
        return None, str(e)


def verify_android_assetlinks(
    domain: str,
    package_name: str = "",
    expected_fingerprint: str = "",
    timeout: float = 3.5,
) -> dict[str, Any]:
    """Verify /.well-known/assetlinks.json for a given domain and package."""
    url = f"https://{domain}/.well-known/assetlinks.json"
    data, err = fetch_url_json(url, timeout=timeout)
    if err:
        return {
            "status": "unreachable",
            "url": url,
            "packageMatched": False,
            "fingerprintMatched": False,
            "foundFingerprints": [],
            "error": err,
            "message": f"Could not fetch assetlinks.json from {domain}: {err}",
        }

    if not isinstance(data, list):
        return {
            "status": "invalid_schema",
            "url": url,
            "packageMatched": False,
            "fingerprintMatched": False,
            "foundFingerprints": [],
            "message": "assetlinks.json root must be a JSON array",
        }

    norm_expected = _normalize_fingerprint(expected_fingerprint) if expected_fingerprint else ""
    matched_pkg = False
    matched_fp = False
    all_found_fps: list[str] = []

    for entry in data:
        if not isinstance(entry, dict):
            continue
        target = entry.get("target", {})
        if not isinstance(target, dict):
            continue
        if target.get("namespace") != "android_app":
            continue

        entry_pkg = target.get("package_name", "")
        if package_name and entry_pkg == package_name:
            matched_pkg = True
        elif not package_name:
            matched_pkg = True

        fps = target.get("sha256_cert_fingerprints", [])
        if isinstance(fps, list):
            for fp in fps:
                all_found_fps.append(str(fp))
                if norm_expected and _normalize_fingerprint(str(fp)) == norm_expected:
                    matched_fp = True

    status = "valid" if (matched_pkg and (matched_fp or not norm_expected)) else "mismatch"
    msg = (
        "AssetLinks verified and matching."
        if status == "valid"
        else f"Package matched: {matched_pkg}, SHA-256 fingerprint matched: {matched_fp}"
    )

    return {
        "status": status,
        "url": url,
        "packageMatched": matched_pkg,
        "fingerprintMatched": matched_fp,
        "expectedFingerprint": expected_fingerprint,
        "foundFingerprints": all_found_fps,
        "message": msg,
    }


def verify_apple_aasa(
    domain: str,
    team_id: str = "",
    bundle_id: str = "",
    timeout: float = 3.5,
) -> dict[str, Any]:
    """Verify /.well-known/apple-app-site-association for a given domain."""
    url = f"https://{domain}/.well-known/apple-app-site-association"
    data, err = fetch_url_json(url, timeout=timeout)
    if err:
        # Fallback to root /apple-app-site-association
        fallback_url = f"https://{domain}/apple-app-site-association"
        data, err = fetch_url_json(fallback_url, timeout=timeout)
        if err:
            return {
                "status": "unreachable",
                "url": url,
                "teamMatched": False,
                "bundleMatched": False,
                "foundAppIds": [],
                "error": err,
                "message": f"Could not fetch AASA from {domain}: {err}",
            }
        url = fallback_url

    if not isinstance(data, dict):
        return {
            "status": "invalid_schema",
            "url": url,
            "teamMatched": False,
            "bundleMatched": False,
            "foundAppIds": [],
            "message": "AASA content must be a JSON dictionary",
        }

    expected_app_id = f"{team_id}.{bundle_id}" if (team_id and bundle_id) else ""
    found_app_ids: list[str] = []

    applinks = data.get("applinks", {})
    details = applinks.get("details", []) if isinstance(applinks, dict) else []
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                app_id = item.get("appID") or item.get("appIDs")
                if isinstance(app_id, str):
                    found_app_ids.append(app_id)
                elif isinstance(app_id, list):
                    found_app_ids.extend([str(x) for x in app_id])

    matched_team = any(app_id.startswith(f"{team_id}.") for app_id in found_app_ids) if team_id else True
    matched_bundle = any(app_id.endswith(f".{bundle_id}") for app_id in found_app_ids) if bundle_id else True
    matched_full = (expected_app_id in found_app_ids) if expected_app_id else (matched_team and matched_bundle)

    status = "valid" if (matched_full and found_app_ids) else ("mismatch" if found_app_ids else "no_applinks")
    msg = (
        "Apple App Site Association verified."
        if status == "valid"
        else f"Found appIDs: {found_app_ids}, Expected: {expected_app_id or 'any'}"
    )

    return {
        "status": status,
        "url": url,
        "expectedAppId": expected_app_id,
        "teamMatched": matched_team,
        "bundleMatched": matched_bundle,
        "foundAppIds": found_app_ids,
        "message": msg,
    }


def validate_app_deep_links(
    app_id: str = "",
    domain_override: str = "",
    timeout: float = 3.5,
) -> dict[str, Any]:
    """Validate all deep links and universal links for a target app."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    android_domains = extract_android_domains(app_dir)
    ios_domains = extract_ios_domains(app_dir)
    all_domains = sorted(set(android_domains + ios_domains))
    if domain_override and domain_override not in all_domains:
        all_domains.append(domain_override)

    # Detect package name and bundle ID from config/app
    app_info = config.get_app_info(app_id) if app_id else {}
    package_name = app_info.get("package_name") or app_info.get("android_id_prod") or ""
    bundle_id = app_info.get("bundle_id") or app_info.get("ios_id_prod") or ""
    team_id = app_info.get("team_id") or ""

    domain_reports: list[dict[str, Any]] = []
    for domain in all_domains:
        android_report = verify_android_assetlinks(
            domain, package_name=package_name, timeout=timeout
        )
        ios_report = verify_apple_aasa(
            domain, team_id=team_id, bundle_id=bundle_id, timeout=timeout
        )
        domain_reports.append({
            "domain": domain,
            "inAndroid": domain in android_domains,
            "inIos": domain in ios_domains,
            "android": android_report,
            "ios": ios_report,
        })

    return {
        "success": True,
        "appId": app_id,
        "package": package_name,
        "bundleId": bundle_id,
        "domainsCount": len(all_domains),
        "domains": domain_reports,
    }
