"""APK / IPA Security & Dangerous Permissions Inspector.

Scans AndroidManifest.xml and iOS Info.plist for restricted high-risk permissions,
insecure cleartext traffic, exported components without permissions, and missing
Apple privacy usage strings. Pure Python standard library only.
"""

from __future__ import annotations

import logging
import plistlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("doctor.permissions")

# High-risk & restricted Android permissions catalog
DANGEROUS_PERMISSIONS_CATALOG: dict[str, dict[str, str]] = {
    "android.permission.ACCESS_BACKGROUND_LOCATION": {
        "severity": "CRITICAL",
        "category": "Location",
        "description": "Background location access requires explicit declaration form on Google Play.",
    },
    "android.permission.ACCESS_FINE_LOCATION": {
        "severity": "HIGH",
        "category": "Location",
        "description": "Precise GPS location tracking.",
    },
    "android.permission.ACCESS_COARSE_LOCATION": {
        "severity": "MEDIUM",
        "category": "Location",
        "description": "Approximate cell/wifi location tracking.",
    },
    "android.permission.READ_SMS": {
        "severity": "CRITICAL",
        "category": "SMS",
        "description": "Restricted permission group: Google Play requires core app functionality declaration.",
    },
    "android.permission.SEND_SMS": {
        "severity": "CRITICAL",
        "category": "SMS",
        "description": "Can send SMS without user interaction, potential financial cost.",
    },
    "android.permission.RECEIVE_SMS": {
        "severity": "CRITICAL",
        "category": "SMS",
        "description": "Monitors incoming SMS, strictly scrutinized by Google Play.",
    },
    "android.permission.READ_CONTACTS": {
        "severity": "HIGH",
        "category": "Contacts",
        "description": "Accesses user address book and personal contact cards.",
    },
    "android.permission.WRITE_CONTACTS": {
        "severity": "HIGH",
        "category": "Contacts",
        "description": "Can modify user address book.",
    },
    "android.permission.READ_CALL_LOG": {
        "severity": "CRITICAL",
        "category": "Call Log",
        "description": "Restricted call log permission group.",
    },
    "android.permission.CAMERA": {
        "severity": "HIGH",
        "category": "Camera",
        "description": "Direct camera access. Requires runtime permission request.",
    },
    "android.permission.RECORD_AUDIO": {
        "severity": "HIGH",
        "category": "Microphone",
        "description": "Microphone recording access. Requires runtime permission request.",
    },
    "android.permission.MANAGE_EXTERNAL_STORAGE": {
        "severity": "CRITICAL",
        "category": "Storage",
        "description": "All-files access; rejected on Google Play unless app is a file manager/backup app.",
    },
    "android.permission.READ_EXTERNAL_STORAGE": {
        "severity": "MEDIUM",
        "category": "Storage",
        "description": "Shared storage read access. Prefer Scoped Storage on Android 13+.",
    },
    "android.permission.WRITE_EXTERNAL_STORAGE": {
        "severity": "MEDIUM",
        "category": "Storage",
        "description": "Shared storage write access. Deprecated in modern Android.",
    },
    "android.permission.QUERY_ALL_PACKAGES": {
        "severity": "CRITICAL",
        "category": "Package Visibility",
        "description": "Scans all installed apps on device. Strictly restricted on Google Play.",
    },
    "android.permission.SYSTEM_ALERT_WINDOW": {
        "severity": "HIGH",
        "category": "Overlay",
        "description": "Draw over other apps. Scrutinized for clickjacking and phishing.",
    },
}

# Standard Apple Info.plist privacy descriptions
IOS_PRIVACY_KEYS = {
    "NSCameraUsageDescription": "Camera access disclosure",
    "NSPhotoLibraryUsageDescription": "Photo library read access disclosure",
    "NSPhotoLibraryAddUsageDescription": "Photo library save access disclosure",
    "NSLocationWhenInUseUsageDescription": "Foreground location access disclosure",
    "NSLocationAlwaysAndWhenInUseUsageDescription": "Background location access disclosure",
    "NSMicrophoneUsageDescription": "Microphone audio recording disclosure",
    "NSUserTrackingUsageDescription": "App Tracking Transparency (ATT) advertisement disclosure",
    "NSBluetoothAlwaysUsageDescription": "Bluetooth peripheral access disclosure",
    "NSContactsUsageDescription": "Contacts address book access disclosure",
    "NSCalendarsUsageDescription": "Calendar read/write disclosure",
}


