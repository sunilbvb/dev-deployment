"""Formatting utilities and alert threshold constants for build size analysis."""

from __future__ import annotations

# Thresholds for size increase alerts
WARN_PERCENT_THRESHOLD = 10.0      # +10% size increase triggers warning
WARN_BYTES_THRESHOLD = 3 * 1024 * 1024   # +3 MB increase triggers warning
CRIT_PERCENT_THRESHOLD = 25.0      # +25% size increase triggers critical
CRIT_BYTES_THRESHOLD = 10 * 1024 * 1024  # +10 MB increase triggers critical
UNCOMPRESSED_WARN_SIZE = 500 * 1024      # >= 500 KB uncompressed asset triggers warning


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_delta_bytes(delta_bytes: int) -> str:
    """Format size change with explicit +/- sign."""
    if delta_bytes == 0:
        return "0 B"
    sign = "+" if delta_bytes > 0 else "-"
    abs_val = abs(delta_bytes)
    return f"{sign}{format_bytes(abs_val)}"


def format_delta_percent(delta_percent: float) -> str:
    """Format percentage change with explicit +/- sign."""
    if delta_percent == 0.0:
        return "0%"
    sign = "+" if delta_percent > 0 else ""
    return f"{sign}{delta_percent:.1f}%"


def detect_artifact_type(path_or_name: str) -> str:
    """Derive short artifact badge type from extension."""
    lower = path_or_name.lower()
    if lower.endswith(".aab"):
        return "AAB"
    if lower.endswith(".apk"):
        return "APK"
    if lower.endswith(".ipa"):
        return "IPA"
    if lower.endswith(".xcarchive"):
        return "XCARCHIVE"
    if lower.endswith(".app"):
        return "APP"
    if lower.endswith(".zip"):
        return "ZIP"
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "TAR"
    return "BUILD"
