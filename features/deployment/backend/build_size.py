"""Build Size Inspector & Diff for Dev Deployment Console.

Provides:
1. Fast artifact discovery (.aab, .apk, .ipa) across Flutter, Android, iOS, and multiplatform builds.
2. Fast size comparison & diff against previous successful run of the same app and flavor.
   Example output: "AAB: 24.2 MB (+3.8 MB, +18%) ⚠️"
3. Deep archive inspection using standard library zipfile (no external dependencies):
   - Uncompressed asset detection (warns if large uncompressed media/assets are bundled with ZIP_STORED).
   - Top largest assets / files inside the build.
   - Archive entry diff between previous and current build to pinpoint exactly which files were added or grew.

Python standard library only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Optional
import zipfile

from config import (
    _resolve_app_dir,
    get_workspace_root,
)

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


# ─────────────────────────────────────────────────────────────────────────────
# 1. Multiplatform Artifact Discovery
# ─────────────────────────────────────────────────────────────────────────────

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

    # Filter by flavor if present in filename
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

    # Prefer artifact built after job start timestamp (with 5 sec leeway)
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


# ─────────────────────────────────────────────────────────────────────────────
# 2. Archive Content & Uncompressed Asset Inspection
# ─────────────────────────────────────────────────────────────────────────────

def inspect_archive_contents(artifact_path: Path | str, max_entries: int = 15) -> dict[str, Any]:
    """Inspect zip-based build archive (.aab, .apk, .ipa) for largest assets and uncompressed bloat."""
    path = Path(artifact_path).resolve()
    if not path.is_file():
        return {"isArchive": False, "error": "Artifact file not found"}

    # Supported zip-based packages
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

                # Check for uncompressed asset bloat
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

    # Sort largest entries descending
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


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fast Size Comparison & History Diff Engine
# ─────────────────────────────────────────────────────────────────────────────

def _get_history_file(ws_root: Optional[Path] = None) -> Path:
    ws = ws_root or get_workspace_root()
    return ws / ".dev-dashboard" / "deployment_history.jsonl"


def get_previous_successful_build(
    app_id: str,
    flavor: str = "",
    current_job_id: str = "",
    artifact_type: str = "",
    ws_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Locate the most recent previous successful build entry for the same app and flavor."""
    history_file = _get_history_file(ws_root)
    if not history_file.is_file():
        return None

    entries: list[dict[str, Any]] = []
    files_to_check = [history_file]
    rot = history_file.parent / (history_file.name + ".1")
    if rot.is_file():
        files_to_check.append(rot)

    for hf in files_to_check:
        try:
            lines = hf.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    entries.append(e)
                except Exception:
                    continue
        except Exception:
            pass

    for entry in entries:
        if entry.get("status") != "success":
            continue
        if current_job_id and entry.get("id") == current_job_id:
            continue
        if entry.get("app") != app_id:
            continue

        entry_flavor = (entry.get("flavor") or entry.get("env") or "").lower()
        target_flavor = (flavor or "").lower()
        if target_flavor and target_flavor not in ("any", "default") and entry_flavor and entry_flavor not in ("any", "default"):
            if entry_flavor != target_flavor:
                continue

        # Check if entry recorded an artifact or build size
        art = entry.get("artifact") or {}
        bs = entry.get("buildSize") or {}
        size_bytes = art.get("sizeBytes") or bs.get("currentSizeBytes")

        if size_bytes:
            art_t = art.get("type") or bs.get("artifactType") or detect_artifact_type(art.get("filename") or "")
            if artifact_type and art_t and art_t != artifact_type:
                # Type mismatch (e.g. comparing AAB against APK)
                continue

            return {
                "jobId": entry.get("id"),
                "app": entry.get("app"),
                "flavor": entry.get("flavor") or entry.get("env"),
                "completedAt": entry.get("completedAt") or (entry.get("finishedAt") * 1000 if entry.get("finishedAt") else None),
                "artifactPath": art.get("path") or bs.get("currentArtifactPath"),
                "filename": art.get("filename") or bs.get("currentFilename"),
                "artifactType": art_t,
                "sizeBytes": size_bytes,
                "sizeFormatted": format_bytes(size_bytes),
            }

    return None


