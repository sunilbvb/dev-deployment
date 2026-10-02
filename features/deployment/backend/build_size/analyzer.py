"""Build size comparison, regression detection, and master runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .archive_inspector import (
    _compute_archive_diff,
    find_build_artifact,
    inspect_archive_contents,
)
from .formatter import (
    CRIT_BYTES_THRESHOLD,
    CRIT_PERCENT_THRESHOLD,
    WARN_BYTES_THRESHOLD,
    WARN_PERCENT_THRESHOLD,
    detect_artifact_type,
    format_bytes,
    format_delta_bytes,
    format_delta_percent,
)
from .history_tracker import get_previous_successful_build


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
