"""Artifact scanner and safe path resolution for Android APKs."""

from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any, Optional

from config import (
    _get_allowed_workspace_roots,
    _resolve_app_dir,
    get_workspace_root,
)
from .network import format_bytes


def find_apk_artifact(
    app_id: Optional[str] = None,
    flavor: str = "",
    started_after: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Locate the most relevant or newest built APK for an app."""
    ws_root = get_workspace_root()
    search_dirs: list[Path] = []

    if app_id and app_id != "latest":
        try:
            app_dir = _resolve_app_dir(app_id)
            if app_dir == ws_root:
                from config import load_deploy_config
                deploy_cfg = load_deploy_config()
                known = set(deploy_cfg.get("apps", {}).keys())
                if app_id not in known and app_id != ws_root.name:
                    return None
            search_dirs.extend([
                app_dir / "build" / "app" / "outputs" / "flutter-apk",
                app_dir / "build" / "app" / "outputs" / "apk",
                app_dir / "build",
                app_dir,
            ])
        except Exception:
            return None
    else:
        search_dirs.extend([
            ws_root / "build" / "app" / "outputs" / "flutter-apk",
            ws_root / "build",
        ])

    apk_candidates: list[Path] = []
    seen: set[Path] = set()

    for d in search_dirs:
        if not d.is_dir():
            continue
        try:
            for p in d.rglob("*.apk"):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    apk_candidates.append(p)
        except Exception:
            pass

    if not apk_candidates:
        return None

    # Filter by flavor if present in filename
    flavor_clean = flavor.strip().lower()
    matched_candidates: list[Path] = []

    if flavor_clean and flavor_clean not in ("default", "any"):
        for cand in apk_candidates:
            name_lower = cand.name.lower()
            if re.search(r'(^|[._\-])' + re.escape(flavor_clean) + r'($|[._\-])', name_lower):
                matched_candidates.append(cand)

    pool = matched_candidates if matched_candidates else apk_candidates

    # Sort candidates by mtime descending (newest first)
    def _mtime_key(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    pool.sort(key=_mtime_key, reverse=True)

    # If started_after is specified, prefer APK built after that timestamp
    selected_apk = pool[0]
    if started_after is not None:
        for cand in pool:
            try:
                if cand.stat().st_mtime >= (started_after - 5.0):
                    selected_apk = cand
                    break
            except Exception:
                continue

    try:
        st = selected_apk.stat()
        return {
            "path": str(selected_apk.resolve()),
            "filename": selected_apk.name,
            "sizeBytes": st.st_size,
            "sizeFormatted": format_bytes(st.st_size),
            "mtime": st.st_mtime,
            "builtAtFormatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }
    except Exception:
        return None


def resolve_safe_apk_path(target: str) -> Optional[Path]:
    """Safely resolve an APK file path from a job_id or app_id, ensuring no path traversal."""
    if not target or ".." in target or "/" in target or "\\" in target:
        return None

    import jobs

    job_info = jobs.get_job(target).get("job")
    if job_info and job_info.get("artifact", {}).get("path"):
        cand = Path(job_info["artifact"]["path"]).resolve()
        if cand.is_file() and cand.suffix.lower() == ".apk":
            return cand

    app_id = job_info.get("app") if job_info else target
    flavor = job_info.get("flavor", "") if job_info else ""
    artifact = find_apk_artifact(app_id=app_id, flavor=flavor)
    if not artifact or not artifact.get("path"):
        return None

    cand = Path(artifact["path"]).resolve()
    if not cand.is_file() or cand.suffix.lower() != ".apk":
        return None

    # Verify cand is within an allowed workspace root
    allowed = _get_allowed_workspace_roots()
    cur = get_workspace_root().resolve()
    if cur not in allowed:
        allowed.append(cur)
    if any(cand == a or a in cand.parents for a in allowed):
        return cand

    return None


def find_ipa_artifact(
    app_id: Optional[str] = None,
    flavor: str = "",
    started_after: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Locate the most relevant or newest built iOS IPA for an app."""
    ws_root = get_workspace_root()
    search_dirs: list[Path] = []

    if app_id and app_id != "latest":
        try:
            app_dir = _resolve_app_dir(app_id)
            if app_dir == ws_root:
                from config import load_deploy_config
                deploy_cfg = load_deploy_config()
                known = set(deploy_cfg.get("apps", {}).keys())
                if app_id not in known and app_id != ws_root.name:
                    return None
            search_dirs.extend([
                app_dir / "build" / "ios" / "ipa",
                app_dir / "build" / "ios" / "archive",
                app_dir / "build" / "ios",
                app_dir / "build",
                app_dir,
            ])
        except Exception:
            return None
    else:
        search_dirs.extend([
            ws_root / "build" / "ios" / "ipa",
            ws_root / "build",
        ])

    ipa_candidates: list[Path] = []
    seen: set[Path] = set()

    for d in search_dirs:
        if not d.is_dir():
            continue
        try:
            for p in d.rglob("*.ipa"):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    ipa_candidates.append(p)
        except Exception:
            pass

    if not ipa_candidates:
        return None

    flavor_clean = flavor.strip().lower()
    matched_candidates: list[Path] = []

    if flavor_clean and flavor_clean not in ("default", "any"):
        for cand in ipa_candidates:
            name_lower = cand.name.lower()
            if re.search(r'(^|[._\-])' + re.escape(flavor_clean) + r'($|[._\-])', name_lower):
                matched_candidates.append(cand)

    pool = matched_candidates if matched_candidates else ipa_candidates

    def _mtime_key(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0.0

    pool.sort(key=_mtime_key, reverse=True)

    selected_ipa = pool[0]
    if started_after is not None:
        for cand in pool:
            try:
                if cand.stat().st_mtime >= (started_after - 5.0):
                    selected_ipa = cand
                    break
            except Exception:
                continue

    try:
        st = selected_ipa.stat()
        return {
            "path": str(selected_ipa.resolve()),
            "filename": selected_ipa.name,
            "sizeBytes": st.st_size,
            "sizeFormatted": format_bytes(st.st_size),
            "mtime": st.st_mtime,
            "builtAtFormatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        }
    except Exception:
        return None


def resolve_safe_ipa_path(target: str) -> Optional[Path]:
    """Safely resolve an IPA file path from a job_id or app_id, ensuring no path traversal."""
    if not target or ".." in target or "/" in target or "\\" in target:
        return None

    import jobs

    job_info = jobs.get_job(target).get("job")
    if job_info and job_info.get("artifact", {}).get("path"):
        cand = Path(job_info["artifact"]["path"]).resolve()
        if cand.is_file() and cand.suffix.lower() == ".ipa":
            return cand

    app_id = job_info.get("app") if job_info else target
    flavor = job_info.get("flavor", "") if job_info else ""
    artifact = find_ipa_artifact(app_id=app_id, flavor=flavor)
    if not artifact or not artifact.get("path"):
        return None

    cand = Path(artifact["path"]).resolve()
    if not cand.is_file() or cand.suffix.lower() != ".ipa":
        return None

    allowed = _get_allowed_workspace_roots()
    cur = get_workspace_root().resolve()
    if cur not in allowed:
        allowed.append(cur)
    if any(cand == a or a in cand.parents for a in allowed):
        return cand

    return None