def compare_build_size(
    app_id: str,
    flavor: str,
    current_artifact: dict[str, Any],
    current_job_id: str = "",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Fast size comparison against previous run and archive diff computation."""
    current_size = int(current_artifact.get("sizeBytes", 0))
    current_type = current_artifact.get("type") or detect_artifact_type(current_artifact.get("filename", ""))
    current_path = current_artifact.get("path") or ""

    # Inspect current archive contents
    inspection = inspect_archive_contents(current_path) if current_path else {}

    # Look up previous successful build baseline
    previous_build = get_previous_successful_build(
        app_id=app_id,
        flavor=flavor,
        current_job_id=current_job_id,
        artifact_type=current_type,
        ws_root=ws_root,
    )

    warnings: list[str] = []
    for ua in inspection.get("uncompressedAssets", []):
        warnings.append(ua.get("warning"))

    # Case A: First recorded build baseline (no previous run)
    if not previous_build:
        severity = "warning" if inspection.get("hasUncompressedWarnings") else "ok"
        summary = f"{current_type}: {format_bytes(current_size)} (first baseline)"
        return {
            "success": True,
            "hasBaseline": False,
            "artifactType": current_type,
            "currentSizeBytes": current_size,
            "currentSizeFormatted": format_bytes(current_size),
            "currentFilename": current_artifact.get("filename"),
            "currentArtifactPath": current_path,
            "previousBuild": None,
            "deltaBytes": 0,
            "deltaFormatted": "0 B",
            "deltaPercent": 0.0,
            "deltaPercentFormatted": "0%",
            "severity": severity,
            "badgeVariant": "warning" if severity == "warning" else "success",
            "summary": summary,
            "warnings": warnings,
            "inspection": inspection,
            "diff": {
                "hasDiff": False,
                "addedAssets": [],
                "removedAssets": [],
                "grownAssets": [],
            },
        }

    # Case B: Diff against previous build
    prev_size = int(previous_build.get("sizeBytes", 0))
    delta_bytes = current_size - prev_size
    delta_percent = 0.0
    if prev_size > 0:
        delta_percent = round((delta_bytes / prev_size) * 100, 1)

    delta_fmt = format_delta_bytes(delta_bytes)
    percent_fmt = format_delta_percent(delta_percent)

    # Calculate severity & badge
    if delta_percent >= CRIT_PERCENT_THRESHOLD or delta_bytes >= CRIT_BYTES_THRESHOLD:
        severity = "critical"
        badge_variant = "danger"
        status_icon = "🚨"
        warnings.insert(0, f"Critical Size Jump: Build increased by {percent_fmt} ({delta_fmt})!")
    elif delta_percent >= WARN_PERCENT_THRESHOLD or delta_bytes >= WARN_BYTES_THRESHOLD:
        severity = "warning"
        badge_variant = "warning"
        status_icon = "⚠️"
        warnings.insert(0, f"Size Warning: Build increased by {percent_fmt} ({delta_fmt})!")
    elif inspection.get("hasUncompressedWarnings"):
        severity = "warning"
        badge_variant = "warning"
        status_icon = "⚠️"
    else:
        severity = "ok"
        badge_variant = "success"
        status_icon = "✅" if delta_bytes < 0 else ""

    icon_str = f" {status_icon}" if status_icon else ""
    summary = f"{current_type}: {format_bytes(current_size)} ({delta_fmt}, {percent_fmt}){icon_str}".strip()

    # Detailed Archive Diff (if previous artifact file still exists on disk)
    diff_data = _compute_archive_diff(previous_build.get("artifactPath"), current_path)

    return {
        "success": True,
        "hasBaseline": True,
        "artifactType": current_type,
        "currentSizeBytes": current_size,
        "currentSizeFormatted": format_bytes(current_size),
        "currentFilename": current_artifact.get("filename"),
        "currentArtifactPath": current_path,
        "previousBuild": previous_build,
        "deltaBytes": delta_bytes,
        "deltaFormatted": delta_fmt,
        "deltaPercent": delta_percent,
        "deltaPercentFormatted": percent_fmt,
        "severity": severity,
        "badgeVariant": badge_variant,
        "summary": summary,
        "warnings": warnings,
        "inspection": inspection,
        "diff": diff_data,
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


# ─────────────────────────────────────────────────────────────────────────────
# 4. Master Job Inspector & Diff Runner
# ─────────────────────────────────────────────────────────────────────────────

def inspect_and_diff_job(job: dict[str, Any], ws_root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Inspect completed job's build artifact and generate size comparison against previous run."""
    app_id = job.get("app") or ""
    flavor = job.get("flavor") or job.get("env") or ""
    started_after = job.get("started_at")
    job_id = job.get("id") or ""

    artifact = job.get("artifact")
    if not artifact:
        artifact = find_build_artifact(
            app_id=app_id,
            flavor=flavor,
            started_after=started_after,
            ws_root=ws_root,
        )

    if not artifact or not artifact.get("path"):
        return None

    # Update job with discovered artifact if not present
    job["artifact"] = artifact

    # Run size comparison
    result = compare_build_size(
        app_id=app_id,
        flavor=flavor,
        current_artifact=artifact,
        current_job_id=job_id,
        ws_root=ws_root,
    )

    job["buildSize"] = result
    return result


def get_build_size_info(
    job_id: Optional[str] = None,
    app_id: Optional[str] = None,
    flavor: str = "",
    ws_root: Optional[Path] = None,
) -> dict[str, Any]:
    """API endpoint handler to fetch build size and diff for a job or app."""
    import jobs

    job_info = jobs.get_job(job_id).get("job") if job_id else None
    if job_info:
        if job_info.get("buildSize"):
            return {"success": True, "buildSize": job_info["buildSize"]}
        res = inspect_and_diff_job(job_info, ws_root=ws_root)
        if res:
            return {"success": True, "buildSize": res}

    effective_app = app_id or (job_info.get("app") if job_info else "")
    effective_flavor = flavor or (job_info.get("flavor") if job_info else "")

    artifact = find_build_artifact(
        app_id=effective_app,
        flavor=effective_flavor,
        ws_root=ws_root,
    )
    if not artifact:
        return {
            "success": False,
            "error": f"No build artifact found for '{effective_app}' ({effective_flavor or 'default'})",
        }

    res = compare_build_size(
        app_id=effective_app,
        flavor=effective_flavor,
        current_artifact=artifact,
        current_job_id=job_id or "",
        ws_root=ws_root,
    )
    return {"success": True, "buildSize": res}
