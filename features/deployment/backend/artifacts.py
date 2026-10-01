"""Artifact discovery, hosting, and QR code generation for Android APKs.

Provides local LAN Wi-Fi download endpoints, QR codes for instant mobile camera
scanning, and safe APK streaming. Python standard library only.
"""

from __future__ import annotations

from pathlib import Path
import re
import socket
import time
from typing import Any, Optional

from config import (
    _get_allowed_workspace_roots,
    _resolve_app_dir,
    get_workspace_root,
)
import qr


def get_lan_ip() -> str:
    """Discover the host machine's primary local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connecting to a public IP routes via the active network interface
        # without sending any packets.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


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


def get_apk_download_info(
    job_id: Optional[str] = None,
    app_id: Optional[str] = None,
    flavor: str = "",
    port: int = 18112,
    token: str = "",
    host_override: str = "",
) -> dict[str, Any]:
    """Compile download links, LAN IP, and QR code SVG/ASCII for mobile installation."""
    import jobs

    job_info = jobs.get_job(job_id).get("job") if job_id else None
    effective_app = app_id or (job_info.get("app") if job_info else "")
    effective_flavor = flavor or (job_info.get("flavor") if job_info else "")
    started_after = job_info.get("started_at") if job_info else None

    # Check if job already recorded an artifact
    artifact = job_info.get("artifact") if job_info else None
    if not artifact:
        artifact = find_apk_artifact(
            app_id=effective_app,
            flavor=effective_flavor,
            started_after=started_after,
        )

    if not artifact:
        return {
            "success": True,
            "hasApk": False,
            "jobId": job_id,
            "app": effective_app,
            "flavor": effective_flavor,
            "message": "No APK artifact found for this build or app.",
        }

    lan_ip = host_override or get_lan_ip()
    target_param = job_id if job_id else (effective_app or "latest")
    token_query = f"?token={token}" if token else ""

    download_url = f"http://{lan_ip}:{port}/api/deployment/download/{target_param}{token_query}"
    local_url = f"http://localhost:{port}/api/deployment/download/{target_param}{token_query}"

    qr_svg_markup = qr.qr_svg(download_url, box_size=6)
    qr_ascii_art = qr.qr_ascii(download_url)

    return {
        "success": True,
        "hasApk": True,
        "jobId": job_id,
        "app": effective_app,
        "flavor": effective_flavor,
        "filename": artifact["filename"],
        "path": artifact["path"],
        "sizeBytes": artifact["sizeBytes"],
        "sizeFormatted": artifact["sizeFormatted"],
        "mtime": artifact["mtime"],
        "builtAtFormatted": artifact["builtAtFormatted"],
        "downloadUrl": download_url,
        "localUrl": local_url,
        "lanIp": lan_ip,
        "port": port,
        "qrSvg": qr_svg_markup,
        "qrAscii": qr_ascii_art,
    }


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
