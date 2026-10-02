"""Systemd user service installer and status inspector."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

from .paths import get_repo_root


def install_systemd_service() -> dict[str, Any]:
    """Install and enable a systemd user service so deployment server runs in

    background on login.
    """
    repo_root = get_repo_root()
    start_sh = repo_root / "start.sh"

    service_dir = Path.home() / ".config" / "systemd" / "user"
    try:
        service_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": f"Cannot create systemd user directory: {e}"}

    service_content = f"""[Unit]
Description=Dev Deployment Console Server
After=network.target

[Service]
Type=simple
WorkingDirectory={repo_root}
ExecStart={start_sh}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
"""

    service_file = service_dir / "dev-deployment.service"
    try:
        service_file.write_text(service_content, encoding="utf-8")
    except Exception as e:
        return {"success": False, "error": f"Failed to write service file: {e}"}

    # Run systemctl daemon-reload and enable
    if shutil.which("systemctl"):
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
            res = subprocess.run(
                ["systemctl", "--user", "enable", "--now", "dev-deployment"],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return {
                    "success": True,
                    "message": "Background systemd service installed and started! Server will always be active.",
                    "serviceFile": str(service_file),
                }
            else:
                return {
                    "success": True,
                    "message": (
                        f"Service file created at {service_file}. "
                        f"Run 'systemctl --user enable --now dev-deployment' to activate."
                    ),
                    "serviceFile": str(service_file),
                    "warning": res.stderr.strip(),
                }
        except Exception as e:
            return {
                "success": True,
                "message": f"Service file created at {service_file}.",
                "serviceFile": str(service_file),
                "warning": str(e),
            }

    return {
        "success": True,
        "message": f"Service file written to {service_file}.",
        "serviceFile": str(service_file),
    }


def get_service_status() -> dict[str, Any]:
    """Check status of systemd user service if present."""
    if not shutil.which("systemctl"):
        return {"installed": False, "running": False, "enabled": False}

    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-active", "dev-deployment"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        is_active = res.stdout.strip() == "active"

        res_en = subprocess.run(
            ["systemctl", "--user", "is-enabled", "dev-deployment"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        is_enabled = res_en.stdout.strip() == "enabled"

        return {
            "installed": True,
            "running": is_active,
            "enabled": is_enabled,
        }
    except Exception:
        return {"installed": False, "running": False, "enabled": False}