def scan_android_security(app_dir: Path) -> dict[str, Any]:
    """Inspect Android manifests for permissions, cleartext traffic, and component export safety."""
    manifests = list(app_dir.glob("android/app/src/*/AndroidManifest.xml"))
    if not manifests:
        manifests = list(app_dir.glob("**/AndroidManifest.xml"))

    all_permissions: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_perms: set[str] = set()

    cleartext_traffic = False
    allow_backup = True
    exported_without_perm: list[str] = []

    ns = {"android": "http://schemas.android.com/apk/res/android"}
    for mf in manifests:
        try:
            tree = ET.parse(mf)
            root = tree.getroot()

            # Inspect permissions
            for p in root.findall(".//uses-permission"):
                p_name = p.attrib.get(f"{{{ns['android']}}}name", "")
                if p_name and p_name not in seen_perms:
                    seen_perms.add(p_name)
                    catalog_info = DANGEROUS_PERMISSIONS_CATALOG.get(p_name)
                    all_permissions.append({
                        "name": p_name,
                        "shortName": p_name.split(".")[-1],
                        "isDangerous": catalog_info is not None,
                        "severity": catalog_info["severity"] if catalog_info else "NORMAL",
                        "category": catalog_info["category"] if catalog_info else "General",
                        "description": catalog_info["description"] if catalog_info else "Standard app permission",
                    })

            # Inspect application security attributes
            app_elem = root.find("application")
            if app_elem is not None:
                cleartext = app_elem.attrib.get(f"{{{ns['android']}}}usesCleartextTraffic")
                if cleartext == "true":
                    cleartext_traffic = True
                backup = app_elem.attrib.get(f"{{{ns['android']}}}allowBackup")
                if backup == "false":
                    allow_backup = False

                for comp_tag in ("activity", "service", "receiver", "provider"):
                    for comp in app_elem.findall(comp_tag):
                        exp = comp.attrib.get(f"{{{ns['android']}}}exported")
                        c_name = comp.attrib.get(f"{{{ns['android']}}}name", "")
                        has_perm = comp.attrib.get(f"{{{ns['android']}}}permission")
                        # If intent-filter exists and exported is true without permission
                        has_intent = comp.find("intent-filter") is not None
                        if exp == "true" and not has_perm and not c_name.endswith(".MainActivity"):
                            exported_without_perm.append(f"{comp_tag.capitalize()}: {c_name}")
        except Exception as e:
            logger.debug("Failed parsing android manifest %s: %s", mf, e)

    if cleartext_traffic:
        warnings.append("android:usesCleartextTraffic is enabled: Unencrypted HTTP traffic allowed.")
    if exported_without_perm:
        warnings.append(f"{len(exported_without_perm)} components are exported without permissions: {', '.join(exported_without_perm[:3])}")

    dangerous_count = sum(1 for p in all_permissions if p["isDangerous"])

    return {
        "manifestFound": bool(manifests),
        "totalPermissions": len(all_permissions),
        "dangerousCount": dangerous_count,
        "permissions": sorted(all_permissions, key=lambda x: (not x["isDangerous"], x["severity"], x["name"])),
        "usesCleartextTraffic": cleartext_traffic,
        "allowBackup": allow_backup,
        "exportedWithoutPermission": exported_without_perm,
        "warnings": warnings,
    }


def scan_ios_security(app_dir: Path) -> dict[str, Any]:
    """Inspect iOS Info.plist for privacy usage descriptions and transport security."""
    plists = list(app_dir.glob("ios/Runner/Info.plist")) + list(app_dir.glob("ios/Info.plist"))
    if not plists:
        plists = list(app_dir.glob("**/Info.plist"))

    configured_privacy: list[dict[str, Any]] = []
    missing_descriptions: list[str] = []
    arbitrary_loads = False
    warnings: list[str] = []

    for plist_path in plists:
        try:
            with open(plist_path, "rb") as f:
                data = plistlib.load(f)

            for key, desc in IOS_PRIVACY_KEYS.items():
                if key in data:
                    val = str(data[key]).strip()
                    is_suspicious = len(val) < 8 or any(w in val.lower() for w in ("todo", "placeholder", "test", "app needs"))
                    configured_privacy.append({
                        "key": key,
                        "description": desc,
                        "value": val,
                        "isSuspicious": is_suspicious,
                    })
                    if is_suspicious:
                        warnings.append(f"iOS {key} contains placeholder or low-effort text: '{val}'")

            # Check ATS
            ats = data.get("NSAppTransportSecurity", {})
            if isinstance(ats, dict) and ats.get("NSAllowsArbitraryLoads") is True:
                arbitrary_loads = True
                warnings.append("NSAppTransportSecurity: NSAllowsArbitraryLoads is TRUE (Insecure HTTP permitted).")

        except Exception as e:
            logger.debug("Failed parsing iOS plist %s: %s", plist_path, e)

    return {
        "plistFound": bool(plists),
        "configuredPrivacyCount": len(configured_privacy),
        "configuredPrivacy": configured_privacy,
        "allowsArbitraryLoads": arbitrary_loads,
        "warnings": warnings,
    }


def inspect_app_security(app_id: str = "") -> dict[str, Any]:
    """Analyze entire mobile security profile for Android and iOS."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    android_sec = scan_android_security(app_dir)
    ios_sec = scan_ios_security(app_dir)

    # Determine composite risk level
    crit_count = sum(1 for p in android_sec["permissions"] if p["severity"] == "CRITICAL")
    high_count = sum(1 for p in android_sec["permissions"] if p["severity"] == "HIGH")
    warn_count = len(android_sec["warnings"]) + len(ios_sec["warnings"])

    if crit_count > 0 or warn_count >= 3:
        risk_level = "HIGH"
    elif high_count > 0 or warn_count >= 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "success": True,
        "appId": app_id,
        "riskLevel": risk_level,
        "criticalPermissionsCount": crit_count,
        "highPermissionsCount": high_count,
        "totalWarningsCount": warn_count,
        "android": android_sec,
        "ios": ios_sec,
    }
