"""Multiplatform artifact finder, zip central directory inspector, and archive diffing."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import time
from typing import Any, Optional
import zipfile

from config import _resolve_app_dir, get_workspace_root
from .formatter import (
    UNCOMPRESSED_WARN_SIZE,
    detect_artifact_type,
    format_bytes,
    format_delta_bytes,
)


def find_build_artifact(
    app_id: Optional[str] = None,
    flavor: str = "",
    started_after: Optional[float] = None,
    artifact_types: Optional[list[str]] = None,
    ws_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Locate the most relevant or newest built artifact (.aab, .apk, .ipa) for an app."""
    ws = ws_root or get_workspace_root()
    search_dirs: list[Path] = []

    if app_id and app_id != "latest":
        try:
            app_dir = (ws / app_id) if (app_id and (ws / app_id).is_dir()) else (_resolve_app_dir(app_id) if app_id else ws)
            search_dirs.extend([
                app_dir / "build" / "app" / "outputs" / "bundle",
                app_dir / "build" / "app" / "outputs" / "flutter-apk",
                app_dir / "build" / "app" / "outputs" / "apk",
                app_dir / "build" / "ios" / "ipa",
                app_dir / "build" / "ios" / "archive",
                app_dir / "build",
                app_dir,
            ])
        except Exception:
            return None
    else:
        search_dirs.extend([
            ws / "build" / "app" / "outputs" / "bundle",
            ws / "build" / "app" / "outputs" / "flutter-apk",
            ws / "build" / "ios" / "ipa",
            ws / "build",
        ])

    patterns = ["*.aab", "*.apk", "*.ipa"]
    if artifact_types:
        patterns = [f"*.{t.lower().lstrip('.')}" for t in artifact_types]

    candidates: list[Path] = []
    seen: set[Path] = set()

    for d in search_dirs:
        if not d.is_dir():
            continue
        try:
            for pat in patterns:
                for p in d.rglob(pat):
                    if p.is_file() and p not in seen:
                        seen.add(p)
                        candidates.append(p)
        except Exception:
            pass

    if not candidates:
        return None

    flavor_clean = flavor.strip().lower()
    matched_candidates: list[Path] = []

    if flavor_clean and flavor_clean not in ("default", "any"):
        for cand in candidates:
            name_lower = cand.name.lower()
            if re.search(r'(^|[._\-])' + re.escape(flavor_clean) + r'($|[._\-])', name_lower):
                matched_candidates.append(cand)

    pool = matched_candidates if matched_candidates else candidates

    def _mtime_key(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    pool.sort(key=_mtime_key, reverse=True)

    selected = pool[0]
    if started_after is not None:
        for cand in pool:
            try:
                if cand.stat().st_mtime >= (started_after - 5.0):
                    selected = cand
                    break
            except Exception:
                continue

    try:
        st = selected.stat()
        art_type = detect_artifact_type(selected.name)
        return {
            "path": str(selected.resolve()),
            "filename": selected.name,
            "extension": selected.suffix.lower(),
            "type": art_type,
            "sizeBytes": st.st_size,
            "sizeFormatted": format_bytes(st.st_size),
            "mtime": st.st_mtime,
            "builtAtFormatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }
    except Exception:
        return None


def inspect_archive_contents(artifact_path: Path | str, max_entries: int = 15) -> dict[str, Any]:
    """Inspect zip-based build archive (.aab, .apk, .ipa) for largest assets and uncompressed bloat."""
    path = Path(artifact_path).resolve()
    if not path.is_file():
        return {"isArchive": False, "error": "Artifact file not found"}

    if path.suffix.lower() not in (".aab", ".apk", ".ipa", ".zip"):
        return {"isArchive": False, "message": f"Non-archive artifact type ({path.suffix})"}

    total_files = 0
    total_uncompressed = 0
    total_compressed = 0
    uncompressed_assets: list[dict[str, Any]] = []
    all_entries: list[dict[str, Any]] = []

    media_extensions = (
        ".mp4", ".mov", ".avi", ".mkv",
        ".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".gif",
        ".wav", ".mp3", ".ogg", ".aac", ".flac",
        ".pdf", ".bin", ".tflite", ".onnx", ".sqlite", ".db",
        ".ttf", ".otf", ".json", ".zip"
    )

    try:
        with zipfile.ZipFile(path, "r") as zf:
            infolist = zf.infolist()
            total_files = len(infolist)

            for info in infolist:
                if info.is_dir():
                    continue

                f_size = info.file_size
                c_size = info.compress_size
                is_stored = info.compress_type == zipfile.ZIP_STORED
                total_uncompressed += f_size
                total_compressed += c_size

                entry_item = {
                    "name": info.filename,
                    "path": info.filename,
                    "filename": Path(info.filename).name,
                    "sizeBytes": f_size,
                    "sizeFormatted": format_bytes(f_size),
                    "compressedBytes": c_size,
                    "compressedFormatted": format_bytes(c_size),
                    "compressType": "stored" if is_stored else "deflated",
                    "isUncompressed": is_stored,
                }
                all_entries.append(entry_item)

                name_lower = info.filename.lower()
                is_media_or_asset = (
                    name_lower.startswith("assets/")
                    or name_lower.startswith("base/assets/")
                    or name_lower.startswith("res/")
                    or name_lower.startswith("base/res/")
                    or "payload/" in name_lower
                    or any(name_lower.endswith(ext) for ext in media_extensions)
                )

                if is_stored and f_size >= UNCOMPRESSED_WARN_SIZE and is_media_or_asset:
                    uncompressed_assets.append({
                        "name": info.filename,
                        "path": info.filename,
                        "filename": Path(info.filename).name,
                        "sizeBytes": f_size,
                        "sizeFormatted": format_bytes(f_size),
                        "warning": (
                            f"Uncompressed asset '{Path(info.filename).name}' ({format_bytes(f_size)}) "
                            f"is stored without compression (STORED). Consider optimizing, compressing, "
                            f"or hosting remotely."
                        ),
                    })

    except zipfile.BadZipFile:
        return {"isArchive": False, "error": "Invalid or corrupted zip archive"}
    except Exception as exc:
        logging.exception("Failed to inspect archive contents for %s", path)
        return {"isArchive": False, "error": str(exc)}

    all_entries.sort(key=lambda e: e["sizeBytes"], reverse=True)
    uncompressed_assets.sort(key=lambda e: e["sizeBytes"], reverse=True)

    ratio = 0.0
    if total_uncompressed > 0:
        ratio = round((1.0 - (total_compressed / total_uncompressed)) * 100, 1)

    return {
        "isArchive": True,
        "totalFiles": total_files,
        "fileCount": total_files,
        "totalUncompressedBytes": total_uncompressed,
        "totalUncompressedFormatted": format_bytes(total_uncompressed),
        "totalCompressedBytes": total_compressed,
        "totalCompressedFormatted": format_bytes(total_compressed),
        "compressionRatio": ratio,
        "compressionRatioFormatted": f"{ratio}%",
        "hasUncompressedWarnings": len(uncompressed_assets) > 0,
        "uncompressedAssetCount": len(uncompressed_assets),
        "uncompressedAssets": uncompressed_assets[:10],
        "largestEntries": all_entries[:max_entries],
        "largestFiles": all_entries[:max_entries],
    }


def _compute_archive_diff(prev_path_str: Optional[str], curr_path_str: Optional[str]) -> dict[str, Any]:
    """Compare internal file entries between previous and current build archives."""
    if not prev_path_str or not curr_path_str:
        return {"hasDiff": False, "addedAssets": [], "removedAssets": [], "grownAssets": []}

    p_prev = Path(prev_path_str)
    p_curr = Path(curr_path_str)
    if not p_prev.is_file() or not p_curr.is_file():
        return {"hasDiff": False, "addedAssets": [], "removedAssets": [], "grownAssets": []}

    try:
        def read_map(p: Path) -> dict[str, int]:
            with zipfile.ZipFile(p, "r") as zf:
                return {info.filename: info.file_size for info in zf.infolist() if not info.is_dir()}

        prev_map = read_map(p_prev)
        curr_map = read_map(p_curr)

        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        grown: list[dict[str, Any]] = []

        for name, c_size in curr_map.items():
            if name not in prev_map:
                added.append({
                    "name": name,
                    "path": name,
                    "filename": Path(name).name,
                    "sizeBytes": c_size,
                    "sizeFormatted": format_bytes(c_size),
                    "status": "added",
                })
            else:
                p_size = prev_map[name]
                d = c_size - p_size
                if d > 0:
                    grown.append({
                        "name": name,
                        "path": name,
                        "filename": Path(name).name,
                        "previousSizeBytes": p_size,
                        "previousSizeFormatted": format_bytes(p_size),
                        "currentSizeBytes": c_size,
                        "currentSizeFormatted": format_bytes(c_size),
                        "deltaBytes": d,
                        "deltaFormatted": format_delta_bytes(d),
                        "status": "grown",
                    })

        for name, p_size in prev_map.items():
            if name not in curr_map:
                removed.append({
                    "name": name,
                    "path": name,
                    "filename": Path(name).name,
                    "sizeBytes": p_size,
                    "sizeFormatted": format_bytes(p_size),
                    "status": "removed",
                })

        added.sort(key=lambda x: x["sizeBytes"], reverse=True)
        removed.sort(key=lambda x: x["sizeBytes"], reverse=True)
        grown.sort(key=lambda x: x["deltaBytes"], reverse=True)

        return {
            "hasDiff": True,
            "addedCount": len(added),
            "removedCount": len(removed),
            "grownCount": len(grown),
            "addedAssets": added[:15],
            "removedAssets": removed[:10],
            "grownAssets": grown[:15],
        }
    except Exception:
        logging.exception("Failed to calculate archive entry diff")
        return {"hasDiff": False, "addedAssets": [], "removedAssets": [], "grownAssets": []}
