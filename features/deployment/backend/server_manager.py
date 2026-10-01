"""
Server lifecycle and system integration manager.

Provides desktop launcher (.desktop) generation and systemd user service
management so developers can run, auto-start, and control the deployment server
without typing terminal commands.
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess
from typing import Any


def get_repo_root() -> Path:
    """Resolve repository root directory."""
    cand = Path(__file__).resolve().parents[3]
    if (cand / "start.sh").is_file():
        return cand
    return Path.cwd().resolve()


def install_desktop_launcher() -> dict[str, Any]:
    """
    Install a .desktop application launcher to ~/.local/share/applications/
    and ~/Desktop/ so user can start server with a single click.
    """
    repo_root = get_repo_root()
    start_sh = repo_root / "start.sh"

    if not start_sh.is_file():
        return {"success": False, "error": f"start.sh not found at {start_sh}"}

    desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Dev Deployment Console
Comment=Flutter & Mobile Deployment Automation Dashboard
Exec="{start_sh}" --open
Path={repo_root}
Icon=utilities-terminal
Terminal=false
Categories=Development;Building;
StartupNotify=true
"""

    created_paths = []

    # 1. ~/.local/share/applications/ (appears in app search/dock)
    app_dir = Path.home() / ".local" / "share" / "applications"
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        target = app_dir / "dev-deployment.desktop"
        target.write_text(desktop_content, encoding="utf-8")
        target.chmod(0o755)
        created_paths.append(str(target))
    except Exception as e:
        logging.warning("Failed to write desktop launcher to %s: %s", app_dir, e)

    # 2. ~/Desktop/ (optional, if Desktop exists)
    desktop_dir = Path.home() / "Desktop"
    if desktop_dir.is_dir():
        try:
            target_desk = desktop_dir / "dev-deployment.desktop"
            target_desk.write_text(desktop_content, encoding="utf-8")
            target_desk.chmod(0o755)
            created_paths.append(str(target_desk))
        except Exception as e:
            logging.warning("Failed to write desktop launcher to %s: %s", desktop_dir, e)

    # Also keep a copy in repo root
    try:
        repo_desk = repo_root / "dev-deployment.desktop"
        repo_desk.write_text(desktop_content, encoding="utf-8")
        repo_desk.chmod(0o755)
    except Exception:
        pass

    # Update desktop database if available
    if shutil.which("update-desktop-database"):
        try:
            subprocess.run(["update-desktop-database", str(app_dir)], check=False, capture_output=True)
        except Exception:
            pass

    return {
        "success": True,
        "message": "Desktop shortcut created! You can now launch from your application menu or desktop.",
        "paths": created_paths,
    }


def install_systemd_service() -> dict[str, Any]:
    """
    Install and enable a systemd user service so deployment server runs in
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
            res = subprocess.run(["systemctl", "--user", "enable", "--now", "dev-deployment"], capture_output=True, text=True)
            if res.returncode == 0:
                return {
                    "success": True,
                    "message": "Background systemd service installed and started! Server will always be active.",
                    "serviceFile": str(service_file),
                }
            else:
                return {
                    "success": True,
                    "message": f"Service file created at {service_file}. Run 'systemctl --user enable --now dev-deployment' to activate.",
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
