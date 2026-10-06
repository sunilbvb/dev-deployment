"""Store metadata reader, validator, and writer for Android & iOS Fastlane structures.

Pure Python standard library only.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger("metadata.store")

# Official store character limits
METADATA_LIMITS: dict[str, dict[str, int]] = {
    "android": {
        "changelog": 500,           # Google Play release notes limit
        "title": 30,               # App title
        "short_description": 80,   # Promotional summary
        "full_description": 4000,  # Full store listing
    },
    "ios": {
        "release_notes": 4000,     # What's new in this version
        "name": 30,                # App name
        "subtitle": 30,            # App subtitle
        "promotional_text": 170,   # Promotional text
        "description": 4000,       # Full description
        "keywords": 100,           # Comma-separated search keywords
    },
}

DEFAULT_LOCALES = ["en-US", "es-ES", "fr-FR", "de-DE", "ja-JP", "pt-BR"]


def _find_metadata_roots(app_dir: Path) -> dict[str, list[Path]]:
    """Locate candidate Fastlane metadata directories for Android and iOS."""
    candidates = {
        "android": [
            app_dir / "android" / "fastlane" / "metadata" / "android",
            app_dir / "fastlane" / "metadata" / "android",
            app_dir / "fastlane" / "android" / "metadata",
        ],
        "ios": [
            app_dir / "ios" / "fastlane" / "metadata",
            app_dir / "fastlane" / "metadata" / "ios",
            app_dir / "fastlane" / "metadata",
        ],
    }
    existing: dict[str, list[Path]] = {"android": [], "ios": []}
    for platform, paths in candidates.items():
        for p in paths:
            if p.exists() and p.is_dir():
                existing[platform].append(p)
    return existing


def _read_file_safe(path: Path) -> str:
    """Read a text file safely returning trimmed string."""
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        logger.debug("Failed reading file %s: %s", path, e)
    return ""


def get_store_metadata(app_id: str = "") -> dict[str, Any]:
    """Retrieve store metadata and localized changelogs for the target app."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    meta_roots = _find_metadata_roots(app_dir)

    # Scan Android metadata
    android_locales: dict[str, dict[str, Any]] = {}
    android_root = meta_roots["android"][0] if meta_roots["android"] else (app_dir / "android" / "fastlane" / "metadata" / "android")
    if android_root.exists():
        for loc_dir in android_root.iterdir():
            if loc_dir.is_dir() and not loc_dir.name.startswith("."):
                loc = loc_dir.name
                # Read changelog from changelogs/default.txt or first txt
                cl = ""
                cl_dir = loc_dir / "changelogs"
                if cl_dir.exists():
                    def_cl = cl_dir / "default.txt"
                    if def_cl.exists():
                        cl = _read_file_safe(def_cl)
                    else:
                        txts = sorted(cl_dir.glob("*.txt"))
                        if txts:
                            cl = _read_file_safe(txts[-1])
                title = _read_file_safe(loc_dir / "title.txt")
                short_desc = _read_file_safe(loc_dir / "short_description.txt")
                full_desc = _read_file_safe(loc_dir / "full_description.txt")

                android_locales[loc] = {
                    "locale": loc,
                    "changelog": cl,
                    "changelogLength": len(cl),
                    "changelogLimit": METADATA_LIMITS["android"]["changelog"],
                    "changelogExceeds": len(cl) > METADATA_LIMITS["android"]["changelog"],
                    "title": title,
                    "shortDescription": short_desc,
                    "fullDescription": full_desc,
                }

    # If no Android locales found, provide placeholder en-US
    if not android_locales:
        android_locales["en-US"] = {
            "locale": "en-US",
            "changelog": "",
            "changelogLength": 0,
            "changelogLimit": METADATA_LIMITS["android"]["changelog"],
            "changelogExceeds": False,
            "title": "",
            "shortDescription": "",
            "fullDescription": "",
        }

    # Scan iOS metadata
    ios_locales: dict[str, dict[str, Any]] = {}
    ios_root = meta_roots["ios"][0] if meta_roots["ios"] else (app_dir / "ios" / "fastlane" / "metadata")
    if ios_root.exists():
        for loc_dir in ios_root.iterdir():
            if loc_dir.is_dir() and not loc_dir.name.startswith("."):
                loc = loc_dir.name
                rn = _read_file_safe(loc_dir / "release_notes.txt")
                name = _read_file_safe(loc_dir / "name.txt")
                subtitle = _read_file_safe(loc_dir / "subtitle.txt")
                desc = _read_file_safe(loc_dir / "description.txt")
                promo = _read_file_safe(loc_dir / "promotional_text.txt")
                keywords = _read_file_safe(loc_dir / "keywords.txt")

                ios_locales[loc] = {
                    "locale": loc,
                    "releaseNotes": rn,
                    "releaseNotesLength": len(rn),
                    "releaseNotesLimit": METADATA_LIMITS["ios"]["release_notes"],
                    "releaseNotesExceeds": len(rn) > METADATA_LIMITS["ios"]["release_notes"],
                    "name": name,
                    "subtitle": subtitle,
                    "description": desc,
                    "promotionalText": promo,
                    "keywords": keywords,
                }

    # If no iOS locales found, provide placeholder en-US
    if not ios_locales:
        ios_locales["en-US"] = {
            "locale": "en-US",
            "releaseNotes": "",
            "releaseNotesLength": 0,
            "releaseNotesLimit": METADATA_LIMITS["ios"]["release_notes"],
            "releaseNotesExceeds": False,
            "name": "",
            "subtitle": "",
            "description": "",
            "promotionalText": "",
            "keywords": "",
        }

    return {
        "success": True,
        "appId": app_id,
        "limits": METADATA_LIMITS,
        "availableLocales": DEFAULT_LOCALES,
        "android": {
            "rootPath": str(android_root),
            "locales": android_locales,
        },
        "ios": {
            "rootPath": str(ios_root),
            "locales": ios_locales,
        },
    }


