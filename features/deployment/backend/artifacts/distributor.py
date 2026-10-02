"""Download endpoint compiler and QR code distribution for mobile artifacts."""

from __future__ import annotations

from typing import Any, Optional

import qr
from .network import get_lan_ip
from .scanner import find_apk_artifact


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
