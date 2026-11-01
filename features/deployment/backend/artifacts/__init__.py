"""Artifact discovery, hosting, and QR code generation for Android APKs.

Provides local LAN Wi-Fi download endpoints, QR codes for instant mobile camera
scanning, and safe APK streaming. Python standard library only.
"""

from __future__ import annotations

from .distributor import (
    generate_ota_manifest_plist,
    get_apk_download_info,
    get_ipa_download_info,
)
from .network import (
    format_bytes,
    get_lan_ip,
)
from .scanner import (
    find_apk_artifact,
    find_ipa_artifact,
    resolve_safe_apk_path,
    resolve_safe_ipa_path,
)
from .symbols import (
    find_android_mappings,
    find_ios_dsyms,
    package_symbols_zip,
    scan_symbols,
)

__all__ = [
    "find_apk_artifact",
    "find_ipa_artifact",
    "format_bytes",
    "generate_ota_manifest_plist",
    "get_apk_download_info",
    "get_ipa_download_info",
    "get_lan_ip",
    "resolve_safe_apk_path",
    "resolve_safe_ipa_path",
    "find_android_mappings",
    "find_ios_dsyms",
    "package_symbols_zip",
    "scan_symbols",
]