def save_store_metadata(
    app_id: str,
    platform: str,
    locale: str,
    release_notes: str = "",
    title: str = "",
    short_description: str = "",
    description: str = "",
    subtitle: str = "",
    keywords: str = "",
) -> dict[str, Any]:
    """Save updated metadata files for a platform and locale."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    locale = locale.strip() or "en-US"
    platform = platform.lower().strip()

    if platform == "android":
        target_root = app_dir / "android" / "fastlane" / "metadata" / "android" / locale
        cl_dir = target_root / "changelogs"
        cl_dir.mkdir(parents=True, exist_ok=True)
        (cl_dir / "default.txt").write_text(release_notes.strip() + "\n", encoding="utf-8")
        if title:
            (target_root / "title.txt").write_text(title.strip() + "\n", encoding="utf-8")
        if short_description:
            (target_root / "short_description.txt").write_text(short_description.strip() + "\n", encoding="utf-8")
        if description:
            (target_root / "full_description.txt").write_text(description.strip() + "\n", encoding="utf-8")

        return {
            "success": True,
            "message": f"Saved Android metadata for locale {locale}.",
            "savedPath": str(target_root),
        }

    elif platform == "ios":
        target_root = app_dir / "ios" / "fastlane" / "metadata" / locale
        target_root.mkdir(parents=True, exist_ok=True)
        (target_root / "release_notes.txt").write_text(release_notes.strip() + "\n", encoding="utf-8")
        if title:
            (target_root / "name.txt").write_text(title.strip() + "\n", encoding="utf-8")
        if subtitle:
            (target_root / "subtitle.txt").write_text(subtitle.strip() + "\n", encoding="utf-8")
        if description:
            (target_root / "description.txt").write_text(description.strip() + "\n", encoding="utf-8")
        if keywords:
            (target_root / "keywords.txt").write_text(keywords.strip() + "\n", encoding="utf-8")

        return {
            "success": True,
            "message": f"Saved iOS metadata for locale {locale}.",
            "savedPath": str(target_root),
        }

    return {"success": False, "error": f"Unsupported platform: {platform}. Use 'android' or 'ios'."}


def preview_store_card(app_id: str, platform: str, locale: str = "en-US") -> dict[str, Any]:
    """Generate mockup preview data for Google Play / App Store update card."""
    data = get_store_metadata(app_id)
    platform_key = "android" if platform.lower() == "android" else "ios"
    locales_data = data[platform_key]["locales"]
    current_meta = locales_data.get(locale) or locales_data.get("en-US") or {}

    notes = current_meta.get("changelog" if platform_key == "android" else "releaseNotes", "")
    title = current_meta.get("title" if platform_key == "android" else "name", app_id or "My Mobile App")

    return {
        "success": True,
        "platform": platform_key,
        "locale": locale,
        "appTitle": title,
        "whatsNew": notes or "Bug fixes and performance improvements.",
        "length": len(notes),
        "limit": METADATA_LIMITS[platform_key]["changelog" if platform_key == "android" else "release_notes"],
        "exceeds": len(notes) > METADATA_LIMITS[platform_key]["changelog" if platform_key == "android" else "release_notes"],
    }
