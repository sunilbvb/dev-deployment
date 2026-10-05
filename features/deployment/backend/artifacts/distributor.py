"""Download endpoint compiler and QR code distribution for mobile artifacts."""

from __future__ import annotations

from pathlib import Path
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
    # Only an .apk can be side-loaded. A job that built an .aab (Play upload) or .ipa
    # must not get an "APK ready" QR: its download link would 404.
    if artifact and not str(artifact.get("path", "")).lower().endswith(".apk"):
        return {"success": True, "hasApk": False, "jobId": job_id, "app": effective_app,
                "reason": f"{artifact.get('type') or 'This build'} cannot be installed from a QR code; only APK builds can."}
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


def generate_ota_manifest_plist(
    ipa_download_url: str,
    bundle_id: str = "com.example.app",
    version: str = "1.0.0",
    title: str = "App",
) -> str:
    """Generate Apple OTA manifest.plist conforming to itms-services specification."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string><![CDATA[{ipa_download_url}]]></string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{bundle_id}</string>
                <key>bundle-version</key>
                <string>{version}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{title}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>"""


def get_ipa_download_info(
    job_id: Optional[str] = None,
    app_id: Optional[str] = None,
    flavor: str = "",
    port: int = 18112,
    token: str = "",
    host_override: str = "",
    scheme: str = "https",
) -> dict[str, Any]:
    """Compile iOS IPA download link, OTA manifest URL, and itms-services QR code."""
    import jobs
    from .scanner import find_ipa_artifact
    from config import load_deploy_config

    job_info = jobs.get_job(job_id).get("job") if job_id else None
    effective_app = app_id or (job_info.get("app") if job_info else "")
    effective_flavor = flavor or (job_info.get("flavor") if job_info else "")
    started_after = job_info.get("started_at") if job_info else None

    artifact = None
    if job_info and job_info.get("artifact") and str(job_info.get("artifact")).endswith(".ipa"):
        artifact = {"path": str(job_info["artifact"]), "filename": Path(job_info["artifact"]).name, "sizeBytes": 0, "sizeFormatted": "-", "mtime": 0, "builtAtFormatted": "-"}
    if not artifact:
        artifact = find_ipa_artifact(
            app_id=effective_app,
            flavor=effective_flavor,
            started_after=started_after,
        )

    if not artifact:
        return {
            "success": True,
            "hasIpa": False,
            "jobId": job_id,
            "app": effective_app,
            "flavor": effective_flavor,
            "message": "No iOS IPA artifact found for this build or app.",
        }

    lan_ip = host_override or get_lan_ip()
    target_param = job_id if job_id else (effective_app or "latest")
    token_query = f"?token={token}" if token else ""

    deploy_cfg = load_deploy_config()
    app_cfg = deploy_cfg.get("apps", {}).get(effective_app, {})
    bundle_id = app_cfg.get(f"bundle_id_{effective_flavor}") or app_cfg.get("bundle_id") or "com.example.app"
    app_name = app_cfg.get("name") or effective_app or "iOS App"

    ipa_download_url = f"{scheme}://{lan_ip}:{port}/api/deployment/download-ipa/{target_param}{token_query}"
    token_param = f"&token={token}" if token else ""
    manifest_url = f"{scheme}://{lan_ip}:{port}/api/deployment/ota/manifest.plist?target={target_param}{token_param}"
    itms_url = f"itms-services://?action=download-manifest&url={manifest_url}"

    qr_svg_markup = qr.qr_svg(itms_url, box_size=6)
    qr_ascii_art = qr.qr_ascii(itms_url)

    return {
        "success": True,
        "hasIpa": True,
        "jobId": job_id,
        "app": effective_app,
        "appName": app_name,
        "flavor": effective_flavor,
        "bundleId": bundle_id,
        "filename": artifact["filename"],
        "path": artifact["path"],
        "sizeBytes": artifact["sizeBytes"],
        "sizeFormatted": artifact["sizeFormatted"],
        "mtime": artifact["mtime"],
        "builtAtFormatted": artifact["builtAtFormatted"],
        "ipaDownloadUrl": ipa_download_url,
        "manifestUrl": manifest_url,
        "itmsUrl": itms_url,
        "lanIp": lan_ip,
        "port": port,
        "qrSvg": qr_svg_markup,
        "qrAscii": qr_ascii_art,
    }

