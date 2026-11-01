"""Crash Symbol Vault: ProGuard/R8 mapping.txt and Apple .dSYM archiver and downloader.

Allows 1-click discovery and zip export of obfuscation mapping files for Firebase
Crashlytics and Sentry symbolication. Pure Python standard library only.
"""

from __future__ import annotations

import hashlib
import io
import logging
import zipfile
from pathlib import Path
from typing import Any, Optional

import config

logger = logging.getLogger("artifacts.symbols")


def _calc_sha256(path: Path) -> str:
    """Calculate SHA-256 digest of a file safely."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def find_android_mappings(app_dir: Path, flavor: str = "") -> list[dict[str, Any]]:
    """Scan for ProGuard/R8 mapping.txt files."""
    results: list[dict[str, Any]] = []
    mapping_dirs = [
        app_dir / "build" / "app" / "outputs" / "mapping",
        app_dir / "android" / "app" / "build" / "outputs" / "mapping",
    ]

    found_files: list[Path] = []
    for md in mapping_dirs:
        if md.exists():
            found_files.extend(list(md.glob("**/mapping.txt")))

    if not found_files and (app_dir / "build").exists():
        found_files.extend(list((app_dir / "build").glob("**/mapping.txt")))

    for mf in found_files:
        try:
            st = mf.stat()
            rel = str(mf.relative_to(app_dir)) if app_dir in mf.parents else mf.name
            line_count = 0
            with open(mf, "r", encoding="utf-8", errors="ignore") as f:
                for _ in f:
                    line_count += 1

            parent_name = mf.parent.name
            results.append({
                "type": "mapping",
                "platform": "android",
                "filename": mf.name,
                "path": str(mf),
                "relativePath": rel,
                "flavor": parent_name,
                "sizeBytes": st.st_size,
                "lineCount": line_count,
                "sha256": _calc_sha256(mf),
                "modified": st.st_mtime,
            })
        except Exception as e:
            logger.debug("Failed scanning mapping file %s: %s", mf, e)

    return results


def find_ios_dsyms(app_dir: Path) -> list[dict[str, Any]]:
    """Scan for iOS .dSYM bundles and zip archives."""
    results: list[dict[str, Any]] = []
    dsym_candidates = [
        app_dir / "build" / "ios" / "archive",
        app_dir / "build" / "ios" / "iphoneos",
        app_dir / "ios" / "build",
    ]

    found_dirs: list[Path] = []
    for d in dsym_candidates:
        if d.exists():
            found_dirs.extend([p for p in d.glob("**/*.dSYM") if p.is_dir()])
            found_dirs.extend([p for p in d.glob("**/*dSYM*.zip") if p.is_file()])

    if not found_dirs and (app_dir / "build").exists():
        found_dirs.extend([p for p in (app_dir / "build").glob("**/*.dSYM") if p.is_dir()])

    for df in found_dirs:
        try:
            st = df.stat()
            rel = str(df.relative_to(app_dir)) if app_dir in df.parents else df.name
            is_zip = df.is_file() and df.suffix.lower() == ".zip"

            total_size = st.st_size
            if not is_zip:
                # Sum directory size
                total_size = sum(f.stat().st_size for f in df.glob("**/*") if f.is_file())

            results.append({
                "type": "dsym",
                "platform": "ios",
                "filename": df.name,
                "path": str(df),
                "relativePath": rel,
                "isZip": is_zip,
                "sizeBytes": total_size,
                "sha256": _calc_sha256(df) if is_zip else "",
                "modified": st.st_mtime,
            })
        except Exception as e:
            logger.debug("Failed scanning dSYM %s: %s", df, e)

    return results


def scan_symbols(app_id: str = "", flavor: str = "prod") -> dict[str, Any]:
    """Scan all crash symbol artifacts (mappings and dSYMs) for the application."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    mappings = find_android_mappings(app_dir, flavor=flavor)
    dsyms = find_ios_dsyms(app_dir)

    return {
        "success": True,
        "appId": app_id,
        "flavor": flavor,
        "count": len(mappings) + len(dsyms),
        "mappings": mappings,
        "dsyms": dsyms,
    }


def package_symbols_zip(app_id: str = "", symbol_type: str = "all", flavor: str = "prod") -> bytes:
    """Package selected symbols into a zip archive and return zip bytes."""
    ws = config.get_workspace_root()
    app_dir = ws / "apps" / app_id if app_id else ws
    if not app_dir.exists():
        app_dir = ws

    mappings = find_android_mappings(app_dir, flavor=flavor) if symbol_type in ("all", "mapping") else []
    dsyms = find_ios_dsyms(app_dir) if symbol_type in ("all", "dsym") else []

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write Android mappings
        for m in mappings:
            p = Path(m["path"])
            if p.exists() and p.is_file():
                arc_name = f"android/{m['flavor']}/{p.name}"
                zf.write(p, arcname=arc_name)

        # Write iOS dSYMs
        for d in dsyms:
            p = Path(d["path"])
            if p.exists():
                if p.is_file():
                    zf.write(p, arcname=f"ios/{p.name}")
                elif p.is_dir():
                    for item in p.rglob("*"):
                        if item.is_file():
                            rel_inside = item.relative_to(p)
                            zf.write(item, arcname=f"ios/{p.name}/{rel_inside}")

        if not mappings and not dsyms:
            zf.writestr("README.txt", f"No crash symbols found for app: {app_id}\nFlavor: {flavor}\n")

    buffer.seek(0)
    return buffer.getvalue()
