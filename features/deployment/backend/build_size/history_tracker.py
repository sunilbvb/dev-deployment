"""History tracking and baseline lookup for build size comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from config import get_workspace_root
from .formatter import detect_artifact_type, format_bytes


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
