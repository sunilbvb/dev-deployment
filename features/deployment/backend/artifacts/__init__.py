"""Artifact discovery, hosting, and QR code generation for Android APKs.

Provides local LAN Wi-Fi download endpoints, QR codes for instant mobile camera
scanning, and safe APK streaming. Python standard library only.
"""

from __future__ import annotations

from .distributor import get_apk_download_info
from .network import (
    format_bytes,
    get_lan_ip,
)
from .scanner import (
    find_apk_artifact,
    resolve_safe_apk_path,
)

__all__ = [
    "find_apk_artifact",
    "format_bytes",
    "get_apk_download_info",
    "get_lan_ip",
    "resolve_safe_apk_path",
]
